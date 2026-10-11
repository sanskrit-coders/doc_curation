"""Sequential matching of dangling footnote definitions with references.

Covers files (typically merged commentary chapters) carrying footnote
definitions outside their using block: dumped at the end of the file,
stranded in wrapper gaps (inside सर्वाष् but outside any content
sub-block), or split across chapter files. Ids may restart per verse;
matching is purely positional: maximum-cardinality non-crossing
(monotone) same-id pairing between references (in document order) and
definitions (in document order), ties broken by minimum displacement.
Star markers (`[*]`, `[^*]`, solitary bare `* ` lines) pair strictly in
order in their own lane. No text-similarity heuristics: sandhi and short
verse-line references make term overlap useless and even misleading here.

Reuses REF_PATTERN / Footnote from :mod:`helper`.
"""

import regex

DEF_LINE_RE = regex.compile(r"^(\[\^?[^\]\n:]+\]):(.*)$")
BRACKET_REF_RE = regex.compile(r"\[(\^?[^\]\n:]+?)\](?!:)")
PLAIN_NUM_RE = regex.compile(r"[०-९\d]+(?:\s*,\s*[०-९\d]+)*")
VERSE_NUM_RE = regex.compile(r"॥[^॥\n]*॥")
OPEN_RE = regex.compile(r"<details[^>]*>")
CLOSE_RE = regex.compile(r"</details>")
SUMMARY_RE = regex.compile(r"<summary>(.*?)</summary>", regex.DOTALL)


def key_of(raw_id):
  return raw_id.lstrip("^").strip()


def parse_details(text):
  """Return list of blocks: dict(open, inner, close, close_end, summary)."""
  events = [(m.start(), m.end(), "open") for m in OPEN_RE.finditer(text)]
  events += [(m.start(), m.end(), "close") for m in CLOSE_RE.finditer(text)]
  events.sort()
  stack, blocks = [], []
  for s, e, kind in events:
    if kind == "open":
      stack.append((s, e))
    elif stack:
      o, oe = stack.pop()
      m = SUMMARY_RE.search(text, oe, e)
      blocks.append({"open": o, "inner": e, "close": s, "close_end": e,
                     "summary": m.group(1).strip() if m else ""})
  return blocks


def line_depths(text, blocks):
  opens = sorted(b["open"] for b in blocks)
  closes = sorted(b["close"] for b in blocks)
  import bisect
  depths, off = [], 0
  for line in text.splitlines(keepends=True):
    # Clamped: stray closes must not push later lines negative (which
    # would hide bare defs from the pool).
    depths.append(max(0, bisect.bisect_right(opens, off) - bisect.bisect_right(closes, off)))
    off += len(line)
  return depths


def innermost_block(blocks, pos):
  cands = [b for b in blocks if b["open"] <= pos < b["close_end"]]
  return min(cands, key=lambda b: b["close_end"] - b["open"]) if cands else None


def own_para(text, pos):
  s = text.rfind("\n\n", 0, pos) + 2
  if s < 2 and not text.startswith("\n\n"):
    s = 0
  e = text.find("\n\n", pos)
  e = len(text) if e < 0 else e
  while s < e and text[s] == "\n":
    s += 1
  while e > s and text[e - 1] == "\n":
    e -= 1
  return s, e


def _masked(text):
  return VERSE_NUM_RE.sub(lambda m: " " * len(m.group(0)), text)


