import logging

import regex
from doc_curation.utils import patterns
from indic_transliteration import sanscript


def _remap_source_matches(source_map, dest_matches):
  if len(dest_matches) != len(source_map):
    logging.info(f"Skipping re-indexing. Lengths do not match. {len(dest_matches)} != {len(source_map)}")
    return source_map

  source_match_map_new = {}
  successful_mappings = 0

  # Pair the destination matches directly with the source map's VALUES
  # This still assumes order, but makes it much more explicit.
  source_values = source_map.values()
  for dest_match, source_value in zip(dest_matches, source_values):
    index_str = sanscript.transliterate(dest_match.group(1), _to=sanscript.IAST)

    if not index_str.isnumeric():
      logging.warning("Could not get numeric index for: %s. Skipping this entry.", dest_match.group())
      continue  # Skip this specific entry, but don't discard the whole operation

    index = int(index_str)

    # Check for potential duplicate keys in the destination text
    if index in source_match_map_new:
      logging.warning("Duplicate index %d found in destination matches. Overwriting previous value.", index)

    source_match_map_new[index] = source_value
    successful_mappings += 1

  # A more intelligent final check
  if successful_mappings != len(source_map):
    logging.error("Re-indexing failed. The original map will be used.")
    return source_map

  logging.info("Successfully re-indexed %d out of %d entries.", successful_mappings, len(source_map))
  return source_match_map_new

def _denumerify(title):
  title = regex.sub(patterns.ALL_DIGITS, "", title)
  title = regex.sub("[ -]*$", "", title)
  return title

def _get_number(title):
  matches = regex.findall(f"{patterns.ALL_DIGITS}+", title)
  if len(matches) > 0:
    return matches[-1]
  else:
    return None

def _normalize_spaces(content):
  content = regex.sub(r"(?<=\n)(<\w+)", r"\n\n\1", content)
  content = regex.sub(r"\n *\n *\s+", "\n\n", content)
  return content


_DETAIL_TAG_RE = regex.compile(r"</details>|<details[^>]*>")
_SUMMARY_RE = regex.compile(r"<summary>(.*?)</summary>", flags=regex.DOTALL)


def get_top_level_detail_spans(content):
  """Return ``(start, end)`` spans of top-level ``<details>...</details>`` blocks."""
  spans = []
  depth = 0
  start = None
  for match in _DETAIL_TAG_RE.finditer(content or ""):
    if match.group().startswith("</"):
      if depth > 0:
        depth -= 1
        if depth == 0 and start is not None:
          spans.append((start, match.end()))
          start = None
    else:
      if depth == 0:
        start = match.start()
      depth += 1
  return spans


def parse_top_level_details(content):
  """Return ``[(start, end, title, body)]`` for top-level ``<details>`` blocks."""
  parsed = []
  for start, end in get_top_level_detail_spans(content):
    summary_match = _SUMMARY_RE.search(content[start:end])
    if summary_match is None:
      continue
    close = content.rfind("</details>", start, end)
    title = (summary_match.group(1) or "").strip()
    body = content[start + summary_match.end():close].strip()
    parsed.append((start, end, title, body))
  return parsed
