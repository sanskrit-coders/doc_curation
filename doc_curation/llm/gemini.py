import json

import os
import tempfile
import logging
import random

import time
from google.genai.errors import APIError, ClientError, ServerError

import regex
from google.genai import types
from pypdf import PdfReader, PdfWriter

from google import genai
from tqdm import tqdm

from curation_utils import creds
from doc_curation import llm
from doc_curation.llm import dump_to_md
from doc_curation.md.file import MdFile

# Silence verbose SDK trace and HTTP debug logs
for logger_name in ["google", "google.genai", "_trace", "httpx", "httpcore", "_client", "chats"]:
  logger = logging.getLogger(logger_name)
  logger.setLevel(logging.WARNING)
  logger.propagate = False

_clients = {}


def scrub_response(obj):
  """Remove nulls and large text fields from Gemini response."""
  if isinstance(obj, dict):
    out = {}

    for k, v in obj.items():
      # Drop null values
      if v is None:
        continue

      # Drop generated text and thought signatures
      if k in {"text", "thought_signature"}:
        continue

      v = scrub_response(v)

      # Drop empty containers
      if v in ({}, [], None):
        continue

      out[k] = v

    return out

  if isinstance(obj, list):
    return [x for item in obj if (x := scrub_response(item)) not in ({}, [], None)]

  return obj

def get_client(api_key_path, cred_path="/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/tokens.toml"):
  # Cache per key-path so rotating api_key_path in
  # process_pdf_chunks_with_keys actually uses a different key.
  # (A single global client made rotation a no-op.)
  if api_key_path not in _clients:
    api_key = creds.get_toml_value(path=cred_path, key=api_key_path)
    _clients[api_key_path] = genai.Client(api_key=api_key)
  return _clients[api_key_path]


def process_pdf_chunks(file_in, prompt, dest_path, pages_per_chunk=5, model_id="gemini-3.5-flash", api_key_path="gemini.vv", overwrite=False):
  client = get_client(api_key_path=api_key_path)

  reader = PdfReader(file_in)
  total_pages = len(reader.pages)

  full_response_metadata = []
  all_text_parts = []

  metadata = {"title": "UNK", "continue_page": 1}
  if not overwrite and os.path.exists(dest_path):
    md_file = MdFile(dest_path)
    metadata, content = md_file.read()
    all_text_parts.append(content)
  start_page = metadata.get("continue_page", 1)

  # Load the detailed prompt once as a system instruction
  config = types.GenerateContentConfig(
    system_instruction=prompt,
  )
  chat = client.chats.create(model=model_id, config=config)

  # Convert 1-indexed start_page to 0-indexed for Python logic
  start_index = max(0, start_page - 1)
  combined_prompt = f"PROMPT 0:  \n{prompt}\n"
  try:
    for i in tqdm(range(start_index, total_pages, pages_per_chunk), desc="Processing PDF Chunks"):
      end_page = min(i + pages_per_chunk, total_pages)
  
      writer = PdfWriter()
      for j in range(i, end_page):
        writer.add_page(reader.pages[j])
  
      with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_path = temp_file.name
        writer.write(temp_file)
  
      try:
        uploaded = client.files.upload(file=temp_path)
  
        chunk_prompt = f"Convert pages {i + 1} to {end_page} into Markdown according to the system instructions."
        response = chat.send_message([uploaded, chunk_prompt])
  
        chunk_metadata = scrub_response(response.model_dump())
        full_response_metadata.append({f"pages_{i+1}_to_{end_page}": chunk_metadata})
  
        if response.text:
          all_text_parts.append(response.text)
          all_text_parts[-1] = regex.sub("```.*", "", all_text_parts[-1])
          metadata["continue_page"] = end_page + 1
  
      finally:
        if os.path.exists(temp_path):
          os.remove(temp_path)
    metadata.pop("continue_page", None)
  except Exception as e:
    logging.error(f"\n[Error encountered: {e}]. Saving partial progress up to this point... Continue from start page : {metadata.get('continue_page')}")
    raise
  
  finally:
    combined_metadata = json.dumps(full_response_metadata, ensure_ascii=False, indent=2)
    combined_text = "\n\n".join(all_text_parts)
    dump_to_md(dest_path, prompt=combined_prompt, response_headers=combined_metadata, content=combined_text, metadata=metadata)







def _get_retry_delay(exc, default_delay):
  """
  Extract Gemini retryDelay from exception text, e.g.

      'retryDelay': '27s'

  Falls back to the exponential backoff delay.
  """
  text = str(exc)

  match = regex.search(r"'retryDelay':\s*'(\d+)s'", text)
  if match:
    return int(match.group(1))

  match = regex.search(r"Please retry in ([\d.]+)s", text)
  if match:
    return float(match.group(1))

  return default_delay