def collect_refs(text, blocks, depths, misc_summaries=("Misc",)):
  masked = _masked(text)
  lines = text.splitlines(keepends=True)
  offs, off = [], 0
  for ln in lines:
    offs.append(off)
    off += len(ln)
  bare_spans, inside_spans = [], []

  def in_span(spans, p):
    return any(s <= p < e for s, e in spans)

  refs = []
  for i, ln in enumerate(lines):
    ls = offs[i]
    if DEF_LINE_RE.match(ln):
      continue
    for m in BRACKET_REF_RE.finditer(masked[ls:ls + len(ln)]):
      p = ls + m.start()
      blk = innermost_block(blocks, p)
      ps, pe = own_para(text, p)
      refs.append({"pos": p, "id": m.group(1), "key": key_of(m.group(1)),
                   "kind": "bracket", "para": (ps, pe), "block": blk})
    blk_here = innermost_block(blocks, ls)
    if blk_here and any(s in (blk_here["summary"] or "") for s in misc_summaries):
      for m in PLAIN_NUM_RE.finditer(masked[ls:ls + len(ln)]):
        a, b = ls + m.start(), ls + m.end()
        if a > 0 and masked[a - 1] == "[":
          continue
        if b < len(masked) and masked[b] == "]":
          continue
        before = masked[max(0, a - 2):a]
        after = masked[b:b + 1]
        if "_" not in before and after != "_":
          continue
        ps, pe = own_para(text, a)
        for num in regex.split(r"\s*,\s*", m.group(0)):
          refs.append({"pos": a, "id": num, "key": key_of(num),
                       "kind": "plain", "para": (ps, pe), "block": blk_here})
  refs.sort(key=lambda r: r["pos"])
  return refs, bare_spans, inside_spans


INLINE_DEF_RE = regex.compile(r"\[(\^?[^\]\n:]+)\]:")


def is_star_key(key):
  return key == "*"


def _split_inline_defs(line_start, line_text):
  """Split '[१]:.. [२]:..' run-on definition lines (cf. helper's
  split_clean_definition_group). Returns list of (pos, id, text) or None
  when the line is not splittable (pieces too short to be real defs)."""
  marks = list(INLINE_DEF_RE.finditer(line_text))
  if len(marks) < 2:
    return None
  parts = []
  for k, m in enumerate(marks):
    end = marks[k + 1].start() if k + 1 < len(marks) else len(line_text)
    body = line_text[m.end():end].strip()
    if len(regex.sub(r"[\s\-–—:;,.\|]+", "", body)) < 4:
      return None
    parts.append((line_start + m.start(), m.group(1), body))
  return parts


STAR_BARE_RE = regex.compile(r"^\* (\S.*)$")
LIST_MARKER_RE = regex.compile(r"^(\* |\- |\+ |\d+[.)] )")


def _is_wrapper_gap(blocks, offs_pos):
  blk = innermost_block(blocks, offs_pos)
  return blk is not None and "सर्वाष्" in (blk["summary"] or "")


def _solitary_star(lines, i):
  """A `* `-line counts as a footnote candidate only when solitary:
  substantive on its own and not one bullet in a list run."""
  body = STAR_BARE_RE.match(lines[i])
  if not body:
    return False
  if len(regex.sub(r"\s+", "", body.group(1))) < 8:
    return False
  n = len(lines)
  j = i - 1
  while j >= 0 and not lines[j].strip():
    j -= 1
  if j >= 0 and LIST_MARKER_RE.match(lines[j].lstrip()):
    return False
  j = i + 1
  while j < n and not lines[j].strip():
    j += 1
  if j < n and LIST_MARKER_RE.match(lines[j].lstrip()):
    return False
  return True


def _def_start(lines, i, depths, blocks, offs, pool):
  """(id, key) if lines[i] opens a pool definition, else None.

  pool "bare": depth-0 lines. pool "gap": lines stranded in wrapper gaps
  (inside a सर्वाष् wrapper but outside any content sub-block).
  Besides `[id]:` lines this also accepts solitary `* ` lines (key `*`).
  """
  m = DEF_LINE_RE.match(lines[i])
  if m and (i == 0 or not lines[i - 1].strip()):
    if pool == "bare" and depths[i] == 0:
      return m.group(1)[1:-1]
    if pool == "gap" and depths[i] >= 1 and _is_wrapper_gap(blocks, offs[i]):
      return m.group(1)[1:-1]
    return None
  if (STAR_BARE_RE.match(lines[i]) and (i == 0 or not lines[i - 1].strip())
      and _solitary_star(lines, i)):
    if pool == "bare" and depths[i] == 0:
      return "*"
    if pool == "gap" and depths[i] >= 1 and _is_wrapper_gap(blocks, offs[i]):
      return "*"
  return None


