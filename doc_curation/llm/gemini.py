import inspect
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
from doc_curation.md import content_processor as md_content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile

_DEFAULT_TOKENS_PATH = inspect.signature(creds.get_toml_value).parameters["path"].default

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


TEXT_CONTINUE_MARKER_RE = regex.compile(
  r"<!--\s*GEMINI-TEXT-CONTINUE(?:\s+done=(\d+)\s+total=(\d+))?\s*-->"
)


def _make_continue_marker(done, total):
  return f"<!-- GEMINI-TEXT-CONTINUE done={done} total={total} -->"


def _split_resume_body(body):
  """Split a checkpointed body into (done_text, todo_text, done, total).

  Returns None when no continuation marker is present.
  """
  m = TEXT_CONTINUE_MARKER_RE.search(body)
  if not m:
    return None
  done = int(m.group(1)) if m.group(1) is not None else 0
  total = int(m.group(2)) if m.group(2) is not None else None
  return body[:m.start()].strip(), body[m.end():].strip(), done, total


def _split_oversized_para(para, max_chunk_chars):
  """Split a single para exceeding max_chunk_chars at sentence/word bounds.

  Prefers the latest sentence boundary in each window (danda | . ! ? |
  newline | space) so chunks stay as large as possible while ending
  cleanly; hard-splits only when no boundary exists.
  """
  chunks = []
  start = 0
  n = len(para)
  min_cut = max(1, int(max_chunk_chars * 0.3))
  while start < n:
    if n - start <= max_chunk_chars:
      tail = para[start:].strip()
      if tail:
        chunks.append(tail)
      break
    window = para[start:start + max_chunk_chars]
    matches = list(regex.finditer(r"[।॥]+|[.!?…]+|\n+|\s+", window))
    viable = [m for m in matches if m.end() >= min_cut]
    cut = viable[-1].end() if viable else max_chunk_chars
    piece = para[start:start + cut].strip()
    if piece:
      chunks.append(piece)
    # Guarantee progress even if strip() emptied a whitespace-only piece.
    start += max(cut, 1)
  return chunks


def _split_text_into_chunks(text, max_chunk_chars=12000):
  """Split text into chunks of ~max_chunk_chars.

  Primary split on blank lines (\\n\\n+); oversized paras fall back to
  sentence boundaries (। ॥ . ! ? newline) then word boundaries.
  Returns chunks in order; concatenated (with whitespace normalized)
  they cover the full input.
  """
  text = text.strip()
  if not text:
    return []
  paras = [p for p in regex.split(r"\n\s*\n+", text) if p.strip() != ""]
  chunks = []
  current = []
  current_len = 0
  for para in paras:
    para = para.strip()
    if not para:
      continue
    if len(para) > max_chunk_chars:
      if current:
        chunks.append("\n\n".join(current))
        current = []
        current_len = 0
      chunks.extend(_split_oversized_para(para, max_chunk_chars))
    elif current and current_len + 2 + len(para) > max_chunk_chars:
      chunks.append("\n\n".join(current))
      current = [para]
      current_len = len(para)
    else:
      current.append(para)
      current_len += (2 if current_len else 0) + len(para)
  if current:
    chunks.append("\n\n".join(current))
  return [c for c in (c.strip() for c in chunks) if c]


def _as_file_path(file_in):
  """Accept an MdFile or a path; always return a usable path string."""
  return file_in.file_path if isinstance(file_in, MdFile) else file_in


