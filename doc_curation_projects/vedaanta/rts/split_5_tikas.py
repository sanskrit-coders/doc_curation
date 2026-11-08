#!/usr/bin/env python3
"""Separate RTS 5-tIkAH word-split-drive OCR into per-TIkA, per-adhikAra Markdown files.

Each page in the destination file corresponds to the original page in Volumes 1-3,
retaining the page marker [[P...]], wrapping any mUlam block on that page in:

<details open><summary>मूलम्</summary>

...
</details>

followed by the corresponding commentary block (without altering the OCR text itself).
Folder and adhikAra structure is inferred directly from sarva-prastutiH.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


RTS_BASE = Path(
    "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/"
    "venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH"
)
SARVA_PRASTUTI_DIR = RTS_BASE / "sarva-prastutiH"
TIKA_BASE_DIR = RTS_BASE / "5-tIkAH"
STATE_BASE_DIR = TIKA_BASE_DIR / "raw" / ".ocr_state"

# The 5 commentaries in canonical page order
TIKAS: List[Tuple[str, str, str]] = [
    ("dIpikA", "sAra-dIpikA", "+सार-दीपिका"),
    ("AsvAdinI", "sArAsvAdinI", "+सारास्वादिनी"),
    ("prakAshikA", "sAra-prakAshikA", "+सार-प्रकाशिका"),
    ("vivaraNI", "sAra-vivaraNI", "+सार-विवरणी"),
    ("sangrahaH", "sAra-prakAshikA-sangrahaH", "+सार-प्रकाशिका-सङ्ग्रहः"),
]

ORDER = ["mUlam", "dIpikA", "AsvAdinI", "prakAshikA", "vivaraNI", "sangrahaH"]

# Exact page boundaries (volume, start_pdf_idx, end_pdf_idx) for adhikAras 00..32
ADHIKARA_PAGE_RANGES: Dict[int, Tuple[int, int, int]] = {
    0: (1, 16, 71),
    1: (1, 72, 109),
    2: (1, 110, 125),
    3: (1, 126, 163),
    4: (1, 164, 209),
    5: (1, 210, 328),
    6: (1, 329, 409),
    7: (1, 410, 436),
    8: (1, 437, 479),
    9: (1, 480, 519),
    10: (1, 520, 539),
    11: (1, 540, 597),
    12: (1, 598, 650),
    13: (2, 16, 41),
    14: (2, 42, 64),
    15: (2, 65, 116),
    16: (2, 117, 155),
    17: (2, 156, 186),
    18: (2, 187, 246),
    19: (2, 247, 270),
    20: (2, 271, 309),
    21: (2, 310, 339),
    22: (2, 340, 386),
    23: (2, 387, 492),
    24: (2, 493, 607),
    25: (2, 608, 705),
    26: (2, 706, 749),
    27: (3, 16, 253),
    28: (3, 254, 398),
    29: (3, 399, 671),
    30: (3, 672, 693),
    31: (3, 694, 713),
    32: (3, 714, 749),
}

# Running header on a single line
RUN_HDR_RE = re.compile(
    r"^(?:[०-९\d]+\s+)?(?:व्याख्यान\s*पञ्चक[^\n]*|श्रीमद्रहस्य[^\n]*|[^\n]{1,45}(?:[अा]?धिकार|सार)[\u0903:;\.\s]*[०-९\d]+|[०-९\d]+)\s*$"
)

# Secondary split at line-initial commentary markers when --- was not emitted between two commentaries
COMM_SPLIT_RE = re.compile(
    r"(?=(?:^|\n)\s*(?:[१२३४५६1-6]\.\s*)?(?:[கक]\s+|\(\s*)?(?:"
    r"\(\s*(?:सां?|स|ना|पा|स्वा)[\s\.\:\,\;\-\u0903]*(?:दी|दि|धी|स्वा|स्व|सा|वा|प्र|प|का|वि|बि|सं|स)[^\n\)]*\)|"
    r"\(\s*(?:सां?|स|ना|पा|स्वा)[\s\.\:\,\;\-\u0903]+(?:दी|दि|धी|स्वा|स्व|सा|वा|प्र|प|का|वि|बि|सं|स)[\s\.\:\,\;\-\u0903]|"
    r"सा[\s]*[\.\:\-\,\u0903]+\s*(?:दी|दि|धी|स्वा|स्व|प्र|वि|सं)[\s\.\:\,\;\-\u0903\)]|"
    r"\(प्र\.\)|\(gmxr\)|वि\)"
    r"))"
)

COMM_PATS: List[Tuple[str, re.Pattern]] = [
    (
        "dIpikA",
        re.compile(
            r"^\s*(?:[१२३४५६1-6]\.\s*)?(?:[கक]\s+|\(\s*)?(?:\(\s*(?:सा|स|ना|पा)[\s\.\:\,\;\-\u0903]*(?:दी|दि|धी)|सा[\s]*[\.\:\-\,\u0903]+\s*(?:दी|दि|धी)|\(gmxr\)|श्रीभाष्य[^\n]*\n\s*सारदीपिका|सारदीपिका)"
        ),
    ),
    (
        "AsvAdinI",
        re.compile(
            r"^\s*(?:[१२३४५६1-6]\.\s*)?(?:\(\s*(?:सा|स|ना|पा|स्वा)[\s\.\:\,\;\-\u0903]*(?:स्वा|स्व|वा|सा[\.\:\u0903\s\)])|सा[\s]*[\.\:\-\,\u0903]+\s*(?:स्वा|स्व)|(?:पूर्व|उत्तर)?सारास्वादिनी|श्रीगोपालार्य[^\n]*सारास्वादिनी)"
        ),
    ),
    (
        "prakAshikA",
        re.compile(
            r"^\s*(?:[१२३४५६1-6]\.\s*)?(?:\(\s*)?(?:\(\s*(?:सा|स|ना|पा)[\s\.\:\,\;\-\u0903]*(?:प्र(?!\.अ\.)|प[\.\:\u0903\,\;\s\)]|का[\.\)])|सा[\s]*[\.\:\-\,\u0903]+\s*प्र|\(प्र\.\)|सारप्रकाशिका(?!स))"
        ),
    ),
    (
        "vivaraNI",
        re.compile(
            r"^\s*(?:[१२३४५६1-6]\.\s*)?(?:\(\s*(?:सां?|स|ना|पा)[\s\.\:\,\;\-\u0903]*(?:वि|बि)|सा[\s]*[\.\:\-\,\u0903]+\s*वि|वि\)|सारविवरणी)"
        ),
    ),
    (
        "sangrahaH",
        re.compile(
            r"^\s*(?:[१२३४५६1-6]\.\s*)?(?:\(\s*(?:सा|स|ना|पा)[\s\.\:\,\;\-\u0903]*(?:सं|स[\.\:\u0903\,\;\s\)])|सा[\s]*[\.\:\-\,\u0903]+\s*सं|सारप्रकाशिकासङ्ग्रह)"
        ),
    ),
]

MULA_PAT = re.compile(
    r"^\s*(?:[१२३४५६1-6]\.\s*)?(?:\(सा\.प्र\.अ\.\)\s*)?(?:[-–—]*\s*)?(?:[मभ][ूु]?ल[ंम्\u0903]?|[मभ][ूुं्\u0903]?[\s\-\–\—\.\:\u0903।\']|श्रियै\s+नमः|॥\s*श्रीः\s*॥|म\s+समर्थ|म\s+मू)"
)


def read_toml_title(md_path: Path) -> str:
    txt = md_path.read_text(encoding="utf-8")
    m = re.search(r'^\s*title\s*=\s*"([^"]+)"', txt, flags=re.M)
    return m.group(1) if m else md_path.stem


def infer_structure_from_sarva_prastuti() -> Tuple[Dict[str, str], Dict[int, Tuple[str, str, str]]]:
    """Return (vibhaga_titles, adhikara_info) inferred from sarva-prastutiH.

    adhikara_info[num] = (vibhaga_folder, adhikara_stem, clean_title)
    """
    vibhaga_titles: Dict[str, str] = {}
    adhikara_info: Dict[int, Tuple[str, str, str]] = {}

    for vibhaga_dir in sorted(SARVA_PRASTUTI_DIR.iterdir()):
        if not vibhaga_dir.is_dir() or not re.match(r"^[1-4]_", vibhaga_dir.name):
            continue
        idx_file = vibhaga_dir / "_index.md"
        vibhaga_titles[vibhaga_dir.name] = (
            read_toml_title(idx_file) if idx_file.exists() else f"+{vibhaga_dir.name}"
        )
        for entry in sorted(vibhaga_dir.iterdir()):
            if entry.name == "_index.md":
                continue
            m = re.match(r"^(\d{2})_(.+?)(?:\.md)?$", entry.name)
            if not m:
                continue
            adh_num = int(m.group(1))
            stem = entry.stem if entry.is_file() else entry.name
            meta_path = entry if entry.is_file() else (entry / "_index.md")
            raw_title = read_toml_title(meta_path) if meta_path.exists() else stem
            clean_title = raw_title.lstrip("+").strip()
            adhikara_info[adh_num] = (vibhaga_dir.name, stem, clean_title)

    return vibhaga_titles, adhikara_info


def explicit_label(text: str) -> Optional[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None
    if re.match(r"^\s*\(सा\.प्र\.अ\.\)\s*मूलं", lines[0]):
        return "mUlam"
    for name, pat in COMM_PATS:
        if pat.search(lines[0]) or (
            len(lines) > 1 and pat.search(lines[1]) and RUN_HDR_RE.match(lines[0])
        ):
            return name
    if MULA_PAT.search(lines[0]) or (
        len(lines) > 1 and MULA_PAT.search(lines[1]) and RUN_HDR_RE.match(lines[0])
    ):
        return "mUlam"
    return None


def parse_page_blocks(vol: int, pdf_idx: int, page_md_path: Path) -> Tuple[str, Dict[str, List[str]]]:
    """Parse a single page file into (page_marker, grouped_blocks_by_role)."""
    txt = page_md_path.read_text(encoding="utf-8")
    m_marker = re.match(r"^(\[\[P[^\]]+\]\])\s*", txt)
    marker = m_marker.group(1) if m_marker else f"[[P{pdf_idx}]]"
    body = txt[m_marker.end() :].strip() if m_marker else txt.strip()

    raw_blocks = [b.strip() for b in re.split(r"\n+---\n+", body) if b.strip()]
    blocks: List[str] = []
    for rb in raw_blocks:
        parts = [pt.strip() for pt in COMM_SPLIT_RE.split(rb) if pt.strip()]
        for pt in parts:
            if len(pt.splitlines()) == 1 and RUN_HDR_RE.match(pt):
                continue
            blocks.append(pt)

    # Editorial addendum page at the end of Ch 29 (Vol 3 p00671 / [[P656]])
    if vol == 3 and pdf_idx == 671:
        labels: List[Optional[str]] = ["prakAshikA"] * len(blocks)
    else:
        labels = [explicit_label(b) for b in blocks]
        # Disambiguate rare OCR prefix typos using strict canonical neighbor order
        if len(labels) >= 2 and labels[0] == "AsvAdinI" and labels[1] == "AsvAdinI":
            labels[0] = "dIpikA"
        for i in range(1, len(labels)):
            if labels[i] is not None and labels[i] == labels[i - 1] and labels[i] != "mUlam":
                if i + 1 < len(labels) and labels[i + 1] is not None:
                    pi = ORDER.index(labels[i - 1])
                    ni = ORDER.index(labels[i + 1])
                    if ni - pi == 2:
                        labels[i] = ORDER[pi + 1]
                elif i == len(labels) - 1 and labels[i - 1] == "vivaraNI":
                    labels[i] = "sangrahaH"
            elif (
                i == len(labels) - 1
                and labels[i - 1] == "vivaraNI"
                and labels[i] == "prakAshikA"
            ):
                labels[i] = "sangrahaH"

    # Resolve unlabeled blocks deterministically via canonical order
    for i in range(len(blocks)):
        if labels[i] is not None:
            continue
        if i > 0 and re.search(r"सा\.\s*वि\s*$", blocks[i - 1]):
            labels[i] = "vivaraNI"
            continue
        prev_l = next((labels[j] for j in range(i - 1, -1, -1) if labels[j] is not None), None)
        next_l = next((labels[j] for j in range(i + 1, len(blocks)) if labels[j] is not None), None)
        if i == 0 and next_l == "dIpikA":
            labels[i] = "mUlam"
        elif i == 0 and next_l == "AsvAdinI":
            labels[i] = "dIpikA"
        elif prev_l is not None and next_l is not None:
            pi = ORDER.index(prev_l)
            ni = ORDER.index(next_l)
            if ni - pi == 2:
                labels[i] = ORDER[pi + 1]
            elif ni - pi <= 1:
                labels[i] = prev_l
        elif prev_l is not None and next_l is None:
            labels[i] = prev_l

    grouped: Dict[str, List[str]] = {k: [] for k in ORDER}
    for b, lbl in zip(blocks, labels):
        assert lbl is not None, f"Unresolved block on v{vol}/p{pdf_idx:05d}.md: {b[:80]}"
        grouped[lbl].append(b)

    return marker, grouped


def build_adhikara_files() -> None:
    vibhaga_titles, adhikara_info = infer_structure_from_sarva_prastuti()
    assert len(adhikara_info) == 33, f"Expected 33 adhikAras, found {len(adhikara_info)}"

    # Ensure top-level TIkA and vibhAga _index.md files exist
    for _, tika_folder, tika_title in TIKAS:
        tika_dir = TIKA_BASE_DIR / tika_folder
        tika_dir.mkdir(parents=True, exist_ok=True)
        (tika_dir / "_index.md").write_text(f'+++\ntitle = "{tika_title}"\n+++\n', encoding="utf-8")
        for vibhaga_folder, vibhaga_title in vibhaga_titles.items():
            v_dir = tika_dir / vibhaga_folder
            v_dir.mkdir(parents=True, exist_ok=True)
            (v_dir / "_index.md").write_text(
                f'+++\ntitle = "{vibhaga_title}"\n+++\n', encoding="utf-8"
            )

    total_pages = 0
    for adh_num in sorted(adhikara_info.keys()):
        vibhaga_folder, adh_stem, adh_title = adhikara_info[adh_num]
        vol, start_idx, end_idx = ADHIKARA_PAGE_RANGES[adh_num]
        vol_state_dir = STATE_BASE_DIR / f"word_split_v{vol}"

        per_tika_pages: Dict[str, List[str]] = {t[0]: [] for t in TIKAS}

        for pdf_idx in range(start_idx, end_idx + 1):
            page_path = vol_state_dir / f"p{pdf_idx:05d}.md"
            marker, grouped = parse_page_blocks(vol, pdf_idx, page_path)
            total_pages += 1

            mula_block = ""
            if grouped["mUlam"]:
                mula_content = "\n\n".join(grouped["mUlam"])
                mula_block = (
                    f"<details open><summary>मूलम्</summary>\n\n{mula_content}\n</details>"
                )

            for tika_key, _, _ in TIKAS:
                comm_content = "\n\n".join(grouped[tika_key])
                parts = [marker]
                if mula_block:
                    parts.append(mula_block)
                if comm_content:
                    parts.append(comm_content)
                per_tika_pages[tika_key].append("\n\n".join(parts))

        for tika_key, tika_folder, _ in TIKAS:
            dest_file = TIKA_BASE_DIR / tika_folder / vibhaga_folder / f"{adh_stem}.md"
            header = f'+++\ntitle = "{adh_title}"\n+++\n\n'
            body = "\n\n".join(per_tika_pages[tika_key]) + "\n"
            dest_file.write_text(header + body, encoding="utf-8")

    print(f"Successfully processed {total_pages} pages across 33 adhikAras into 5 TIkA folders.")


if __name__ == "__main__":
    build_adhikara_files()