def _collect_pool_defs(text, blocks, depths, pool):
  lines = text.splitlines(keepends=True)
  offs, off = [], 0
  for ln in lines:
    offs.append(off)
    off += len(ln)
  defs, i, n = [], 0, len(lines)
  while i < n:
    did = _def_start(lines, i, depths, blocks, offs, pool)
    if did is None:
      i += 1
      continue
    start = offs[i]
    j = i + 1
    while j < n:
      if not lines[j].strip():
        j += 1
        continue
      s = lines[j].lstrip()
      if DEF_LINE_RE.match(lines[j]) or STAR_BARE_RE.match(lines[j]):
        break
      if s.startswith(("<", "#")) or s.startswith(("---", "+++")):
        break
      while j < n and lines[j].strip():
        j += 1
    end = offs[j] if j < n else len(text)
    split = _split_inline_defs(start, lines[i])
    if split is not None:
      for k, (ppos, pid, _pbody) in enumerate(split):
        if k + 1 < len(split):
          pend = split[k + 1][0]
          ptext = text[ppos:pend].strip()
        else:
          pend = end
          ptext = text[ppos:end].strip("\n")
        defs.append({"pos": ppos, "end": pend, "id": pid,
                     "key": key_of(pid), "text": ptext})
      i = j
      continue
    raw = text[start:end]
    defs.append({"pos": start, "end": end, "id": did,
                 "key": key_of(did), "text": raw.strip("\n")})
    i = j
  return defs


def collect_bare_defs(text, depths):
  """Bare (depth-0) def lines grouped with following non-structural paras."""
  return _collect_pool_defs(text, None, depths, "bare")


def collect_gap_defs(text, blocks, depths):
  """Defs stranded in wrapper gaps (inside सर्वाष्, outside sub-blocks)."""
  return _collect_pool_defs(text, blocks, depths, "gap")


def collect_inside_defs(text, blocks, depths):
  lines = text.splitlines(keepends=True)
  offs, off = [], 0
  for ln in lines:
    offs.append(off)
    off += len(ln)
  defs = []
  for i, ln in enumerate(lines):
    m = DEF_LINE_RE.match(ln)
    if not (m and depths[i] >= 1 and (i == 0 or not lines[i - 1].strip())):
      continue
    if _is_wrapper_gap(blocks, offs[i]):
      continue  # stranded gap def: pool material, not a placed rival
    ps, pe = own_para(text, offs[i])
    blk = innermost_block(blocks, offs[i])
    if blk is not None and pe > blk["close"]:
      pe = blk["close"]
      while pe > ps and text[pe - 1] == "\n":
        pe -= 1
    defs.append({"pos": offs[i], "end": pe, "id": m.group(1)[1:-1],
                 "key": key_of(m.group(1)[1:-1]), "text": text[ps:pe],
                 "block": blk})
  return defs


