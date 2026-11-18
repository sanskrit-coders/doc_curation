"""LLM-assisted commentary & translation interleaving without retyping source text.

Implements the ``/interleaver`` skill's strict "no retyping, ever" invariant:
1. For plain core↔translation streams, delegates directly to
   ``doc_curation.llm.translation_matcher`` using ``backend.generate_content``.
2. For multi-role Sanskrit commentaries & Vedic/śāstric translations (where
   segments must be classified into ``viniyoga``, ``avatarika``, ``translation``,
   ``tika``, ``note``, ``viniyoga_sangraha``, or ``heading`` and placed in canonical
   order around ``विश्वास-प्रस्तुतिः`` and ``मूलम्``), slices the source quote-safely,
   asks the LLM ONLY for JSON segment-to-core & role assignments, and reassembles
   verbatim text in Python.
"""
from __future__ import annotations

import json
import regex

from .prompts import INTERLEAVER_SYSTEM_PROMPT

VALID_ROLES = frozenset({
  "viniyoga",
  "avatarika",
  "translation",
  "tika",
  "note",
  "viniyoga_sangraha",
  "heading",
})


def split_quote_safe_segments(text: str) -> list[str]:
  """Split commentary/translation text into sentence/paragraph segments without
  cutting inside quotes (``"..."``, ``“...”``, ``'...'``) or parentheses ``(...)``."""
  if not text or not text.strip():
    return []
  segments: list[str] = []
  buf: list[str] = []
  paren_depth = 0
  in_dquote = False
  n = len(text)
  i = 0
  while i < n:
    ch = text[i]
    buf.append(ch)
    if ch == '"' and (i == 0 or text[i - 1] != "\\"):
      in_dquote = not in_dquote
    elif not in_dquote:
      if ch in "([“":
        paren_depth += 1
      elif ch in ")]”" and paren_depth > 0:
        paren_depth -= 1

    # Check sentence/paragraph boundary outside quotes & parens
    if not in_dquote and paren_depth == 0:
      if text[i:i + 2] == "\n\n":
        seg = "".join(buf).strip()
        if seg:
          segments.append(seg)
        buf = []
        while i + 1 < n and text[i + 1] in "\n\r ":
          i += 1
      elif ch in "।॥" or (ch in ".!?" and i + 1 < n and text[i + 1].isspace()):
        # Absorb doubled danda ॥ or trailing digits/spaces on same danda
        while i + 1 < n and text[i + 1] in "।॥०१२३४५६७८९0123456789":
          i += 1
          buf.append(text[i])
        seg = "".join(buf).strip()
        if seg:
          segments.append(seg)
        buf = []
    i += 1

  tail = "".join(buf).strip()
  if tail:
    segments.append(tail)
  return segments


def sanitize_details_footnotes(text: str) -> str:
  """Convert ``[^32]`` to ``[32]`` inside ``<details>`` so Hugo/Markdown renderers
  keep notes inline inside the details block instead of hoisting them to page end."""
  return regex.sub(r"\[\^([^\]]+)\]", r"[\1]", text)


_TM_WORDS_SECTION_RE = regex.compile(
  r"(TRANSLATION WORDS:\n)(.*?)(\n\n(?:UPCOMING CORES|Reply with ONLY this JSON))",
  flags=regex.DOTALL,
)


def annotate_translation_matcher_prompt(prompt_text: str) -> str:
  """Prefix each whitespace-delimited word in ``TRANSLATION WORDS:`` with its exact
  0-based index ``[i]`` so a non-thinking LLM can read exact ``starts`` / ``next_en``
  indices directly instead of mentally counting 150+ unnumbered words."""
  if "TRANSLATION WORDS:\n" not in prompt_text or "[0] " in prompt_text:
    return prompt_text

  def _repl(m: regex.Match) -> str:
    words = m.group(2).split()
    numbered = " ".join(f"[{idx}] {w}" for idx, w in enumerate(words))
    hdr = (
      "TRANSLATION WORDS (each whitespace-split string is prefixed with its exact "
      "0-based index [i] — use these [i] integers directly in \"starts\" and \"next_en\"):\n"
    )
    return hdr + numbered + m.group(3)

  return _TM_WORDS_SECTION_RE.sub(_repl, prompt_text, count=1)


def format_interleave_prompt(
  cores: list[str],
  segments: list[str],
  *,
  author_label: str = "टीका",
  is_sarvash_tikah: bool = False,
) -> str:
  """Build the user prompt for JSON segment-to-core & role alignment."""
  core_lines = "\n".join(
    f"[CORE {idx}] { regex.sub(r'\\s+', ' ', c).strip() }"
    for idx, c in enumerate(cores)
  )
  seg_lines = "\n".join(
    f"[SEG {idx}] {s}" for idx, s in enumerate(segments)
  )
  ctx = "sarvASh_TIkAH (intrinsic mantra-only file: no viniyoga blocks allowed inside)" if is_sarvash_tikah else "sarva-prastutiH"
  return (
    f"AUTHOR / SOURCE LABEL: {author_label}\n"
    f"TARGET FILE TYPE: {ctx}\n"
    f"TOTAL CORES: {len(cores)} (indices 0..{len(cores) - 1})\n"
    f"TOTAL SEGMENTS: {len(segments)} (indices 0..{len(segments) - 1})\n\n"
    f"CORE MULA BLOCKS:\n{core_lines}\n\n"
    f"SOURCE SEGMENTS:\n{seg_lines}"
  )