def process_text_chunks(file_in, prompt, max_chunk_chars=12000, model_id="gemini-3.5-flash", api_key_path="gemini.vv", dry_run=False):
  """Process a huge text file chunk-by-chunk with Gemini, in place.

  Splits the file body via _split_text_into_chunks, sends each chunk to
  the chat (system instruction = prompt) in order, and replaces each input
  chunk with the model's output chunk. The input file is overwritten with
  the joined outputs (frontmatter, if any, is preserved verbatim).

  Checkpointing: after every processed chunk the file holds
  <processed outputs> + <!-- GEMINI-TEXT-CONTINUE done=k total=n --> +
  <remaining original chunks>. On failure the latest checkpoint is already
  on disk (provided at least one chunk completed, otherwise the input is
  untouched), so re-running resumes after the marker instead of redoing
  processed chunks. The marker is removed on full success. Returns the
  processed text. With dry_run=True nothing is written.
  """
  file_in = _as_file_path(file_in)
  md_file = MdFile(file_in)
  metadata, content = md_file.read()

  resume = _split_resume_body(content)
  if resume is None:
    done_prefix = ""
    done_count = 0
    chunks = _split_text_into_chunks(content, max_chunk_chars=max_chunk_chars)
    total_chunks = len(chunks)
  else:
    done_prefix, todo_text, done_count, marked_total = resume
    chunks = _split_text_into_chunks(todo_text, max_chunk_chars=max_chunk_chars)
    if not chunks:
      # Marker present but nothing left to do: finalize by dropping it.
      if not dry_run:
        _dump_md_file_atomic(md_file, metadata, done_prefix)
      return done_prefix
    total_chunks = marked_total or (done_count + len(chunks))
    total_chunks = max(total_chunks, done_count + len(chunks))

  if not chunks:
    # Frontmatter-only / whitespace-only file: nothing to process.
    logging.debug(f"No text content in {file_in}; returning silently.")
    return ""

  client = get_client(api_key_path=api_key_path)

  config = types.GenerateContentConfig(
    system_instruction=prompt,
  )
  chat = client.chats.create(model=model_id, config=config)

  processed_new = []
  try:
    for idx in tqdm(range(len(chunks)), desc="Processing Text Chunks"):
      chunk_text = chunks[idx]
      chunk_prompt = (
        f"Process text chunk {done_count + idx + 1} of {total_chunks} "
        f"according to the system instructions:\n\n{chunk_text}"
      )
      response = chat.send_message(chunk_prompt)

      text = regex.sub("```.*", "", response.text or "")
      if not text.strip():
        raise RuntimeError(f"Empty response for chunk {done_count + idx + 1}/{total_chunks}")
      processed_new.append(text)

      # Checkpoint so a later attempt resumes after the marker.
      prefix = "\n\n".join(([done_prefix] if done_prefix else []) + processed_new)
      remaining = chunks[idx + 1:]
      if remaining and not dry_run:
        marker = _make_continue_marker(done_count + idx + 1, total_chunks)
        _dump_md_file_atomic(
          md_file, metadata,
          prefix + "\n\n" + marker + "\n\n" + "\n\n".join(remaining),
        )
  except Exception as e:
    done_so_far = done_count + len(processed_new)
    if processed_new or done_count:
      # A checkpoint reflecting all completed chunks is on disk (written
      # after the last success, or pre-existing resume state).
      logging.error(
        f"\n[Error encountered on chunk {done_so_far + 1}/{total_chunks}: {e}]. "
        f"Checkpoint saved in {file_in}; re-run to resume."
      )
    else:
      # Failed before the first chunk completed: nothing was written, so
      # don't claim a checkpoint exists.
      logging.error(
        f"\n[Error encountered on chunk 1/{total_chunks}: {e}]. "
        f"No progress made; input file {file_in} left unmodified."
      )
    raise

  combined_text = "\n\n".join(([done_prefix] if done_prefix else []) + processed_new)
  if not dry_run:
    _dump_md_file_atomic(md_file, metadata, combined_text)
  return combined_text


DETAIL_SPLIT_MARKER_RE = regex.compile(r"<!--\s*GEMINI-DETAIL-SPLIT\s+(\d+)\s*-->")

# Frontmatter keys recording process_details checkpoint progress. Removed
# on full success.
DETAILS_PROGRESS_KEYS = (
  "gemini_details_pattern",
  "gemini_details_done",  # legacy single count; migrated to gemini_batches_done
  "gemini_batches_done",  # list like ["1-5", "6-11"]: completed detail ranges
  "gemini_details_total",
)


def _parse_batches_ledger(value):
  """Parse a gemini_batches_done ledger into [(start, end), ...] or None.

  Requires well-formed contiguous ranges starting at 1.
  """
  if not isinstance(value, (list, tuple)) or not value:
    return None
  ranges = []
  for entry in value:
    m = regex.fullmatch(r"(\d+)-(\d+)", str(entry).strip())
    if not m:
      return None
    start, end = int(m.group(1)), int(m.group(2))
    if start < 1 or end < start:
      return None
    if not ranges and start != 1:
      return None
    if ranges and start != ranges[-1][1] + 1:
      return None
    ranges.append((start, end))
  return ranges


def _make_detail_split_marker(index):
  return f"<!-- GEMINI-DETAIL-SPLIT {index:04d} -->"