def monotone_match(refs, defs):
  """Max-cardinality non-crossing same-id pairing; ties -> min displacement.

  Returns (ri, di) list. The secondary objective matters: e.g. when early
  references (whose defs sit misplaced inside later blocks) compete with
  later references for the same early defs, both options may pair equally
  many items, but only the local (small-displacement) choice keeps every
  verse's notes with its own verse.
  """
  m, n = len(refs), len(defs)
  dp = [[(0, 0)] * (n + 1) for _ in range(m + 1)]
  for i in range(m - 1, -1, -1):
    for j in range(n - 1, -1, -1):
      best = dp[i + 1][j] if dp[i + 1][j] >= dp[i][j + 1] else dp[i][j + 1]
      if refs[i]["key"] == defs[j]["key"]:
        c, negd = dp[i + 1][j + 1]
        pair = (c + 1, negd - abs(refs[i]["pos"] - defs[j]["pos"]))
        if pair >= best:
          best = pair
      dp[i][j] = best
  pairs, i, j = [], 0, 0
  while i < m and j < n:
    if refs[i]["key"] == defs[j]["key"]:
      c, negd = dp[i + 1][j + 1]
      if (c + 1, negd - abs(refs[i]["pos"] - defs[j]["pos"])) == dp[i][j]:
        pairs.append((i, j))
        i += 1
        j += 1
        continue
    if dp[i + 1][j] >= dp[i][j + 1]:
      i += 1
    else:
      j += 1
  return pairs


def match_dangling_footnotes_sequentially(content, misc_summaries=("Misc",),
                                            allow_relocate=True,
                                            skip_bare=()):
  """Move bare footnote defs into the blocks referencing them, sequentially.

  Returns (new_content, report). Never invents pairings: only exact same-id
  monotone matches are applied; everything else is reported.

  If allow_relocate is False, a bare definition competing with an
  already-placed same-id definition is left in place and reported as a
  collision instead of evicting the placed one.

  skip_bare: bare-definition file offsets to exclude from the pool (left
  untouched). Used when specific pairings were manually judged wrong.

  Fixpoint guarantee: when edits were made, the result is re-analysed; if
  a further round still wants changes (fragmentary landscape where
  leftovers would keep shoehorning onto starving refs), the edits are
  discarded and the original content is returned with an 'unstable' note.
  The tool therefore never leaves a file in a state that degrades on
  re-run.
  """
  # Star lane first: anonymous markers pair strictly in order in their own
  # lane, so numbered notes can neither starve nor steal them.
  mid, rep_star = match_dangling_star_footnotes(content)
  new_content, report = _match_once(mid, misc_summaries=misc_summaries,
                                    allow_relocate=allow_relocate,
                                    skip_bare=skip_bare)
  for key in report:
    report[key] = rep_star[key] + report[key]
  if new_content == content:
    if report["placed"]:
      # Moves netted to zero: defs already sat adjacent to use
      # (Bhagavatam-style inline runs). Say so honestly.
      report["notes"].append(
        f"{len(report['placed'])} defs already adjacent to use; left as-is")
      report["placed"] = []
    return new_content, report
  sim1, _ = match_dangling_star_footnotes(new_content)
  check, _ = _match_once(sim1, misc_summaries=misc_summaries,
                         allow_relocate=allow_relocate, skip_bare=())
  if check != new_content:
    report["notes"].append(
      "unstable landscape: leftovers would keep shoehorning onto "
      "starving refs on re-runs; left untouched")
    return content, report
  return new_content, report


