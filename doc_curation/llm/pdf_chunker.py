"""PDF chunk processing with LLMs."""
import json
import logging
import os
import tempfile

import regex
from pypdf import PdfReader, PdfWriter
from tqdm import tqdm

from doc_curation.llm import dump_to_md
from doc_curation.llm.backend import LlmBackend
from doc_curation.md.file import MdFile


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


def process_pdf_chunks(file_in, prompt, dest_path, pages_per_chunk=5, model_id=None, api_key_path="gemini.vv", overwrite=False, backend: LlmBackend | None = None, cred_path=None):
  """Process PDF chunks with an LLM, saving markdown to dest_path.

  The model backend defaults to Gemini (api_key_path selects the key);
  pass backend= explicitly (e.g. a Claude backend) to use another
  provider, in which case api_key_path is ignored. model_id=None selects
  the backend's default model.
  """
  if backend is None:
    # Lazy import keeps this shared module free of provider imports.
    from doc_curation.llm.gemini.backend import GeminiBackend
    backend = GeminiBackend(api_key_path=api_key_path, model_id=model_id, cred_path=cred_path)

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
  chat = backend.new_chat(system_prompt=prompt, model_id=model_id)

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
        uploaded = backend.upload_file(temp_path)

        chunk_prompt = f"Convert pages {i + 1} to {end_page} into Markdown according to the system instructions."
        text = chat.send_parts([uploaded, chunk_prompt])

        chunk_metadata = scrub_response(chat.last_metadata())
        full_response_metadata.append({f"pages_{i+1}_to_{end_page}": chunk_metadata})

        if text:
          all_text_parts.append(text)
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


def process_file(file_in, prompt, dest_path, model_id=None, api_key_path="gemini.vv", backend: LlmBackend | None = None, cred_path=None):
  """Process a single file with an LLM, saving markdown to dest_path.

  Backend resolution mirrors process_pdf_chunks. Returns the output text.
  """
  if backend is None:
    from doc_curation.llm.gemini.backend import GeminiBackend
    backend = GeminiBackend(api_key_path=api_key_path, model_id=model_id, cred_path=cred_path)
  uploaded = backend.upload_file(file_in)
  text, raw_metadata = backend.generate_content(
    [uploaded, prompt],
    model_id=model_id,
  )
  metadata = json.dumps(
    scrub_response(raw_metadata),
    ensure_ascii=False,
    indent=2,
  )
  dump_to_md(dest_path, prompt, metadata, text, {"title": os.path.basename(file_in)})
  return text
