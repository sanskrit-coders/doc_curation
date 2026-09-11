"""Per-<details>-block processing with Gemini (in-place)."""
import logging
import os
import tempfile

import regex
from google.genai import types
from tqdm import tqdm

from doc_curation.md import content_processor as md_content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile

from .keys import get_client
from .text_chunker import _as_file_path, _dump_md_file_atomic


DETAIL_SPLIT_MARKER_RE = regex.compile(r"<!--\s*GEMINI-DETAIL-SPLIT\s+(\d+)\s*-->")


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