def _normalize_detail_pattern(detail_pattern):
  if detail_pattern is None:
    return ""
  return detail_pattern.pattern if hasattr(detail_pattern, "pattern") else detail_pattern


def _without_details_progress(metadata):
  cleaned = dict(metadata)
  for k in DETAILS_PROGRESS_KEYS:
    cleaned.pop(k, None)
  return cleaned


def _dump_md_file_atomic(md_file, metadata, content):
  """Write an md file atomically (temp + rename) so a crash can't corrupt it."""
  tmp_path = md_file.file_path + ".tmp"
  tmp_md = MdFile(tmp_path, frontmatter_type=md_file.frontmatter_type)
  tmp_md.dump_to_file(metadata=dict(metadata), content=content, dry_run=False, silent=True)
  os.replace(tmp_path, md_file.file_path)


def _split_detail_batch(processed_batch, expected):
  """Split processed batch text back into {index: text} via split markers.

  Raises RuntimeError listing expected vs found markers on any mismatch
  (dropped/altered/duplicated markers, or leading junk before the first
  marker).
  """
  found = DETAIL_SPLIT_MARKER_RE.split(processed_batch)
  # split() yields ['', '0001', text1, '0002', text2, ...] when the batch
  # starts with a marker as constructed above.
  expected = list(expected)
  outputs = {}
  ok = found[0].strip() == "" and len(found) == 1 + 2 * len(expected)
  if ok:
    for num_str, text in zip(found[1::2], found[2::2]):
      outputs[int(num_str)] = text.strip()
    ok = sorted(outputs) == expected
  if not ok:
    found_markers = [int(n) for n in found[1::2]]
    raise RuntimeError(
      f"Marker mismatch (expected details {expected}, found markers {found_markers}, "
      f"output chars {len(processed_batch)})"
    )
  return outputs


def _generate_with_gemini(system_prompt, user_text, model_id, api_key_path):
  """Single Gemini chat exchange with no files involved.

  Batches always go as one message, so unlike process_text_chunks there is
  no chunking, no CONTINUE markers, and no temp files.
  """
  client = get_client(api_key_path=api_key_path)
  config = types.GenerateContentConfig(system_instruction=system_prompt)
  chat = client.chats.create(model=model_id, config=config)
  response = chat.send_message(user_text)
  text = regex.sub("```.*", "", response.text or "")
  if not text.strip():
    raise RuntimeError("Empty response from Gemini")
  return text


# Visible batch-status lines living in the input file itself (plain text,
# deliberately free of '<' so the soup guard never trips on them). States:
# PENDING (queued) -> IN PROGRESS (being processed - steer clear) -> DONE.
# Rewritten on every run to reflect the current plan; stripped entirely on
# full success. The frontmatter ledger stays the machine-readable truth.
BATCH_LINE_RE = regex.compile(
  r"^@@GEMINI-BATCH\s+(\d+)/(\d+)\s+details\s+(\d+)-(\d+)\s+(PENDING|IN PROGRESS|DONE)@@\s*$",
  regex.MULTILINE,
)


def _make_batch_line(batch_num, nbatches, first, last, state):
  return f"@@GEMINI-BATCH {batch_num}/{nbatches} details {first}-{last} {state}@@"


def _flip_batch_line(file_in, batch_num, nbatches, first, last, old_state, new_state):
  """Best-effort status flip of one batch line (PENDING->IN PROGRESS).

  Pure string surgery on freshly re-read content; never touches details.
  Warns instead of failing if the line is gone (lines are expendable
  visibility; the ledger is the truth).
  """
  md_file = MdFile(file_in)
  metadata, content = md_file.read()
  old = _make_batch_line(batch_num, nbatches, first, last, old_state)
  new = _make_batch_line(batch_num, nbatches, first, last, new_state)
  if old not in content:
    logging.warning(f"Batch line for batch {batch_num} not found in {file_in}; skipping status flip.")
    return
  _dump_md_file_atomic(md_file, dict(metadata), content.replace(old, new, 1))