def parse_interleave_json(raw_reply: str, num_cores: int, num_segments: int) -> dict:
  """Parse and validate LLM JSON reply for commentary/translation interleaving."""
  cleaned = regex.sub(r"^\s*<think>.*?</think>\s*", "", raw_reply or "", flags=regex.DOTALL)
  cleaned = regex.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", cleaned.strip())
  data = json.loads(cleaned)
  assignments = data.get("assignments", [])
  unmatched_from = int(data.get("unmatched_from", num_segments))
  if not (0 <= unmatched_from <= num_segments):
    raise ValueError(f"unmatched_from={unmatched_from} out of [0, {num_segments}]")

  validated = []
  seen_segs = set()
  for item in assignments:
    seg_idx = int(item["seg"])
    core_idx = int(item["core"])
    role = str(item["role"]).strip()
    if not (0 <= seg_idx < unmatched_from):
      raise ValueError(f"seg={seg_idx} out of [0, {unmatched_from})")
    if seg_idx in seen_segs:
      raise ValueError(f"duplicate seg={seg_idx}")
    if not (0 <= core_idx < num_cores):
      raise ValueError(f"core={core_idx} out of [0, {num_cores})")
    if role not in VALID_ROLES:
      raise ValueError(f"invalid role={role!r}")
    seen_segs.add(seg_idx)
    validated.append({"seg": seg_idx, "core": core_idx, "role": role})

  return {"assignments": sorted(validated, key=lambda x: x["seg"]), "unmatched_from": unmatched_from}


def summary_for_role(author_label: str, role: str, *, is_sanskrit_commentary: bool = True) -> str:
  """Map ``(author_label, role)`` to canonical ``<summary>`` title per interleaver skill."""
  base = regex.sub(r"-(?:टीका|भाष्यम्)$", "", author_label).strip()
  if role == "viniyoga":
    if base in ("भट्टभास्करः", "भट्टभास्कर"):
      return "भास्करोक्त-विनियोगः"
    if base in ("सायणः", "सायण"):
      return "सायणोक्त-विनियोगः"
    return f"{base} - विनियोगः"
  if role == "avatarika":
    return f"{base} - अवतारिका"
  if role == "note":
    return f"{base} - Note"
  if role == "viniyoga_sangraha":
    return "विनियोगसङ्ग्रहः"
  if role == "translation":
    return base
  # Default: tika
  if is_sanskrit_commentary and not author_label.endswith(("टीका", "भाष्यम्", "प्रस्तुतिः", "टिप्पनी", "प्रकाशिका", "(सं)")):
    return f"{base.rstrip('ः')}-टीका"
  return author_label


def assemble_cluster_blocks(
  clusters: list[dict[str, str]],
  segments: list[str],
  parsed_plan: dict,
  *,
  author_label: str = "टीका",
  is_sanskrit_commentary: bool = True,
  is_sarvash_tikah: bool = False,
) -> tuple[str, list[str]]:
  """Insert verbatim source segments into clusters in canonical order.

  Each input item in ``clusters`` is ``{"pre": str, "vp": str, "mula": str, "post": str}``
  holding verbatim ``<details>`` strings. Returns ``(assembled_markdown, host_only_blocks)``
  where ``host_only_blocks`` collects any ``*विनियोगः`` blocks withheld when
  ``is_sarvash_tikah=True`` (so callers can place them in the ``sarva-prastutiH`` host).
  """
  by_core: dict[int, dict[str, list[str]]] = {
    i: {r: [] for r in VALID_ROLES} for i in range(len(clusters))
  }
  for item in parsed_plan["assignments"]:
    seg_text = sanitize_details_footnotes(segments[item["seg"]])
    by_core[item["core"]][item["role"]].append(seg_text)

  out_clusters: list[str] = []
  withheld_host_blocks: list[str] = []

  for idx, cl in enumerate(clusters):
    bucket = by_core[idx]
    parts: list[str] = []
    if cl.get("pre"):
      parts.append(cl["pre"].strip())

    for h in bucket["heading"]:
      h_clean = regex.sub(r"^[#*>\s]+|[॥।\s*]+$", "", h).strip()
      if h_clean:
        parts.append(f"### {h_clean}")

    for role_top in ("viniyoga", "avatarika"):
      if bucket[role_top]:
        lbl = summary_for_role(author_label, role_top, is_sanskrit_commentary=is_sanskrit_commentary)
        blk = f"<details><summary>{lbl}</summary>\n\n" + "\n\n".join(bucket[role_top]) + "\n</details>"
        if is_sarvash_tikah and role_top == "viniyoga":
          withheld_host_blocks.append(blk)
        else:
          parts.append(blk)

    if cl.get("vp"):
      parts.append(cl["vp"].strip())

    for role_mid in ("translation", "note"):
      if bucket[role_mid]:
        lbl = summary_for_role(author_label, role_mid, is_sanskrit_commentary=False)
        parts.append(f"<details><summary>{lbl}</summary>\n\n" + "\n\n".join(bucket[role_mid]) + "\n</details>")

    parts.append(cl["mula"].strip())

    if cl.get("post"):
      parts.append(cl["post"].strip())

    for role_bot in ("tika", "viniyoga_sangraha"):
      if bucket[role_bot]:
        lbl = summary_for_role(author_label, role_bot, is_sanskrit_commentary=is_sanskrit_commentary)
        parts.append(f"<details><summary>{lbl}</summary>\n\n" + "\n\n".join(bucket[role_bot]) + "\n</details>")

    out_clusters.append("\n\n".join(p for p in parts if p))

  assembled = "\n\n".join(out_clusters)
  # Structural sanity check: details tags must stay balanced
  if assembled.count("<details") != assembled.count("</details>"):
    raise RuntimeError("Unbalanced <details> tags after interleaving assembly")
  return assembled, withheld_host_blocks
