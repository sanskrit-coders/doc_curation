"""IAST Sanskrit hyphenation, validation, and dictionary-patching utilities.

Reuses the Devanāgarī sandhi-preservation and inline merger-veto checks from
:mod:`doc_curation.llm.proofreader.guards` via canonical IAST-to-Devanāgarī
round-tripping.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
import difflib
import regex
from indic_transliteration import sanscript

from doc_curation.llm.proofreader.guards import (
  canonical_sandhi_skeleton,
  forward_fuse_candidates,
  rejoin_merger_violations,
)

_PROTECTED_RE = regex.compile(
  r"<details(?:\s+open)?\s*>\s*<summary>\s*मूलम्[^<]*</summary>.*?</details>"
  r"|\[\[[^\]]+\]\]"
  r"|\[\^[^\]\n]+\]"
  r"|https?://\S+"
  r"|<[^>]+>",
  flags=regex.DOTALL,
)
_IAST_CHAR_RE = regex.compile(r"[āīūṛṝḷḹṅñṭḍṇśṣṃṁḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢṂṀḤ]")
_IAST_HYPHEN_TOKEN_RE = regex.compile(
  r"[A-Za-zĀāĪīŪūṚṛṜṝḶḷḸḹṂṃṀṁḤḥṄṅÑñṬṭḌḍṆṇŚśṢṣ]+"
  r"(?:-[A-Za-zĀāĪīŪūṚṛṜṝḶḷḸḹṂṃṀṁḤḥṄṅÑñṬṭḌḍṆṇŚśṢṣ]+)+"
)
_ENGLISH_DERIV_SUFFIX_RE = regex.compile(
  r"(?:ism|ist|ists|ic|ics|ical|ically|ian|ians|ize|izes|ized|ise|ises|ised"
  r"|ization|isation|ity|ities|ness|hood|ship|less|ful|ly|dom|'s|’s)$",
  flags=regex.IGNORECASE,
)
_EDGE_PUNCT_RE = regex.compile(r"^([*\"'‘“(-]*)(.+?)([*\"'’”.,;:!?)/-]*)$")

DEFAULT_HYBRID_ENGLISH_SUFFIXES: tuple[str, ...] = (
  "-worship",
  "-worshippers",
  "-cult",
  "-cults",
  "-theory",
  "-legend",
  "-legends",
  "-doctrine",
  "-system",
  "-literature",
  "-text",
  "-texts",
  "-religion",
  "-tradition",
  "-hymn",
  "-hymns",
  "-god",
  "-gods",
  "-deity",
  "-deities",
  "-concept",
  "-idea",
  "-period",
  "-age",
  "-school",
  "-schools",
  "-sect",
  "-sects",
  "-element",
  "-ritual",
  "-sacrifice",
  "-myth",
  "-mythology",
  "-philosophy",
  "-conception",
  "-view",
  "-principle",
  "-process",
  "-stage",
  "-aspect",
  "-factor",
  "-feature",
  "-image",
  "-images",
  "-episode",
  "-episodes",
  "-ideology",
  "-ideologies",
)


def _split_edge_punctuation(token: str) -> tuple[str, str, str] | None:
  """Split leading/trailing Markdown or prose punctuation from a token."""
  m = _EDGE_PUNCT_RE.match(token)
  if not m:
    return None
  return m.group(1), m.group(2), m.group(3)


def iast_to_devanagari(text: str) -> str:
  """Transliterate IAST text to lowercased Devanāgarī for sandhi checking."""
  cleaned = text.replace("ṁ", "ṃ").replace("Ṁ", "Ṃ").replace("’", "'")
  return sanscript.transliterate(cleaned.lower(), sanscript.IAST, sanscript.DEVANAGARI)


def has_iast_merger_violation(unsplit_iast: str, split_iast: str) -> bool:
  """Return True if an inline IAST split violates dīrgha/guṇa/vṛddhi merger veto."""
  old_dev = iast_to_devanagari(unsplit_iast)
  new_dev = iast_to_devanagari(split_iast)
  return rejoin_merger_violations(old_dev, new_dev) != new_dev


def mask_iast_protected_spans(
  text: str,
  *,
  sentinel_prefix: str = "§§P",
  sentinel_suffix: str = "§§",
) -> tuple[str, dict[str, str]]:
  """Replace brackets, footnote markers, URLs, and tags with sentinels."""
  masks: dict[str, str] = {}

  def _repl(m: regex.Match) -> str:
    key = f"{sentinel_prefix}{len(masks):04d}{sentinel_suffix}"
    masks[key] = m.group(0)
    return key

  return _PROTECTED_RE.sub(_repl, text), masks


def restore_iast_protected_spans(text: str, masks: Mapping[str, str]) -> str:
  """Restore spans previously masked by :func:`mask_iast_protected_spans`."""
  out = text
  for key, orig in masks.items():
    out = out.replace(key, orig)
  return out


def is_valid_iast_hyphen_edit(
  old_span: str,
  new_span: str,
  *,
  require_iast_diacritic: bool = True,
) -> bool:
  """Validate an IAST hyphenation or sandhi-separation edit.

  Rejects silent lexical edits, casing changes, non-Sanskrit English-suffixed
  derivatives, and inline ``dīrgha``/``guṇa``/``vṛddhi`` merger-veto violations.
  Set ``require_iast_diacritic=False`` only for caller-curated pure-ASCII Sanskrit
  maps (e.g. ``karmayoga -> karma-yoga``).
  """
  if old_span == new_span:
    return True
  forbidden = ("\n", "[", "]", "`", "*")
  if any(c in new_span for c in forbidden) or any(c in old_span for c in forbidden):
    return False
  if require_iast_diacritic and not _IAST_CHAR_RE.search(old_span):
    return False
  for word in old_span.split():
    stem = word.strip(".,;:!?\"'()—–-")
    if "-" not in stem and _ENGLISH_DERIV_SUFFIX_RE.search(stem):
      return False

  old_letters = regex.sub(r"[\s\-–—]+", "", old_span)
  new_letters = regex.sub(r"[\s\-–—]+", "", new_span)
  if not old_letters or not new_letters:
    return False
  if old_letters == new_letters:
    return not has_iast_merger_violation(old_span, new_span)

  if old_letters[0].isupper() != new_letters[0].isupper():
    return False
  old_dev = iast_to_devanagari(old_span)
  new_dev = iast_to_devanagari(new_span)
  if canonical_sandhi_skeleton(old_dev) != canonical_sandhi_skeleton(new_dev):
    return False
  return rejoin_merger_violations(old_dev, new_dev) == new_dev


def build_validated_iast_map(
  raw_map: Mapping[str, str],
  *,
  excluded_tokens: Iterable[str] = (),
  expand_case_variants: bool = True,
  require_iast_diacritic: bool = False,
) -> dict[str, str]:
  """Filter an IAST hyphenation dictionary through sandhi and merger-veto checks."""
  excluded = set(excluded_tokens)
  validated: dict[str, str] = {}
  for src, dst in raw_map.items():
    if src in excluded or src == dst:
      continue
    if is_valid_iast_hyphen_edit(src, dst, require_iast_diacritic=require_iast_diacritic):
      validated.setdefault(src, dst)

  if not expand_case_variants:
    return validated

  extra: dict[str, str] = {}
  for src, dst in list(validated.items()):
    variants = (
      (src.lower(), dst.lower()),
      (src[:1].upper() + src[1:].lower(), dst[:1].upper() + dst[1:].lower()),
    )
    for k_var, v_var in variants:
      if (
        k_var not in excluded
        and k_var not in validated
        and is_valid_iast_hyphen_edit(k_var, v_var, require_iast_diacritic=require_iast_diacritic)
      ):
        extra[k_var] = v_var
  validated.update(extra)
  return validated


def apply_iast_hyphenation_map(
  text: str,
  hyphen_map: Mapping[str, str],
) -> tuple[str, list[tuple[str, str]]]:
  """Apply a vetted IAST hyphenation map safely while preserving protected spans.

  Masks ``[[...]]``, ``[^...]``, URLs, and HTML/मूलम् tags with a Private-Use-Area
  sentinel so compound tokens immediately preceding footnotes or attached via ``-``
  or em-dashes ``—`` are hyphenated without corrupting surrounding markup.
  """
  if not text or not hyphen_map:
    return text, []
  masked, masks = mask_iast_protected_spans(text, sentinel_prefix="\ue000P", sentinel_suffix="\ue000")
  chunks = regex.findall(r"\ue000P\d{4}\ue000|[^\s—\ue000]+|\s+|—", masked)
  out_chunks: list[str] = []
  changes: list[tuple[str, str]] = []

  for chunk in chunks:
    if chunk.isspace() or chunk == "—" or chunk.startswith("\ue000P"):
      out_chunks.append(chunk)
      continue
    split = _split_edge_punctuation(chunk)
    if not split:
      out_chunks.append(chunk)
      continue
    pre, core, suf = split
    if core in hyphen_map and hyphen_map[core] != core:
      repl = hyphen_map[core]
      out_chunks.append(f"{pre}{repl}{suf}")
      changes.append((core, repl))
    elif "-" in core:
      parts = core.split("-")
      new_parts: list[str] = []
      changed = False
      for part in parts:
        if part in hyphen_map and hyphen_map[part] != part:
          repl = hyphen_map[part]
          new_parts.append(repl)
          changes.append((part, repl))
          changed = True
        else:
          new_parts.append(part)
      out_chunks.append(f"{pre}{'-'.join(new_parts)}{suf}" if changed else chunk)
    else:
      out_chunks.append(chunk)

  return restore_iast_protected_spans("".join(out_chunks), masks), changes


def reconcile_iast_hyphenation(
  orig_text: str,
  cand_text: str,
) -> tuple[str, list[tuple[str, str]]]:
  """Accept only validated IAST hyphenation/sandhi edits from an LLM candidate string."""
  orig_masked, orig_masks = mask_iast_protected_spans(orig_text)
  if set(orig_masks.keys()) - set(regex.findall(r"§§P\d{4}§§", cand_text)):
    return orig_text, []

  o_toks = regex.findall(r"\S+|\s+", orig_masked)
  c_toks = regex.findall(r"\S+|\s+", cand_text)
  sm = difflib.SequenceMatcher(a=o_toks, b=c_toks, autojunk=False)
  out_toks: list[str] = []
  changes: list[tuple[str, str]] = []

  for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
      out_toks.extend(o_toks[i1:i2])
      continue
    o_span = "".join(o_toks[i1:i2])
    c_span = "".join(c_toks[j1:j2])
    if tag == "replace":
      s_o = _split_edge_punctuation(o_span)
      s_c = _split_edge_punctuation(c_span)
      if s_o and s_c and s_o[0] == s_c[0] and s_o[2] == s_c[2]:
        core_o, core_c = s_o[1], s_c[1]
        if is_valid_iast_hyphen_edit(core_o, core_c):
          out_toks.append(c_span)
          if core_o != core_c:
            changes.append((core_o, core_c))
          continue
    out_toks.extend(o_toks[i1:i2])

  return restore_iast_protected_spans("".join(out_toks), orig_masks), changes


def _token_has_merger_violation(token: str, raw_dev_compact: str | None = None) -> str | None:
  """Return rejoined Devanāgarī form if a hyphenated IAST token violates vowel-merger veto."""
  new_dev = iast_to_devanagari(token)
  parts = new_dev.split("-")
  for idx in range(len(parts) - 1):
    left, right = parts[idx], parts[idx + 1]
    if not left or not right or right[0] not in "अआइईउऊऋॠएऐओऔ":
      continue
    pair = f"{left}-{right}"
    if raw_dev_compact is not None:
      if pair in raw_dev_compact:
        continue
      rejoined = rejoin_merger_violations(raw_dev_compact, pair)
      if rejoined != pair:
        return rejoined
      continue
    # Standalone mode: exclude unmerged hiatus skeleton so only fused sandhi forms trigger.
    fused_only = [
      c for c in forward_fuse_candidates(left, right)
      if c != canonical_sandhi_skeleton(left + " " + right)
    ]
    if not fused_only:
      continue
    rejoined = rejoin_merger_violations(" ".join(fused_only), pair)
    if rejoined != pair:
      return rejoined
  return None


def find_iast_merger_violations(
  text: str,
  *,
  raw_text: str | None = None,
  require_iast_or_italic: bool = True,
  excluded_hybrid_suffixes: Iterable[str] = DEFAULT_HYBRID_ENGLISH_SUFFIXES,
) -> list[tuple[str, str]]:
  """Return ``(token, rejoined_devanagari)`` for hyphenated IAST tokens breaking merger veto.

  When ``raw_text`` is given, compares against the pre-hyphenation baseline so
  pre-existing bibliographic hyphens (e.g. ``Taittirīya-Upaniṣad``) are ignored and
  only newly introduced inline merger splits are flagged. Otherwise checks all vowel
  seams via forward sandhi candidates. When ``require_iast_or_italic`` is True, inspects
  tokens with IAST diacritics or enclosed in ``*italics*``.
  """
  suffixes = tuple(excluded_hybrid_suffixes)
  masked, _ = mask_iast_protected_spans(text)
  raw_dev_compact = regex.sub(r"\s+", "", iast_to_devanagari(mask_iast_protected_spans(raw_text)[0])) if raw_text else None
  italic_spans = [(m.start(), m.end()) for m in regex.finditer(r"\*[^*\n]+\*", masked)]
  violations: list[tuple[str, str]] = []
  for match in _IAST_HYPHEN_TOKEN_RE.finditer(masked):
    token = match.group(0)
    if suffixes and token.lower().endswith(suffixes):
      continue
    if require_iast_or_italic and not _IAST_CHAR_RE.search(token):
      if not any(s <= match.start() and match.end() <= e for s, e in italic_spans):
        continue
    rejoined = _token_has_merger_violation(token, raw_dev_compact=raw_dev_compact)
    if rejoined is not None:
      violations.append((token, rejoined))
  return violations