def _match_once(content, misc_summaries=("Misc",), allow_relocate=True,
                skip_bare=()):
  report = {"placed": [], "relocated": [], "duplicates_dropped": [],
            "shared": [], "unmatched_refs": [], "unmatched_defs": [],
            "notes": []}
  blocks = parse_details(content)
  depths = line_depths(content, blocks)
  refs, _, _ = collect_refs(content, blocks, depths, misc_summaries)
  bare_all = collect_bare_defs(content, depths) + collect_gap_defs(content, blocks, depths)
  bare_all.sort(key=lambda d: d["pos"])
  bare = [d for d in bare_all if not is_star_key(d["key"]) and d["pos"] not in skip_bare]
  skipped = [d for d in bare_all if not is_star_key(d["key"]) and d["pos"] in skip_bare]
  if not bare:
    # Star defs (if any) are the star lane's domain; it runs before this.
    return content, report
  inside = collect_inside_defs(content, blocks, depths)

  def_spans = [(d["pos"], d["end"]) for d in bare_all]
  def_spans += [(d["pos"], d["end"]) for d in inside]
  refs = [r for r in refs
          if not is_star_key(r["key"])
          and not any(s <= r["pos"] < e for s, e in def_spans)]
  if not refs:
    report["notes"].append("no references found; bare defs left untouched")
    for d in bare:
      report["unmatched_defs"].append(d["id"])
    return content, report

  inside_by_block_id = {}
  for d in inside:
    if d["block"] is not None:
      inside_by_block_id.setdefault((id(d["block"]), d["key"]), []).append(d)

  pairs = monotone_match(refs, bare)
  matched_refs = {ri for ri, _ in pairs}
  matched_bare = {di for _, di in pairs}

  moves = []  # (bare_def, ref, rival_inside_def or None)
  evictions = {}
  blocked = set()
  dropped = []
  for ri, di in pairs:
    r, d = refs[ri], bare[di]
    rivals = inside_by_block_id.get((id(r["block"]), r["key"]), []) if r["block"] else []
    if rivals:
      same = [x for x in rivals if x["text"].strip() == d["text"].strip()]
      if same:
        report["duplicates_dropped"].append(f"{d['id']} @{d['pos']}")
        dropped.append(d)
        blocked.add((ri, di))
        continue
      ev = rivals[0]
      moves.append((d, r, ev))
      evictions[id(ev)] = ev
    else:
      moves.append((d, r, None))

  # Evicted defs need a home: an unmatched, currently unsatisfied same-id
  # ref. Requiring unsatisfied homes forbids eviction chains and swap churn
  # (a satisfied home would only displace another placed definition).
  # If there is no such home, the inside definition stays and the bare
  # match dissolves.
  ref_home = {}
  for ri, r in enumerate(refs):
    if ri not in matched_refs:
      rivals = inside_by_block_id.get((id(r["block"]), r["key"]), []) if r["block"] else []
      if not rivals:
        ref_home.setdefault(r["key"], []).append((ri, r))
  final_moves, evicted_ok = [], {}
  for d, r, ev in moves:
    if ev is not None:
      if not allow_relocate:
        report["notes"].append(
          f"collision: bare {d['id']} @{d['pos']} vs placed same-id "
          f"@{ev['pos']}; both left")
        for ri2, di2 in pairs:
          if refs[ri2] is r and bare[di2] is d:
            matched_refs.discard(ri2)
            matched_bare.discard(di2)
        continue
      homes = ref_home.get(ev["key"], [])
      if not homes:
        report["notes"].append(
          f"keep misplaced {ev['id']} in place (no sequential home); "
          f"bare {d['id']} @{d['pos']} left")
        for ri2, di2 in pairs:
          if refs[ri2] is r and bare[di2] is d:
            matched_refs.discard(ri2)
            matched_bare.discard(di2)
        continue
      hri, hr = homes.pop(0)
      matched_refs.add(hri)
      evicted_ok[id(ev)] = (ev, hr)
    final_moves.append((d, r))

  for eid, (ev, hr) in evicted_ok.items():
    report["relocated"].append(f"{ev['id']} -> ref @{hr['pos']} ({hr['kind']})")

  placed_blocks = {}
  for d, r in final_moves:
    placed_blocks.setdefault((id(r["block"]), r["key"]), []).append(d)
    report["placed"].append(f"{d['id']} @{d['pos']} -> ref @{r['pos']} ({r['kind']})")

  for ri, r in enumerate(refs):
    if ri not in matched_refs:
      key = (id(r["block"]), r["key"])
      if key in inside_by_block_id or key in placed_blocks:
        report["shared"].append(f"{r['id']} @{r['pos']}")
      else:
        report["unmatched_refs"].append(f"{r['id']} @{r['pos']} ({r['kind']})")
  consumed = {id(d) for d, _ in final_moves} | {id(d) for d in dropped}
  for d in bare:
    if id(d) not in consumed:
      report["unmatched_defs"].append(f"{d['id']} @{d['pos']}")
  for d in skipped:
    report["unmatched_defs"].append(f"{d['id']} @{d['pos']} (skipped)")

  if not final_moves and not evicted_ok and not dropped:
    return content, report

  edits = []
  for d in dropped:
    edits.append((d["pos"], d["end"], ""))
  for d, r in final_moves:
    edits.append((d["pos"], d["end"], ""))
    if r["block"] is not None:
      ce = r["block"]["close"]
      edits.append((ce, ce, "\n\n" + d["text"] + "\n"))
    else:
      ps, pe = r["para"]
      edits.append((pe, pe, "\n\n" + d["text"]))
  for _, (ev, hr) in evicted_ok.items():
    edits.append((ev["pos"], ev["end"], ""))
    if hr["block"] is not None:
      ce = hr["block"]["close"]
      edits.append((ce, ce, "\n\n" + ev["text"] + "\n"))
    else:
      _, pe = hr["para"]
      edits.append((pe, pe, "\n\n" + ev["text"]))

  edits.sort()
  for k in range(len(edits) - 1):
    assert edits[k][1] <= edits[k + 1][0], f"overlapping edits: {edits[k]} {edits[k+1]}"
  return _apply_edits(content, edits), report