def _write_batch_checkpoint(file_in, detail_pattern, batch_num, nbatches, batch, outputs,
                            expected_titles, ledger_ranges, pattern_key, total, done_so_far):
  """Checkpoint one batch with read-modify-write, atomically.

  Re-reads the input file fresh (never trusting possibly-stale in-memory
  state), verifies the file still holds the same matched detail set with
  the batch's titles at their expected positions, applies this batch's
  outputs onto that fresh state, flips the batch's status line to DONE
  (stripping all status lines once done_so_far reaches total), and writes
  it back atomically with an updated batch ledger (likewise removed once
  done). Returns the written content. Raises without writing anything if
  the file changed underneath the run.
  """
  md_file = MdFile(file_in)
  metadata, content = md_file.read()
  soup = md_content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    raise RuntimeError(f"Could not re-parse {file_in} for checkpoint; refusing to overwrite.")
  fresh = []
  for tag in soup.find_all("details"):
    if tag.find_parent("details") is not None:
      continue
    summary = tag.select_one("summary")
    if summary is None:
      continue
    title = summary.text.strip()
    if detail_pattern is not None and not regex.search(detail_pattern, title):
      continue
    detail = details_helper.Detail.from_soup_tag(detail_tag=tag)
    if not detail.content.strip():
      continue
    fresh.append((tag, detail))
  if len(fresh) != total:
    raise RuntimeError(
      f"{file_in} changed during the run (matched {len(fresh)} details vs {total} "
      f"at start); refusing checkpoint to avoid misplacing outputs."
    )
  for index, _ in batch:
    if fresh[index - 1][1].title != expected_titles[index]:
      raise RuntimeError(
        f"{file_in} changed during the run (detail {index} is now "
        f"'{fresh[index - 1][1].title}', expected '{expected_titles[index]}'); "
        f"refusing checkpoint to avoid misplacing outputs."
      )
  for index, (tag, detail) in batch:
    details_helper.detail_content_replacer_soup(fresh[index - 1][0], outputs[index])
  new_content = md_content_processor._make_content_from_soup(soup=soup)
  first, last = batch[0][0], batch[-1][0]
  for old_state in ("IN PROGRESS", "PENDING"):
    old_line = _make_batch_line(batch_num, nbatches, first, last, old_state)
    if old_line in new_content:
      new_content = new_content.replace(
        old_line, _make_batch_line(batch_num, nbatches, first, last, "DONE"), 1)
      break
  else:
    logging.warning(f"Batch line for batch {batch_num} not found in {file_in}; skipping DONE flip.")
  if done_so_far >= total:
    new_content = regex.sub(r"\n{3,}", "\n\n", BATCH_LINE_RE.sub("", new_content))
    _dump_md_file_atomic(md_file, _without_details_progress(metadata), new_content)
  else:
    progress = _without_details_progress(metadata)
    progress["gemini_details_pattern"] = pattern_key
    progress["gemini_details_total"] = total
    progress["gemini_batches_done"] = [f"{a}-{b}" for a, b in ledger_ranges]
    _dump_md_file_atomic(md_file, progress, new_content)
  return new_content


