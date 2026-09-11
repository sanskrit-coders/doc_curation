"""Plain-text chunk processing with Gemini (in-place)."""
import logging
import os

import regex
from google.genai import types
from tqdm import tqdm

from doc_curation.md.file import MdFile

from .keys import get_client


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


def _dump_md_file_atomic(md_file, metadata, content):
  """Write an md file atomically (temp + rename) so a crash can't corrupt it."""
  tmp_path = md_file.file_path + ".tmp"
  tmp_md = MdFile(tmp_path, frontmatter_type=md_file.frontmatter_type)
  tmp_md.dump_to_file(metadata=dict(metadata), content=content, dry_run=False, silent=True)
  os.replace(tmp_path, md_file.file_path)


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