def _apply_edits(content, edits):
  out, cur = [], 0
  for s, e, rep in sorted(edits):
    out.append(content[cur:s])
    out.append(rep)
    cur = max(cur, e)
  out.append(content[cur:])
  return regex.sub(r"\n\n\n+", "\n\n", "".join(out))


def _star_marker(ref_id):
  return "[^*]" if ref_id.startswith("^") else "[*]"


def _star_normalize(def_text, ref_id):
  marker = _star_marker(ref_id) + ":"
  out = regex.sub(r"^\[[^\]\n]*\]:", marker, def_text, count=1)
  if out == def_text:
    # Bare-`*` style ("* ..."): give it the explicit footnote form.
    out = regex.sub(r"^\* ", marker + " ", def_text, count=1)
  return out


def _star_body(def_text):
  out = regex.sub(r"^\[[^\]\n]*\]:", "", def_text).strip()
  if out == def_text.strip():
    out = regex.sub(r"^\* ", "", def_text).strip()
  return out


def match_dangling_star_footnotes(content):
  """Pair anonymous `[*]` / `[^*]` refs with same-mark defs, strictly in order.

  Star markers carry no identity, so first ref pairs with first def and so
  on, in a lane independent of numbered notes (sharing the pool lets the
  displacement tie-break sacrifice star pairs). A moved definition adopts
  its ref's marker style (`[*]` vs `[^*]`). Rivals already inside the
  target block are never evicted: identical bodies are dropped as
  duplicates, anything else is reported as a collision and left alone.
  Returns (new_content, report).
  """
  new_content, report = _star_once(content)
  if new_content == content:
    return new_content, report
  check, _ = _star_once(new_content)
  if check != new_content:
    report["notes"].append("unstable star landscape; left untouched")
    return content, report
  return new_content, report