def process_details(file_in, prompt, detail_pattern=None, max_chunk_chars=12000, model_id="gemini-3.5-flash", api_key_path="gemini.vv", dry_run=False, fallback_per_detail=True):
  """Process matching <details> blocks of a markdown file with Gemini, in place.

  Only top-level <details> blocks whose <summary> title matches
  detail_pattern (regex.search; None matches all details) are processed;
  everything else in the file is left untouched.

  For efficiency, matched detail contents are gathered into batches (each
  batch holding as many whole details as fit in max_chunk_chars, so batch
  boundaries always align with detail boundaries) and each batch goes to
  the model as a single chat message - no temp files, no chunk files, no
  external state of any kind. Details in a batch are separated by
  `<!-- GEMINI-DETAIL-SPLIT NNNN -->` marker lines which the model is
  instructed (via an appended prompt note) to reproduce exactly; the
  processed batch is split back on those markers and each output is
  placed into its own detail block.

  Some prompts (e.g. ones demanding bare output or stripping markup) make
  the model drop the markers. When a batch's markers don't survive and
  fallback_per_detail is True (default), that batch is automatically
  redone detail-by-detail with marker-free calls, which map 1:1 by
  construction; the raw mismatched output is saved to a debug file in the
  temp dir and its path logged. With fallback_per_detail=False a mismatch
  raises immediately.

  Progress is checkpointed to the input file after every batch: each
  checkpoint re-reads the file fresh, applies just that batch's outputs
  onto the current on-disk state (verifying the matched detail set and
  titles still line up, aborting otherwise), and writes atomically with an
  updated per-batch gemini_batches_done ledger like ["1-5", "6-11"] in
  frontmatter — so partial results are visible immediately, concurrent
  edits elsewhere survive, and a later run resumes after the completed
  prefix instead of redoing it. Every batch also gets a visible
  `@@GEMINI-BATCH k/N details a-b STATE@@` status line in the file itself
  (PENDING at plan time, IN PROGRESS while its call runs so readers steer
  clear, DONE after); all status lines are stripped on full success along
  with the ledger. With dry_run=True nothing is written. Returns the
  updated content.
  """
  file_in = _as_file_path(file_in)
  md_file = MdFile(file_in)
  metadata, content = md_file.read()

  soup = md_content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    logging.warning(f"Could not parse details in {file_in}; leaving file untouched.")
    return content

  matched = []
  for tag in soup.find_all("details"):
    if tag.find_parent("details") is not None:
      continue
    summary = tag.select_one("summary")
    if summary is None:
      logging.warning("Skipping <details> block without <summary>.")
      continue
    title = summary.text.strip()
    if detail_pattern is not None and not regex.search(detail_pattern, title):
      continue
    detail = details_helper.Detail.from_soup_tag(detail_tag=tag)
    if not detail.content.strip():
      logging.info(f"Skipping empty detail: {title}")
      continue
    matched.append((tag, detail))

  if not matched:
    logging.info(f"No details matching {detail_pattern!r} in {file_in}; nothing to do.")
    return content

  total = len(matched)
  logging.info(f"Processing {total} detail(s) matching {detail_pattern!r} in {file_in}.")

  # Resume from an earlier checkpoint (frontmatter batch ledger). Valid
  # only for the same pattern over an unchanged detail set; the completed
  # prefix is already processed in the file, so it is skipped.
  pattern_key = _normalize_detail_pattern(detail_pattern)
  start = 0
  ledger_ranges = []
  if "gemini_batches_done" in metadata or "gemini_details_done" in metadata:
    ledger = _parse_batches_ledger(metadata.get("gemini_batches_done"))
    if ledger is None:
      legacy_done = metadata.get("gemini_details_done", 0)
      if isinstance(legacy_done, bool):
        legacy_done = 0
      if isinstance(legacy_done, int) and 0 < legacy_done <= total:
        ledger = [(1, legacy_done)]
        logging.info(f"Migrating legacy progress count ({legacy_done}) to batch ledger.")
    if (
      ledger is not None
      and metadata.get("gemini_details_pattern", "") == pattern_key
      and metadata.get("gemini_details_total", 0) == total
    ):
      start = ledger[-1][1]
      ledger_ranges = list(ledger)
      logged_ranges = ", ".join(f"{a}-{b}" for a, b in ledger)
      logging.info(f"Resuming {file_in}: {start}/{total} details already processed (batches {logged_ranges}).")
    else:
      logging.warning(
        f"Ignoring stale progress record in {file_in} (pattern/total mismatch); "
        f"processing all {total} details fresh."
      )

  if start >= total:
    # Crash landed between the last checkpoint and the final cleanup write:
    # everything is processed, just drop the progress record.
    new_content = md_content_processor._make_content_from_soup(soup=soup)
    if not dry_run:
      _dump_md_file_atomic(md_file, _without_details_progress(metadata), new_content)
    return new_content

  for index, (tag, detail) in enumerate(matched[start:], start=start + 1):
    if DETAIL_SPLIT_MARKER_RE.search(detail.content):
      raise RuntimeError(
        f"Detail '{detail.title}' already contains a GEMINI-DETAIL-SPLIT marker; refusing to proceed."
      )

  # Group whole pending details into batches fitting max_chunk_chars so
  # that process_text_chunks never cuts a batch mid-marker. Global indices
  # are preserved for markers and numbering.
  expected_titles = {index: detail.title for index, (_, detail) in enumerate(matched, start=1)}
  pending = list(enumerate(matched, start=1))[start:]
  batches = []
  current_batch, current_len = [], 0
  for index, item in pending:
    piece = f"{_make_detail_split_marker(index)}\n\n{item[1].content.strip()}"
    if len(piece) > max_chunk_chars:
      if current_batch:
        batches.append(current_batch)
        current_batch, current_len = [], 0
      batches.append([(index, item)])
    elif current_batch and current_len + 2 + len(piece) > max_chunk_chars:
      batches.append(current_batch)
      current_batch, current_len = [(index, item)], len(piece)
    else:
      current_batch.append((index, item))
      current_len += (2 if current_len else 0) + len(piece)
  if current_batch:
    batches.append(current_batch)

  safe_base = regex.sub(r"[^A-Za-z0-9_.-]+", "_", os.path.basename(file_in))
  done_so_far = start
  new_content = None
  nbatches = len(batches)
  if not dry_run:
    # Make this run's plan visible in the file itself: one status line per
    # pending batch (stale lines were stripped pre-parse). No angle
    # brackets, so the soup guard never trips on them.
    for line_batch_num, line_batch in enumerate(batches, start=1):
      line_first, line_last = line_batch[0][0], line_batch[-1][0]
      line_batch[0][1][0].insert_before(
        "\n\n" + _make_batch_line(line_batch_num, nbatches, line_first, line_last, "PENDING") + "\n\n"
      )
    startup_metadata = dict(metadata) if start else _without_details_progress(metadata)
    _dump_md_file_atomic(
      md_file, startup_metadata, md_content_processor._make_content_from_soup(soup=soup))
  with tqdm(total=total, initial=start, desc="Processing Details", unit="detail") as pbar:
    for batch_num, batch in enumerate(batches, start=1):
      expected = [index for index, _ in batch]
      first, last = expected[0], expected[-1]
      batch_text = "\n\n".join(
        f"{_make_detail_split_marker(index)}\n\n{item[1].content.strip()}" for index, item in batch
      )
      batch_prompt = (
        f"{prompt}\n\nIMPORTANT: Lines of the form {_make_detail_split_marker(1)} "
        f"separate {len(batch)} independent passage(s). Reproduce each such separator line "
        f"EXACTLY as given, unmodified, in order. Only modify the text between them."
      )
      # Single message per batch, straight to the model: no chunk files, no
      # temp files of any kind.
      user_text = (
        "Process text chunk 1 of 1 according to the system instructions:\n\n" + batch_text
      )
      if not dry_run:
        # Mark IN PROGRESS before the long call so a reader knows to steer
        # clear; best-effort, the ledger stays the truth.
        try:
          _flip_batch_line(file_in, batch_num, nbatches, first, last, "PENDING", "IN PROGRESS")
        except Exception as e:
          logging.warning(f"Could not mark batch {batch_num} IN PROGRESS in {file_in} ({e}); continuing.")
      try:
        processed_batch = _generate_with_gemini(batch_prompt, user_text, model_id, api_key_path)

        try:
          outputs = _split_detail_batch(processed_batch, expected)
        except RuntimeError as e:
          debug_path = os.path.join(
            tempfile.gettempdir(), f"gemini_detail_batch_mismatch_{safe_base}_batch{batch_num}.md"
          )
          with open(debug_path, "w", encoding="utf-8") as f:
            f.write(processed_batch)
          if not fallback_per_detail:
            logging.error(f"Batch {batch_num}: {e}. Debug output saved at {debug_path}.")
            raise RuntimeError(f"Batch {batch_num}: {e}; leaving {file_in} untouched.") from e
          logging.warning(
            f"Batch {batch_num} (details {expected}): {e}. The model dropped/altered the "
            f"separator markers - raw batch output saved at {debug_path}. "
            f"Falling back to per-detail calls for this batch."
          )
          outputs = {}
          for index, item in batch:
            outputs[index] = _generate_with_gemini(
              prompt,
              "Process text chunk 1 of 1 according to the system instructions:\n\n"
              + item[1].content.strip(),
              model_id,
              api_key_path,
            ).strip()
        for index, (tag, detail) in batch:
          details_helper.detail_content_replacer_soup(tag, outputs[index])
        done_so_far += len(batch)
      except Exception as e:
        logging.error(
          f"Batch {batch_num}/{nbatches} failed ({e}). Progress checkpoint at "
          f"{done_so_far}/{total} details in {file_in}; re-run to resume."
        )
        raise

      # Checkpoint with read-modify-write: the outputs are applied onto
      # freshly re-read file state (never stale in-memory content) and
      # written atomically, so concurrent external edits to other parts
      # survive and mid-run file changes abort loudly instead of
      # misplacing outputs. The batch ledger stays in frontmatter until
      # full success.
      if dry_run:
        new_content = md_content_processor._make_content_from_soup(soup=soup)
      else:
        ledger_ranges.append((first, last))
        new_content = _write_batch_checkpoint(
          file_in, detail_pattern, batch_num, nbatches, batch, outputs, expected_titles,
          ledger_ranges, pattern_key, total, done_so_far,
        )
        if done_so_far >= total:
          logging.info(f"Finished {file_in}: all {total} details processed; progress record removed.")
        else:
          logged_ranges = ", ".join(f"{a}-{b}" for a, b in ledger_ranges)
          logging.info(f"Checkpoint {file_in}: batch {batch_num}/{nbatches} done ({done_so_far}/{total} details; batches {logged_ranges}).")
        pbar.set_postfix_str(f"batch {batch_num}/{nbatches}")
        pbar.update(len(batch))

  if new_content is None:
    new_content = md_content_processor._make_content_from_soup(soup=soup)
  return new_content







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


