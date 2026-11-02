import re
import unicodedata
from pathlib import Path

from doc_curation.md.file import MdFile

SRC_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA"
URL_PREFIX = "/vedAH_Rk/shAkalam/saMhitA"


def _normalize(text):
    text = re.sub(r"\+\+\+.*?\+\+\+", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\u0900-\u097F]+", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Mn", "Mc", "Me"))
    for ch in ("ं", "ँ", "ः", "ऽ", "।", "॥"):
        text = text.replace(ch, "")
    return re.sub(r"[०-९]", "", text)


def _strip_frontmatter(text):
    if text.startswith("+++"):
        parts = text.split("+++", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    if text.startswith("---"):
        match = re.match(r"^---\n.*?\n---\n", text, re.S)
        if match:
            return text[match.end():]
    return text


def _frontmatter_title(text):
    match = re.search(r"^(?:\+\+\+|---)\s*\ntitle\s*=\s*\"(.+?)\"", text, re.M)
    if not match:
        match = re.search(r"^title:\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else ""


def _build_index(src_dir):
    src_dir = Path(src_dir)
    index = {}
    for path in sorted((src_dir / "sarvASh_TIkAH").rglob("*.md")):
        if path.name == "_index.md":
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r"<details><summary>Thomson & Solcum</summary>(.*?)</details>", text, re.S)
        if not match:
            continue
        key = _normalize(match.group(1))
        if key:
            index.setdefault(key, []).append(path)
    return index


def _details_pattern(title):
    return re.compile(
        r"(?s)<details(?: open)?><summary>" + re.escape(title) + r"</summary>(.*?)</details>"
    )


def _find_previous_details(text, title, before):
    pattern = _details_pattern(title)
    found = None
    for match in pattern.finditer(text, 0, before):
        found = match
    return found


def _find_next_marker(text, start):
    pattern = re.compile(
        r"<details(?: open)?><summary>(?:विश्वास-प्रस्तुतिः|सायणोक्त-विनियोगः|भास्करोक्त-विनियोगः)</summary>"
        r"|<div class=\"js_include\""
    )
    match = pattern.search(text, start)
    return match.start() if match else len(text)


def _extract_body(text, title):
    pattern = _details_pattern(title)
    return [(m.start(), m.end(), m.group(1).strip()) for m in pattern.finditer(text)]


def _include_block(kind, rel_path, body, title):
    if kind == "vishvAsa-prastutiH":
        attrs = 'includetitle="plain" newlevelforh1="5" title="विश्वास-प्रस्तुतिः"'
        summary = "विश्वास-प्रस्तुतिः ...{Loading}..."
    else:
        attrs = 'includetitle="false" newlevelforh1="5"'
        summary = (title or rel_path.split("/")[-1][:3]) + " ...{Loading}..."
    return (
        f'<div class="js_include" {attrs} unfilled url="{URL_PREFIX}/{kind}/{rel_path}">\n'
        f'<details open><summary><h5>{summary}</h5></summary>\n\n'
        f"{body.strip()}\n\n</details>\n</div>"
    )


def _ensure_block(text, title, body, anchor_title=None):
    pattern = _details_pattern(title)
    if pattern.search(text):
        return text
    block = f"<details><summary>{title}</summary>\n\n{body.strip()}\n</details>\n"
    if anchor_title:
        anchor = _details_pattern(anchor_title)
        matches = list(anchor.finditer(text))
        if matches:
            end = matches[0].end()
            return text[:end] + "\n" + block + text[end:]
    return text.rstrip() + "\n\n" + block


def _append_under(text, title, body):
    pattern = _details_pattern(title)
    match = pattern.search(text)
    if not match:
        return _ensure_block(text, title, body)
    insert_at = match.end() - len("</details>")
    return text[:insert_at] + "\n\n_____________\n" + body.strip() + "\n</details>" + text[match.end():]


def _reorder_bhattabhaskara(text):
    s_pat = _details_pattern("सायण-भाष्यम्")
    b_pat = _details_pattern("भट्टभास्कर-टीका")
    s_match = s_pat.search(text)
    b_matches = list(b_pat.finditer(text))
    if not s_match or not b_matches:
        return text
    if not text[s_match.end():b_matches[0].start()].strip():
        return text
    blocks = [text[m.start():m.end()] for m in b_matches]
    for m in reversed(b_matches):
        text = text[:m.start()] + text[m.end():]
    s_match = s_pat.search(text)
    insert_at = s_match.end()
    return text[:insert_at] + "\n\n" + "\n\n".join(blocks) + text[insert_at:]


def _move_to_sarvASh_TIkAH(path, mUla, padapATha, commentaries):
    text = path.read_text(encoding="utf-8")
    if mUla:
        text = _ensure_block(text, "तैत्तिरीयम् मूलम्", mUla, anchor_title="Thomson & Solcum")
    if padapATha:
        text = _ensure_block(text, "पद-पाठः-तैत्तिरीयः", padapATha, anchor_title="पद-पाठः")
    if commentaries.get("सायण-टीका"):
        text = _append_under(text, "सायण-भाष्यम्", commentaries["सायण-टीका"])
    if commentaries.get("भट्टभास्कर-टीका"):
        text = _append_under(text, "भट्टभास्कर-टीका", commentaries["भट्टभास्कर-टीका"])
    text = _reorder_bhattabhaskara(text)
    path.write_text(text, encoding="utf-8")


def include(content, src_dir=SRC_DIR, dry_run=False):
    src_dir = Path(src_dir)
    index = _build_index(src_dir)
    paths = []
    if isinstance(content, (str, Path)):
        p = Path(content)
        paths = sorted(p.rglob("*.md")) if p.is_dir() else [p]
    else:
        paths = [Path(p) for p in content]

    changes = []
    for path in paths:
        if path.name == "_index.md":
            continue
        text = path.read_text(encoding="utf-8")
        mUla_blocks = _extract_body(text, "मूलम्")
        if not mUla_blocks:
            continue
        used_starts = set()
        replacements = []
        for m_start, m_end, m_body in mUla_blocks:
            key = _normalize(m_body)
            if key not in index:
                continue
            target = index[key][0]
            rel = target.relative_to(src_dir / "sarvASh_TIkAH").as_posix()
            vishvasa_path = src_dir / "vishvAsa-prastutiH" / rel
            if not vishvasa_path.exists():
                continue
            prev = _find_previous_details(text, "विश्वास-प्रस्तुतिः", m_start)
            if not prev:
                continue
            if prev.start() in used_starts:
                continue
            used_starts.add(prev.start())
            group_end = _find_next_marker(text, m_end)
            group = text[prev.start():group_end]
            if "<details><summary>मूलम्</summary>" not in group:
                continue
            local_mUla = _extract_body(group, "मूलम्")
            local_pada = _extract_body(group, "पद-पाठः")
            commentaries = {}
            for title in ("सायण-टीका", "भट्टभास्कर-टीका"):
                blocks = _extract_body(group, title)
                if blocks:
                    commentaries[title] = "\n\n".join(b for _, _, b in blocks)
            mUla_text = "\n\n".join(b for _, _, b in local_mUla)
            pada_text = "\n\n".join(b for _, _, b in local_pada)
            if not dry_run:
                _move_to_sarvASh_TIkAH(target, mUla_text, pada_text, commentaries)
            v_raw = vishvasa_path.read_text(encoding="utf-8")
            s_raw = target.read_text(encoding="utf-8")
            v_body = _strip_frontmatter(v_raw)
            s_body = _strip_frontmatter(s_raw)
            s_title = _frontmatter_title(s_raw)
            replacement = (
                _include_block("vishvAsa-prastutiH", rel, v_body, "विश्वास-प्रस्तुतिः")
                + "\n"
                + _include_block("sarvASh_TIkAH", rel, s_body, s_title)
            )
            replacements.append((prev.start(), group_end, replacement))
        if replacements:
            for start, end, replacement in sorted(replacements, reverse=True):
                text = text[:start] + replacement + text[end:]
            if not dry_run:
                path.write_text(text, encoding="utf-8")
            changes.append((path, len(replacements)))
    return changes


if __name__ == "__main__":
    import sys
    result = include(sys.argv[1] if len(sys.argv) > 1 else ".", dry_run="--dry-run" in sys.argv)
    for path, count in result:
        print(path, count)