def _star_once(content):
  report = {"placed": [], "relocated": [], "duplicates_dropped": [],
            "shared": [], "unmatched_refs": [], "unmatched_defs": [],
            "notes": []}
  blocks = parse_details(content)
  depths = line_depths(content, blocks)
  refs, _, _ = collect_refs(content, blocks, depths)
  bare = collect_bare_defs(content, depths) + collect_gap_defs(content, blocks, depths)
  bare.sort(key=lambda d: d["pos"])
  inside = collect_inside_defs(content, blocks, depths)
  def_spans = [(d["pos"], d["end"]) for d in bare]
  def_spans += [(d["pos"], d["end"]) for d in inside]
  refs = [r for r in refs if is_star_key(r["key"])
          and not any(s <= r["pos"] < e for s, e in def_spans)]
  bare = [d for d in bare if is_star_key(d["key"])]
  inside = [d for d in inside if is_star_key(d["key"])]
  if not bare:
    return content, report
  inside_by_block = {}
  for d in inside:
    if d["block"] is not None:
      inside_by_block.setdefault(id(d["block"]), []).append(d)
  moves, dropped = [], []
  n_pairs = min(len(refs), len(bare))
  for k in range(n_pairs):
    r, d = refs[k], bare[k]
    rivals = inside_by_block.get(id(r["block"]), []) if r["block"] else []
    if rivals and any(_star_body(x["text"]) == _star_body(d["text"]) for x in rivals):
      report["duplicates_dropped"].append(f"* @{d['pos']}")
      report["shared"].append(f"* @{r['pos']}")
      dropped.append(d)
      continue
    if rivals:
      report["notes"].append(
        f"collision: bare * @{d['pos']} vs placed same-mark "
        f"@{rivals[0]['pos']}; both left")
      report["shared"].append(f"* @{r['pos']}")
      continue
    place_text = _star_normalize(d["text"], r["id"])
    moves.append((d, r, place_text))
    report["placed"].append(f"* @{d['pos']} -> ref @{r['pos']} ({r['kind']})")
  for r in refs[n_pairs:]:
    report["unmatched_refs"].append(f"* @{r['pos']} ({r['kind']})")
  consumed = {id(d) for d, _, _ in moves} | {id(d) for d in dropped}
  for d in bare:
    if id(d) not in consumed:
      report["unmatched_defs"].append(f"* @{d['pos']}")
  if not moves and not dropped:
    return content, report
  edits = []
  for d in dropped:
    edits.append((d["pos"], d["end"], ""))
  for d, r, place_text in moves:
    edits.append((d["pos"], d["end"], ""))
    if r["block"] is not None:
      edits.append((r["block"]["close"], r["block"]["close"], "\n\n" + place_text + "\n"))
    else:
      _, pe = r["para"]
      edits.append((pe, pe, "\n\n" + place_text))
  return _apply_edits(content, edits), report


def _lone_items(content, misc_summaries=("Misc",)):
  """Refs/defs with no partner inside their own file.

  A ref is lone when it is neither sequentially matched nor already
  satisfied by a same-id definition inside its block; a bare def is lone
  when sequentially unmatched. Conservative on purpose: items tangled in
  rival/eviction situations stay out (they keep their intra-file state).
  Returns (blocks, refs, bare, inside, lone_refs, lone_defs).
  """
  blocks = parse_details(content)
  depths = line_depths(content, blocks)
  refs, _, _ = collect_refs(content, blocks, depths, misc_summaries)
  bare = collect_bare_defs(content, depths) + collect_gap_defs(content, blocks, depths)
  bare.sort(key=lambda d: d["pos"])
  inside = collect_inside_defs(content, blocks, depths)
  def_spans = [(d["pos"], d["end"]) for d in bare]
  def_spans += [(d["pos"], d["end"]) for d in inside]
  refs = [r for r in refs
          if not any(s <= r["pos"] < e for s, e in def_spans)]
  pairs = monotone_match(refs, bare)
  matched_r = {ri for ri, _ in pairs}
  matched_b = {di for _, di in pairs}
  satisfied = set()
  for d in inside:
    if d["block"] is not None:
      satisfied.add((id(d["block"]), d["key"]))
  lone_refs = [r for i, r in enumerate(refs)
               if i not in matched_r
               and (id(r["block"]), r["key"]) not in satisfied]
  lone_defs = [d for j, d in enumerate(bare) if j not in matched_b]
  return blocks, refs, bare, inside, lone_refs, lone_defs