def _should_rotate_key(exc):
  """Quota/rate-limit errors are per-key: rotating to a fresh key helps.

  Model overload / transient 5xx (e.g. 503 UNAVAILABLE "high demand ...
  try again later") is global to the model: all keys hit the same
  overloaded backend, so backoff + retry the SAME key instead.
  """
  code = getattr(exc, "code", None)
  if code == 429:
    return True
  if code in (500, 502, 503, 504):
    return False

  status = str(getattr(exc, "status", "") or "").upper()
  if status == "RESOURCE_EXHAUSTED":
    return True
  if status in ("INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"):
    return False

  text = str(exc)
  text_lower = text.lower()
  if (
      "resource_exhausted" in text_lower
      or "quota" in text_lower
      or "rate limit" in text_lower
      or "retrydelay" in text_lower
      or "please retry in" in text_lower
      or "429" in text
  ):
    return True
  return False


# Example errors -
# 'error': {'code': 429, 'message': 'You exceeded your current quota.... Please retry in 27.065191817s.'}
def _is_retryable_gemini_error(exc):
  # 5xx are transient server-side failures - always retry (same key or rotated,
  # decided by _should_rotate_key).
  if isinstance(exc, ServerError):
    return True

  code = getattr(exc, "code", None)
  if code in (429, 500, 502, 503, 504):
    return True

  status = str(getattr(exc, "status", "") or "").upper()
  if status in ("RESOURCE_EXHAUSTED", "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"):
    return True

  text = str(exc)
  text_lower = text.lower()

  return (
      "resource_exhausted" in text_lower
      or "429" in text
      or "500" in text
      or "502" in text
      or "503" in text
      or "504" in text
      or "quota" in text_lower
      or "rate limit" in text_lower
      or "retrydelay" in text_lower
      or "internal" in text_lower
      or "unavailable" in text_lower
      or "deadline" in text_lower
      or "overloaded" in text_lower
      or "try again" in text_lower
      or "timeout" in text_lower
      or "timed out" in text_lower
      or "connection" in text_lower
      or "reset" in text_lower
      or "temporarily" in text_lower
  )


def process_pdf_chunks_with_keys(
    api_key_path="gemini_friends",
    max_attempts=None,
    max_transient_retries=8,
    *args,
    **kwargs,
):
  keys = list(creds.get_toml_value(api_key_path).keys())

  if not keys:
    raise ValueError(f"No API keys found in {api_key_path}")

  i = random.randrange(len(keys))

  if max_attempts is None:
    max_attempts = len(keys)

  for attempt in range(max_attempts):
    key_name = keys[i % len(keys)]
    key = f"{api_key_path}.{key_name}"

    for transient_attempt in range(max_transient_retries + 1):
      try:
        logging.info("Cred %s", key)

        return process_pdf_chunks(
          api_key_path=key,
          *args,
          **kwargs,
        )

      except Exception as e:
        if not _is_retryable_gemini_error(e):
          raise

        if _should_rotate_key(e):
          base_delay = min(2 ** attempt, 300)
          delay = _get_retry_delay(e, base_delay)
          logging.warning(
            f"Cred {key} quota/rate-limit ({e}). "
            "Sleeping %.1fs and rotating.",
            delay,
          )
          time.sleep(delay)
          break

        # Model overload / transient 5xx / transport blip (e.g. 503
        # UNAVAILABLE "high demand ... try again later"): same backend for
        # every key, so backoff + retry the SAME key.
        if transient_attempt >= max_transient_retries:
          base_delay = min(2 ** attempt, 300)
          delay = _get_retry_delay(e, base_delay)
          logging.warning(
            f"Cred {key} overload persists after "
            f"{max_transient_retries + 1} same-key tries ({e}). "
            "Sleeping %.1fs and rotating as fallback.",
            delay,
          )
          time.sleep(delay)
          break

        base_delay = min(5 * (2 ** transient_attempt), 300)
        delay = _get_retry_delay(e, base_delay)
        # Small jitter so concurrent workers don't wake in lockstep.
        delay = delay + random.uniform(0, 1)
        logging.warning(
          f"Model overloaded/transient ({e}). "
          f"Sleeping {delay:.1f}s and retrying same key {key} "
          f"(try {transient_attempt + 2}/{max_transient_retries + 1}).",
        )
        time.sleep(delay)
        continue

    i += 1

  raise RuntimeError(
    f"Failed after {max_attempts} attempts across {len(keys)} API keys"
  )


def process_file(file_in, prompt, dest_path, model_id="gemini-3.5-flash", api_key_path="gemini.vv"):
  client = get_client(api_key_path=api_key_path)
  uploaded = client.files.upload(
    file=file_in
  )
  response = client.models.generate_content(
    model=model_id,
    contents=[
      uploaded,
      prompt
    ]
  )
  metadata = json.dumps(
    scrub_response(response.model_dump()),
    ensure_ascii=False,
    indent=2,
  )
  dump_to_md(dest_path, prompt, metadata, response.text)
  return response


if __name__ == '__main__':
  pass
  process_pdf_chunks_with_keys(file_in="/media/vvasuki/vData/text/granthasangrahaH/kAvyam/shrIvaiShNavakRtam/yatirAja-vijaya-nATakam.pdf", dest_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/rUpakam/naDAdUr-ghaTikA-shata-varadaH/yatirAja-vijaya-nATakam.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md"))