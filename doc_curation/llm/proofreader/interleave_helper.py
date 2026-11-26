"""Hybrid deterministic + LLM commentary & translation interleaver ("no retyping, ever").

Supports both:
1. **Zero-GPU local alignment (`backend=None`):** Uses ``interleave_aligner``'s
   sandhi-restored pratīka, headword, and stem-IDF Monotonic Viterbi DP solver.
2. **LLM + DP hybrid (`backend=ProofreaderBackend(...)`):** Enriches prompts with
   pre-computed pratīka/anchor & role cues + ``UPCOMING CORES`` lookahead, asks
   the LLM ONLY for 0-based JSON indices, and post-guards with ``refine_interleave_plan``.
"""
from __future__ import annotations

import json
import regex

from .interleave_aligner import align_commentary_segments, refine_interleave_plan
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
  cutting inside ``"..."``, ``“...”``, ``‘...’``, Sanskrit ``'...'``, ``(...)``,
  ``[...]``, or ``+++...+++`` editorial glosses."""
  if not text or not text.strip():
    return []
  segments: list[str] = []
  buf: list[str] = []
  paren_depth = 0
  in_dquote = False
  in_squote = False
  in_plus = False
  n = len(text)
  i = 0
  while i < n:
    if text[i:i + 3] == "+++":
      in_plus = not in_plus
      buf.append("+++")
      i += 3
      continue
    ch = text[i]
    buf.append(ch)
    if not in_plus:
      if ch == '"' and (i == 0 or text[i - 1] != "\\"):
        in_dquote = not in_dquote
      elif not in_dquote:
        if ch == "'" and not (i > 0 and text[i - 1].isascii() and text[i - 1].isalpha()):
          if in_squote or ("'" in text[i + 1:i + 140]):
            in_squote = not in_squote
        elif not in_squote:
          if ch in "([“‘":
            paren_depth += 1
          elif ch in ")]”’" and paren_depth > 0:
            paren_depth -= 1

    if not in_plus and not in_dquote and not in_squote and paren_depth == 0:
      if text[i:i + 2] == "\n\n":
        seg = "".join(buf).strip()
        if seg:
          segments.append(seg)
        buf = []
        while i + 1 < n and text[i + 1] in "\n\r ":
          i += 1
      elif ch in "।॥" or (ch in ".!?" and i + 1 < n and text[i + 1].isspace()):
        while i + 1 < n and text[i + 1] in "।॥०१२३४५६७८९0123456789*":
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
  """Convert ``[^32]`` to ``[32]`` inside ``<details>`` so renderers keep notes inline."""
  return regex.sub(r"\[\^([^\]]+)\]", r"[\1]", text)


def join_prose_segments(segments: list[str] | tuple[str, ...]) -> str:
  """Join prose segments using Markdown soft breaks (`  \\n`) after punctuation or spaces mid-sentence."""
  out: list[str] = []
  for seg in segments:
    s = seg.strip()
    if not s:
      continue
    if not out:
      out.append(s)
    elif regex.search(r"[।॥?!'’”\)]$", out[-1]):
      out.append(f"  \n{s}")
    else:
      out.append(f" {s}")
  return "".join(out)


def normalize_bhashya_prose(
  text: str,
  *,
  resolve_editorial_suggestions: bool = True,
  drop_line_pattern: regex.Pattern | str | None = None,
) -> str:
  """Remove fake blank-line paragraph breaks in commentary prose while preserving blockquotes.

  Reattaches trailing verse numbers (`॥  \\n१ ॥` -> `॥ १ ॥`), sanitizes inline
  footnotes inside details blocks, joins broken prose paragraphs via Markdown soft
  breaks (`  \\n`), and leaves ``>`` blockquotes and explicit topic openings separated.
  """
  if not text or not text.strip():
    return ""
  from doc_curation.sanskrit import fixer

  s = regex.sub(r"॥\s*\n+\s*([०-९0-9]+\s*॥)", r"॥ \1", text)
  if resolve_editorial_suggestions:
    s = fixer.resolve_suggestions(s)
  s = sanitize_details_footnotes(s)
  drop_re = regex.compile(drop_line_pattern) if isinstance(drop_line_pattern, str) else drop_line_pattern

  out_paras: list[str] = []
  for raw_p in regex.split(r"\n\s*\n+", s.strip()):
    p = raw_p.strip()
    if not p:
      continue
    lines = [ln.rstrip() for ln in p.splitlines() if ln.strip()]
    if drop_re is not None:
      lines = [ln for ln in lines if not drop_re.match(ln.lstrip("> "))]
    if not lines:
      continue
    first = lines[0]
    is_bq = all(ln.lstrip().startswith(">") for ln in lines)
    if out_paras:
      prev = out_paras[-1]
      prev_is_bq = all(ln.lstrip().startswith(">") for ln in prev.splitlines())
      if regex.match(r"^इति\s*[।॥]?\s*$", " ".join(lines)):
        if prev_is_bq:
          out_paras.append("  \n".join(lines))
        else:
          out_paras[-1] = prev.rstrip() + "  \n" + "  \n".join(lines)
        continue
      prev_last = prev.splitlines()[-1].rstrip()
      if (
        not is_bq
        and not prev_is_bq
        and not prev_last.endswith(("—", "–", ":"))
        and (
          not prev_last.endswith(("।", "॥", "?", "!", '"', "”", "’"))
          or regex.match(
            r"^(?:इति|ततः|तत्र|तथा|अथ|एवं|यथा|किञ्च|अतश्|यस्मात्|तस्मात्|अपि|च)(?=\s|$)",
            first,
          )
        )
        and not first.startswith(("कल्पः", "पाठ", "अथ ", ">"))
      ):
        sep = "\n" if prev_last.endswith("  ") else "  \n"
        out_paras[-1] = prev + sep + "  \n".join(lines)
        continue
    out_paras.append("  \n".join(lines))

  final_paras: list[str] = []
  for p in out_paras:
    lines = [ln.rstrip() for ln in p.splitlines() if ln.strip()]
    if len(lines) > 1:
      final_paras.append("\n".join([*(ln + "  " for ln in lines[:-1]), lines[-1]]))
    elif lines:
      final_paras.append(lines[0])
  return "\n\n".join(final_paras).strip()


_TM_WORDS_SECTION_RE = regex.compile(
  r"(TRANSLATION WORDS:\n)(.*?)(\n\n(?:UPCOMING CORES|Reply with ONLY this JSON))",
  flags=regex.DOTALL,
)


def annotate_translation_matcher_prompt(prompt_text: str) -> str:
  """Enrich a ``translation_matcher`` prompt with unambiguous ``[i]`` word indices,
  sentence-start line breaks, and pre-computed bilingual DP anchor hints."""
  if "TRANSLATION WORDS:\n" not in prompt_text or "TRANSLATION WORDS (pre-indexed" in prompt_text:
    return prompt_text
  from .translation_aligner import (
    align_cores_to_translation_dp,
    candidate_word_starts,
    parse_translation_matcher_prompt,
  )

  parsed = parse_translation_matcher_prompt(prompt_text)
  updated = regex.sub(
    r"The translation is one unsplit text — split it yourself by regex \\s[^\n]*",
    "Each translation word below is ALREADY pre-indexed with its exact 0-based tag "
    "[0], [1], ... — do NOT re-split or recount; copy the exact [i] integer standing "
    "immediately before the first word of each core's English rendering.",
    prompt_text,
    count=1,
  )

  def _repl(m: regex.Match) -> str:
    words = m.group(2).split()
    cands = candidate_word_starts(words)
    parts = []
    for idx, w in enumerate(words):
      sep = "\n" if idx > 0 and cands.get(idx, 0.0) >= 1.8 else (" " if idx > 0 else "")
      parts.append(f"{sep}[{idx}] {w}")
    hdr = (
      "TRANSLATION WORDS (pre-indexed 0-based [i] tags — use these [i] integers "
      "directly in \"starts\" and \"next_en\"):\n"
    )
    hint_block = ""
    if parsed and parsed["cores"]:
      dp = align_cores_to_translation_dp(
        parsed["cores"], words, c_start=parsed["c_start"], upcoming_cores=parsed["upcoming_cores"]
      )
      hint_block = (
        f"\n\nBILINGUAL ANCHOR PRIOR (heuristic starting estimate — refine semantically where needed):\n"
        f"{json.dumps(dp, ensure_ascii=False)}"
      )
    return hdr + "".join(parts) + hint_block + m.group(3)

  return _TM_WORDS_SECTION_RE.sub(_repl, updated, count=1)


def format_interleave_prompt(
  cores: list[str],
  segments: list[str],
  *,
  upcoming_cores: list[str] | None = None,
  author_label: str = "टीका",
  is_sarvash_tikah: bool = False,
  include_hints: bool = True,
) -> str:
  """Build the user prompt for JSON segment-to-core & role alignment, optionally
  enriched with sandhi-resolved pratīka/anchor cues and read-only ``upcoming_cores``."""
  core_lines = "\n".join(
    f"[CORE {idx}] {regex.sub(r'\\s+', ' ', c).strip()}" for idx, c in enumerate(cores)
  )
  upcoming = list(upcoming_cores or [])
  up_block = ""
  if upcoming:
    up_lines = "\n".join(
      f"[UPCOMING {idx}] {regex.sub(r'\\s+', ' ', c).strip()}" for idx, c in enumerate(upcoming)
    )
    up_block = (
      f"UPCOMING CORES (read-only lookahead — set unmatched_from at the first segment belonging to these):\n"
      f"{up_lines}\n\n"
    )

  hints_by_seg: dict[int, str] = {}
  if include_hints and cores and segments:
    dp = align_commentary_segments(
      cores, segments, upcoming_cores=upcoming, is_sarvash_tikah=is_sarvash_tikah
    )
    for h in dp["hints"]:
      if h["score"] >= 3.0 and h["witness"]:
        tag = f"{{cue: {h['best_target']} via '{h['witness'][:24]}', role={h['role_hint']}}} "
      else:
        tag = f"{{cue: cont, role={h['role_hint']}}} "
      hints_by_seg[h["seg"]] = tag

  seg_lines = "\n".join(
    f"[SEG {idx}] {hints_by_seg.get(idx, '')}{s}" for idx, s in enumerate(segments)
  )
  ctx = "sarvASh_TIkAH (intrinsic mantra-only file: no viniyoga blocks allowed inside)" if is_sarvash_tikah else "sarva-prastutiH"
  return (
    f"AUTHOR / SOURCE LABEL: {author_label}\n"
    f"TARGET FILE TYPE: {ctx}\n"
    f"TOTAL CORES: {len(cores)} (indices 0..{len(cores) - 1})\n"
    f"TOTAL SEGMENTS: {len(segments)} (indices 0..{len(segments) - 1})\n\n"
    f"CORE MULA BLOCKS:\n{core_lines}\n\n"
    f"{up_block}"
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


def summary_for_role(
  author_label: str,
  role: str,
  *,
  is_sanskrit_commentary: bool = True,
  role_labels: dict[str, str] | None = None,
) -> str:
  """Map ``(author_label, role)`` to canonical ``<summary>`` title per commentary_translation skill."""
  if role_labels and role in role_labels:
    return role_labels[role]
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
  role_labels: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
  """Insert verbatim source segments into clusters in canonical ``/commentary_translation`` order."""
  by_core: dict[int, dict[str, list[str]]] = {
    i: {r: [] for r in VALID_ROLES} for i in range(len(clusters))
  }
  for item in parsed_plan["assignments"]:
    seg_text = sanitize_details_footnotes(segments[item["seg"]])
    role = item["role"]
    if role != "heading":
      # Hoist any opening `**name॥**` line out of commentary block per skill rule
      hm = regex.match(r"^\*\*([^*।\n]+॥)\*\*\s*\n+(.+)$", seg_text, flags=regex.DOTALL)
      if hm:
        by_core[item["core"]]["heading"].append(hm.group(1))
        seg_text = hm.group(2).strip()
    if role == "translation" and by_core[item["core"]]["viniyoga"]:
      seg_text = regex.sub(r"\s*\[P[0-9.]*\]", "", seg_text)
    by_core[item["core"]][role].append(seg_text)

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
        lbl = summary_for_role(
          author_label, role_top, is_sanskrit_commentary=is_sanskrit_commentary, role_labels=role_labels
        )
        blk = f"<details><summary>{lbl}</summary>\n\n" + "\n\n".join(bucket[role_top]) + "\n</details>"
        if is_sarvash_tikah and role_top == "viniyoga":
          withheld_host_blocks.append(blk)
        else:
          parts.append(blk)

    if cl.get("vp"):
      vp_str = cl["vp"].strip()
      if bucket["heading"] and parts and parts[-1].startswith("### "):
        parts[-1] = f"{parts[-1]}\n{vp_str}"  # No blank line between hoisted ### and विश्वास-प्रस्तुतिः
      else:
        parts.append(vp_str)

    for role_mid in ("translation", "note"):
      if bucket[role_mid]:
        lbl = summary_for_role(author_label, role_mid, is_sanskrit_commentary=False, role_labels=role_labels)
        parts.append(f"<details><summary>{lbl}</summary>\n\n" + "\n\n".join(bucket[role_mid]) + "\n</details>")

    parts.append(cl["mula"].strip())
    if cl.get("post"):
      parts.append(cl["post"].strip())

    for role_bot in ("tika", "viniyoga_sangraha"):
      if bucket[role_bot]:
        lbl = summary_for_role(
          author_label, role_bot, is_sanskrit_commentary=is_sanskrit_commentary, role_labels=role_labels
        )
        parts.append(f"<details><summary>{lbl}</summary>\n\n" + "\n\n".join(bucket[role_bot]) + "\n</details>")

    out_clusters.append("\n\n".join(p for p in parts if p))

  assembled = "\n\n".join(out_clusters)
  if assembled.count("<details") != assembled.count("</details>"):
    raise RuntimeError("Unbalanced <details> tags after interleaving assembly")
  return assembled, withheld_host_blocks


_DETAIL_SPAN_RE = regex.compile(
  r"<details(?P<attrs>[^>]*)><summary>(?P<title>.*?)</summary>(?P<body>.*?)</details>",
  flags=regex.DOTALL,
)


def parse_markdown_clusters(md_text: str) -> tuple[str, list[dict[str, str]], str, list[str]]:
  """Parse host Markdown into ``(preamble, clusters, postamble, core_mula_bodies)``."""
  matches = list(_DETAIL_SPAN_RE.finditer(md_text or ""))
  mula_indices = [i for i, m in enumerate(matches) if m.group("title").strip().startswith("मूलम्")]
  if not mula_indices:
    return md_text, [], "", []

  # Group each मूलम् with its preceding विश्वास-प्रस्तुतिः/viniyoga/translation and following tika
  first_start = matches[0].start()
  preamble = md_text[:first_start]
  clusters: list[dict[str, str]] = []
  mula_bodies: list[str] = []

  def _is_upper_layer(title: str) -> bool:
    t = title.strip()
    return (
      t.startswith("विश्वास-प्रस्तुतिः")
      or t.endswith(("विनियोगः", "अवतारिका", "- Note"))
      or not any(k in t for k in ("टीका", "भाष्य", "प्रकाशिका", "पद-पाठः", "विनियोगसङ्ग्रहः"))
    )

  # Partition matches around each मूलम्
  group_starts = [0]
  for k in range(len(mula_indices) - 1):
    mi = mula_indices[k]
    nxt_mi = mula_indices[k + 1]
    split_at = nxt_mi
    for j in range(mi + 1, nxt_mi):
      between_txt = md_text[matches[j - 1].end():matches[j].start()]
      if regex.search(r"(?m)^#{1,6}\s+\S", between_txt) or _is_upper_layer(matches[j].group("title")):
        split_at = j
        break
    group_starts.append(split_at)
  group_starts.append(len(matches))

  for k, mi in enumerate(mula_indices):
    g0, g1 = group_starts[k], group_starts[k + 1]
    pre_lead = md_text[matches[g0 - 1].end():matches[g0].start()].strip() if g0 > 0 else ""
    vp_idx = next(
      (j for j in range(g0, mi) if matches[j].group("title").strip().startswith("विश्वास-प्रस्तुतिः")),
      None,
    )
    if vp_idx is not None:
      pre_end = matches[vp_idx].start()
      pre_part = (
        (pre_lead + "\n\n" if pre_lead else "") + md_text[matches[g0].start():pre_end].strip()
      ).strip() if vp_idx > g0 else pre_lead
      vp_and_mid = md_text[matches[vp_idx].start():matches[mi].start()].strip()
    else:
      pre_part = (
        (pre_lead + "\n\n" if pre_lead else "") + md_text[matches[g0].start():matches[mi].start()].strip()
      ).strip() if mi > g0 else pre_lead
      vp_and_mid = ""

    mula_raw = md_text[matches[mi].start():matches[mi].end()]
    post_part = md_text[matches[mi].end():matches[g1 - 1].end()].strip() if g1 - 1 > mi else ""
    clusters.append({"pre": pre_part, "vp": vp_and_mid, "mula": mula_raw, "post": post_part})
    mula_bodies.append(matches[mi].group("body").strip())

  postamble = md_text[matches[-1].end():]
  return preamble, clusters, postamble, mula_bodies


def verify_interleaved_markdown(
  assembled_md: str,
  placed_segments: list[str],
  *,
  withheld_blocks: list[str] | None = None,
  is_sarvash_tikah: bool = False,
) -> dict:
  """Run the ``/commentary_translation`` 6-point verification checklist programmatically."""
  norm = lambda s: regex.sub(r"[\s>*#]+", "", sanitize_details_footnotes(s))
  norm_page = norm(assembled_md + "\n" + "\n".join(withheld_blocks or ()))
  missing = []
  for idx, seg in enumerate(placed_segments):
    probe = regex.sub(r"\[P[0-9.]*\]", "", seg)
    probe_n = regex.sub(r"[॥।*]+$", "", norm(probe))
    if probe_n and probe_n not in norm_page:
      missing.append({"seg": idx, "head": seg[:80]})

  open_count = assembled_md.count("<details")
  close_count = assembled_md.count("</details>")
  closed_vp = bool(regex.search(r"<details>\s*<summary>विश्वास-प्रस्तुतिः", assembled_md))
  illegal_viniyoga = bool(
    is_sarvash_tikah and regex.search(r"<summary>[^<]*विनियोगः</summary>", assembled_md)
  )
  empty_blocks = bool(regex.search(r"<details[^>]*><summary>[^<]*</summary>\s*</details>", assembled_md))
  bold_edge = False
  for m in _DETAIL_SPAN_RE.finditer(assembled_md):
    t = m.group("title").strip()
    b = m.group("body").strip()
    if any(k in t for k in ("टीका", "भाष्य", "प्रकाशिका")):
      if regex.match(r"^\*\*[^*\n]+॥\*\*", b) or regex.search(r"\*\*[^*\n]+॥\*\*\s*$", b):
        bold_edge = True

  ok = (
    not missing
    and open_count == close_count
    and not closed_vp
    and not illegal_viniyoga
    and not empty_blocks
    and not bold_edge
  )
  return {
    "ok": ok,
    "missing": missing,
    "details_balanced": open_count == close_count,
    "all_vp_open": not closed_vp,
    "sarvash_tikah_clean": not illegal_viniyoga,
    "no_empty_blocks": not empty_blocks,
    "no_bold_edge_headings": not bold_edge,
  }


def interleave_source_into_markdown(
  host_md: str,
  source_text: str,
  *,
  author_label: str = "टीका",
  is_sanskrit_commentary: bool = True,
  is_sarvash_tikah: bool = False,
  backend=None,
  batch_cores: int = 4,
  role_labels: dict[str, str] | None = None,
) -> dict:
  """Interleave ``source_text`` into ``host_md`` verbatim using local DP or LLM+DP."""
  preamble, clusters, postamble, mula_bodies = parse_markdown_clusters(host_md)
  segments = split_quote_safe_segments(source_text)
  if not clusters or not segments:
    return {
      "markdown": host_md,
      "withheld_viniyogas": [],
      "unmatched_segments": segments,
      "verification": verify_interleaved_markdown(host_md, [], is_sarvash_tikah=is_sarvash_tikah),
    }

  seg_cursor = 0
  global_assignments: list[dict] = []
  n_cores = len(clusters)
  n_segs = len(segments)
  eff_batch = n_cores if backend is None else max(1, batch_cores)

  for c_start in range(0, n_cores, eff_batch):
    if seg_cursor >= n_segs:
      break
    c_end = min(n_cores, c_start + eff_batch)
    batch_mulas = mula_bodies[c_start:c_end]
    upcoming_mulas = mula_bodies[c_end:c_end + 2]
    max_win = n_segs - seg_cursor if c_end == n_cores else min(n_segs - seg_cursor, max(12, (c_end - c_start) * 5))
    win_segs = segments[seg_cursor:seg_cursor + max_win]

    if backend is None:
      plan = align_commentary_segments(
        batch_mulas, win_segs, upcoming_cores=upcoming_mulas, is_sarvash_tikah=is_sarvash_tikah
      )
    else:
      prompt = format_interleave_prompt(
        batch_mulas,
        win_segs,
        upcoming_cores=upcoming_mulas,
        author_label=author_label,
        is_sarvash_tikah=is_sarvash_tikah,
        include_hints=True,
      )
      raw_json = backend.new_chat(INTERLEAVER_SYSTEM_PROMPT).send_text(prompt)
      raw_plan = parse_interleave_json(raw_json, num_cores=len(batch_mulas), num_segments=len(win_segs))
      plan = refine_interleave_plan(
        raw_plan, batch_mulas, win_segs, upcoming_cores=upcoming_mulas, is_sarvash_tikah=is_sarvash_tikah
      )

    for a in plan["assignments"]:
      global_assignments.append({
        "seg": seg_cursor + a["seg"],
        "core": c_start + a["core"],
        "role": a["role"],
      })
    seg_cursor += plan["unmatched_from"]

  merged_plan = {"assignments": global_assignments, "unmatched_from": seg_cursor}
  assembled_body, withheld = assemble_cluster_blocks(
    clusters,
    segments,
    merged_plan,
    author_label=author_label,
    is_sanskrit_commentary=is_sanskrit_commentary,
    is_sarvash_tikah=is_sarvash_tikah,
    role_labels=role_labels,
  )
  full_md = (preamble.rstrip() + "\n\n" if preamble.strip() else preamble) + assembled_body + (
    "\n\n" + postamble.lstrip() if postamble.strip() else "\n"
  )
  ver = verify_interleaved_markdown(
    full_md, segments[:seg_cursor], withheld_blocks=withheld, is_sarvash_tikah=is_sarvash_tikah
  )
  return {
    "markdown": full_md,
    "withheld_viniyogas": withheld,
    "unmatched_segments": segments[seg_cursor:],
    "verification": ver,
  }