def match_cross_file_footnotes(prev_content, curr_content,
                               misc_summaries=("Misc",)):
  """Match lone refs of one chapter file with lone defs of its neighbour.

  Chapter splits sometimes strand footnotes across the file boundary: refs
  at the end of one file whose defs open (or close) the adjacent file, or
  vice versa. Both directions are tried; pairing is same-id monotone over
  the lone pools only, so intra-file arrangements are never disturbed.
  Defs move across the boundary into their ref's block.
  Returns (new_prev, new_curr, report).
  """
  report = {"placed": [], "relocated": [], "duplicates_dropped": [],
            "shared": [], "unmatched_refs": [], "unmatched_defs": [],
            "notes": []}
  p_blocks, _, _, _, p_refs, p_defs = _lone_items(prev_content, misc_summaries)
  c_blocks, _, _, _, c_refs, c_defs = _lone_items(curr_content, misc_summaries)
  moves = []  # (def, ref, from_curr: bool)
  for ri, di in monotone_match(p_refs, c_defs):
    moves.append((c_defs[di], p_refs[ri], True))
  for ri, di in monotone_match(c_refs, p_defs):
    moves.append((p_defs[di], c_refs[ri], False))
  if not moves:
    return prev_content, curr_content, report
  p_edits, c_edits = [], []
  for d, r, from_curr in moves:
    if from_curr:
      c_edits.append((d["pos"], d["end"], ""))
      tgt, ted = p_edits, r
    else:
      p_edits.append((d["pos"], d["end"], ""))
      tgt, ted = c_edits, r
    if ted["block"] is not None:
      ce = ted["block"]["close"]
      tgt.append((ce, ce, "\n\n" + d["text"] + "\n"))
    else:
      _, pe = ted["para"]
      tgt.append((pe, pe, "\n\n" + d["text"]))
    report["placed"].append(
      f"{d['id']} {'curr' if from_curr else 'prev'}@{d['pos']} "
      f"-> {'prev' if from_curr else 'curr'}-ref @{r['pos']} ({r['kind']})")
  new_prev = _apply_edits(prev_content, p_edits)
  new_curr = _apply_edits(curr_content, c_edits)
  return new_prev, new_curr, report


def match_lone_footnotes_in_directory(dir_path, write=False,
                                      misc_summaries=("Misc",)):
  """Apply cross-file matching to every consecutive chapter-file pair.

  Returns {filename: report}. Files are paired in sorted order; a file
  with no lone items is a no-op, so running this over a whole tree is
  safe. Pass write=True to persist.
  """
  import os
  names = sorted(f for f in os.listdir(dir_path) if f.endswith(".md"))
  texts = {}
  for n in names:
    with open(os.path.join(dir_path, n), encoding="utf-8") as f:
      texts[n] = f.read()
  reports, owned = {}, {}
  for a, b in zip(names, names[1:]):
    new_a, new_b, rep = match_cross_file_footnotes(texts[a], texts[b],
                                                   misc_summaries)
    if new_a != texts[a] or new_b != texts[b]:
      texts[a], texts[b] = new_a, new_b
      owned[a] = owned.get(a, {})
      owned[b] = owned.get(b, {})
      for k in rep:
        owned[a][k] = owned.get(a, {}).get(k, []) + rep[k]
        owned[b][k] = owned.get(b, {}).get(k, []) + rep[k]
  for n in names:
    reports[n] = owned.get(n, {"placed": [], "relocated": [],
                               "duplicates_dropped": [], "shared": [],
                               "unmatched_refs": [], "unmatched_defs": [],
                               "notes": []})
  if write:
    for n in names:
      with open(os.path.join(dir_path, n), "w", encoding="utf-8") as f:
        f.write(texts[n])
  return reports


def process_file(path, write=False, **kwargs):
  with open(path, encoding="utf-8") as f:
    content = f.read()
  new_content, report = match_dangling_footnotes_sequentially(content, **kwargs)
  if write and new_content != content:
    with open(path, "w", encoding="utf-8") as f:
      f.write(new_content)
  return new_content != content, report