def _is_dead_credential_error(exc):
  """Detect deterministically-dead credentials (no retry or wait can help).

  E.g. 401 UNAUTHENTICATED "bound service account is deleted or disabled",
  400 API_KEY_INVALID, 403 PERMISSION_DENIED (key restrictions / API not
  enabled). These are per-key config states: ban the key and rotate.
  """
  code = getattr(exc, "code", None)
  if code in (401, 403):
    return True

  status = str(getattr(exc, "status", "") or "").upper()
  if status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
    return True

  text_lower = str(exc).lower()
  return (
      "api key not valid" in text_lower
      or "api_key_invalid" in text_lower
      or "account_state_invalid" in text_lower
      or "deleted or disabled" in text_lower
  )


def _comment_out_dead_keys(keys_file, table_path, key_names):
  """Comment out dead key lines under [table_path] as `#name = "..." DEAD`.

  Only touches uncommented `name = "secret"` lines in the target table;
  multiline values, tables and arrays are left alone. Writes atomically.
  Returns the names actually commented out.
  """
  with open(keys_file, "r", encoding="utf-8") as f:
    parts = f.read().split("\n")
  target = tuple(table_path.split("."))
  current = None
  pending = set(key_names)
  commented = []
  out = []
  for line in parts:
    header = regex.match(r"^[ \t]*\[([^\[\]]+)\][ \t]*$", line)
    if header:
      inner = header.group(1).strip()
      if len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in ("\"", "'"):
        current = (inner[1:-1],)
      else:
        current = tuple(part.strip() for part in inner.split("."))
      out.append(line)
      continue
    done = False
    if current == target and pending and not line.strip().startswith("#"):
      for key in sorted(pending):
        if not regex.match(r"^" + regex.escape(key) + r"\s*=\s*[\"']", line.strip()):
          continue
        if regex.match(r"^" + regex.escape(key) + r"""\s*=\s*(\"\"\"|''')""", line.strip()):
          continue
        new_line = "#" + line.strip()
        if not new_line.rstrip().endswith("DEAD"):
          new_line += " DEAD"
        out.append(new_line)
        pending.discard(key)
        commented.append(key)
        done = True
        break
    if not done:
      out.append(line)
  if not commented:
    return []
  tmp_path = str(keys_file) + ".tmp"
  with open(tmp_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
  os.replace(tmp_path, keys_file)
  return commented


def _report_dead_keys(keys_file, api_key_path, dead_found):
  """Comment dead keys out of the keys file and alert with an error message.

  No-op when no dead keys were found. Never raises (a reporting failure
  must not mask the run's own outcome).
  """
  if not dead_found:
    return
  try:
    commented = _comment_out_dead_keys(keys_file, api_key_path, dead_found)
  except Exception as edit_error:
    logging.warning(f"Could not comment out dead keys in {keys_file}: {edit_error}")
    commented = []
  skipped = [k for k in dead_found if k not in commented]
  message = (
    f"Dead Gemini API credentials detected under {api_key_path}: "
    f"{', '.join(dead_found)}. "
  )
  if commented:
    message += (
      f"Commented out in {keys_file} (marked DEAD, will be skipped from "
      f"now on): {', '.join(commented)}. Please replace them with fresh keys. "
    )
  if skipped:
    message += f"NOT commented out - edit {keys_file} manually: {', '.join(skipped)}. "
  logging.error(message.strip())


def _call_with_keys(
    func,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  keys_file = cred_path if cred_path is not None else _DEFAULT_TOKENS_PATH
  if cred_path is None:
    keys = list(creds.get_toml_value(api_key_path).keys())
  else:
    keys = list(creds.get_toml_value(api_key_path, cred_path).keys())

  if not keys:
    raise ValueError(f"No API keys found in {api_key_path}")

  i = random.randrange(len(keys))

  if max_attempts is None:
    max_attempts = len(keys)

  # Keys that hit quota exhaustion (429/RESOURCE_EXHAUSTED) or turn out
  # dead (401/403/auth failures) are banned for the rest of the run: their
  # quota won't recover mid-run and dead accounts won't revive, so never
  # rotate back into them.
  banned = set()
  dead_found = []

  for attempt in range(max_attempts):
    while keys[i % len(keys)] in banned:
      i += 1
      if len(banned) >= len(keys):
        _report_dead_keys(keys_file, api_key_path, dead_found)
        raise RuntimeError(
          f"All {len(keys)} API keys banned for rest of run: {sorted(banned)}"
        )
    key_name = keys[i % len(keys)]
    key = f"{api_key_path}.{key_name}"

    for transient_attempt in range(max_transient_retries + 1):
      try:
        logging.info("Cred %s", key)

        result = func(
          *args,
          api_key_path=key,
          **kwargs,
        )
        _report_dead_keys(keys_file, api_key_path, dead_found)
        return result

      except Exception as e:
        if _is_dead_credential_error(e):
          # Dead credential (deleted/disabled account, invalid key, ...):
          # waiting cannot help, so ban immediately and rotate without
          # sleeping.
          banned.add(key_name)
          if key_name not in dead_found:
            dead_found.append(key_name)
          logging.error(
            f"Cred {key} is dead, banning for rest of run and rotating: {e}",
          )
          if len(banned) >= len(keys):
            _report_dead_keys(keys_file, api_key_path, dead_found)
            raise RuntimeError(
              f"All {len(keys)} API keys dead/banned for rest of run: {sorted(banned)}"
            )
          break

        if not _is_retryable_gemini_error(e):
          _report_dead_keys(keys_file, api_key_path, dead_found)
          raise

        if _should_rotate_key(e):
          base_delay = min(2 ** attempt, 300)
          delay = _get_retry_delay(e, base_delay)
          banned.add(key_name)
          logging.warning(
            f"Cred {key} quota/rate-limit ({e}). "
            "Sleeping %.1fs, banning it for the rest of the run, and rotating.",
            delay,
          )
          time.sleep(delay)
          if len(banned) >= len(keys):
            _report_dead_keys(keys_file, api_key_path, dead_found)
            raise RuntimeError(
              f"All {len(keys)} API keys banned for rest of run: {sorted(banned)}"
            )
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

  _report_dead_keys(keys_file, api_key_path, dead_found)
  raise RuntimeError(
    f"Failed after {max_attempts} attempts across {len(keys)} API keys"
  )


def process_pdf_chunks_with_keys(
    file_in,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  return _call_with_keys(
    process_pdf_chunks,
    file_in,
    *args,
    api_key_path=api_key_path,
    cred_path=cred_path,
    max_attempts=max_attempts,
    max_transient_retries=max_transient_retries,
    **kwargs,
  )


def process_text_chunks_with_keys(
    file_in,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  return _call_with_keys(
    process_text_chunks,
    file_in,
    *args,
    api_key_path=api_key_path,
    cred_path=cred_path,
    max_attempts=max_attempts,
    max_transient_retries=max_transient_retries,
    **kwargs,
  )


def process_details_with_keys(
    file_in,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  return _call_with_keys(
    process_details,
    file_in,
    *args,
    api_key_path=api_key_path,
    cred_path=cred_path,
    max_attempts=max_attempts,
    max_transient_retries=max_transient_retries,
    **kwargs,
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
  # process_text_chunks_with_keys(file_in="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/lokAchArya-shAkhA/lokAchAryaH/shrI-vachana-bhUShaNam/vyAkhyA/mImAMsA/private/shrInivAsa-mahA-parakAla-yatiH.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md"))
  # process_details_with_keys(file_in="//home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/12k_vAdikesari-jIyar__36k_IDu_nam-piLLai_vaDakkut-tiru-vIdi-piLLai/sa_hi/01.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/bare-hyphenator.md"), detail_pattern="मूलम्.*|.+वतारिका - .+|टीका.+")
  # process_pdf_chunks_with_keys(file_in="/media/vvasuki/vData/text/granthasangrahaH/kAvyam/shrIvaiShNavakRtam/yatirAja-vijaya-nATakam.pdf", dest_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/rUpakam/naDAdUr-ghaTikA-shata-varadaH/yatirAja-vijaya-nATakam.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md"))