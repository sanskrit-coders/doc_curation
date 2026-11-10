import csv
import os
import re
import urllib.request

COMMENTARY_PATTERN = re.compile(r"<details[^>]*><summary>(सायण-टीका|भट्टभास्कर-टीका)</summary>")
VINIYOGA_BLOCK_PATTERN = re.compile(r"<details[^>]*><summary>(सायणोक्त-विनियोगः|भास्करोक्त-विनियोगः)</summary>")
VISHVASA_PATTERN = re.compile(r"<summary>विश्वास-प्रस्तुतिः")

NON_VINIYOGA_AHA = (
    "विशेषणमाह", "दृष्टान्तमाह", "हेतुमाह", "अर्थमाह",
    "फलमाह", "तात्पर्यमाह", "उत्तरमाह", "किमित्याह",
)

PRATIKA_PART_RE = re.compile(
    r"(इति|[ेिी]ति|इत्य|त्याद|इत्माद|डति"
    r"|गायत्र|त्रिष्टु|जगत|अनुष्टु|बृहत|पङ्क्त|उष्णि|विरा|शक्वर|अत्यष्ट"
    r"|द्विपद|त्रिपद|चतुष्पद|एकपद|पञ्चपद|पाद|अर्धर्च|मन्त्र|अनुवाक|ऋग्भिः|भिः\s*$"
    r"|व्याख्यात|निगद|ब्राह्मण|पुरोनुवाक्य|याज्य|सामिधेन|होम|यजु)"
)

VINIYOGA_VERB_RE = re.compile(
    r"(जुहोति|जुहुयात्|जपति|जपेत्|आदधाति|उपदधाति|उपतिष्ठते|अभिमन्त्रयते|अनुमन्त्रयते|आलभते|आलभेत|अभिमृशति|अभिमृशेत्"
    r"|अभिजिघ्रति|अवजिघ्रति|प्रयच्छति|प्रतिगृह्णाति|गृह्णाति|निर्वपति|निर्वपेत्|अवद्यति|अवसिञ्चति|अभिषिञ्चति|प्रोक्षति"
    r"|मार्जयन्ते|मार्जयति|वाचयति|ब्रूयात्|आह|पठति|विधत्ते|विनियुङ्क्ते|दर्शयति|उच्यते|उच्यन्ते|व्याख्यास्यते|प्रस्तौति"
    r"|करोति|कुर्यात्|भवन्ति|स्तौति|यजति|यजेत|ददाति|दद्यात्|(?<!प्रति)बध्नाति|मुञ्चति|विमुञ्चति|संमार्ष्टि|नयति|हरति|सादयति"
    r"|प्रतितपति|अभिदधाति|उपाकरोति|अन्वाह|उत्सृजति|प्रसर्पति|अवेक्षते|ईक्षते|संवेशयति|उच्छ्रयति|मिनोति|छिनत्ति|वृश्चति"
    r"|कल्पः|ब्राह्मणम्|पुरोनुवाक्या|याज्या|याज्यानुवाक्या|सामिधेन्यः|होमाः|मन्त्राः|यजुः|यजूँषि|ऋचः|ऋचौ|अनुवाक"
    r"|उत्तरस्यां श्रोण्यां|उत्तरे\s*ऽ?ंसे)"
)

BAD_BEFORE_DASH = (
    "यद्वा", "अथवा", "किञ्च", "किं च", "किंच", "किं बहुना", "अन्य आह", "केचित्",
    "इत्याह", "अर्थाः", "मित्यत्र", "इति वक्तव्ये", "पा.सू.", "उ.सू.", "तै.ब्रा.",
    "तदेवाह", "कस्माद", "कथमित्याह", "अत्रेदमुक्तम्", "सङ्गतिः", "उच्यते -", "मन्त्रार्थस्तु",
    "तत्राह", "विशेष्यते", "परोक्षम् उच्यते", "इति चेत्", "चेत्", "यथा", "यथोक्तम्", "उच्यते", "**",
    "अत्र ब्राह्मणम्", "ब्राह्मणं च भवति", "गतम् ।", "प्रत्यक्षेणाह",
    "महानुभावत्वमाह", "विधानार्थमाह", "भवतीत्याह", "दार्ष्टान्तिकः",
    "विधत्ते", "प्रशंसति",
)

MANTRA_ANUVAKAS_IN_BRAHMANA_SECTIONS = {
    (2, 3, 9), (2, 3, 10), (2, 4, 5), (2, 4, 7), (2, 4, 8),
    (5, 5, 5), (5, 5, 9), (5, 5, 10), (5, 6, 1), (5, 6, 4), (5, 6, 8),
    (5, 7, 2), (5, 7, 3), (5, 7, 4), (5, 7, 5), (5, 7, 6), (5, 7, 7), (5, 7, 8), (5, 7, 9),
    (7, 5, 14), (7, 5, 23), (7, 5, 24),
}


def _extract_sayana_viniyoga(body_lines):
    start = 0
    while start < len(body_lines) and not body_lines[start].strip():
        start += 1
    if start >= len(body_lines):
        return None, body_lines

    marker_index = None
    marker = None
    marker_position = -1
    for index in range(start, min(len(body_lines), start + 9)):
        line = body_lines[index]
        if index > start:
            if line.lstrip().startswith("-"):
                break
            prev_text = " ".join(body_lines[start:index])
            if not (
                "अनुवाक" in prev_text
                or "कल्पः" in prev_text
                or "कल्पे" in prev_text
                or "प्रथमेनुवाके" in prev_text
                or "अथ " in prev_text
                or "तत्र आदौ" in prev_text
            ):
                break
        if any(bad in line for bad in NON_VINIYOGA_AHA):
            continue
        match = re.search(
            r"((?:पुरोनुवाक्याम्|याज्याम्|मन्त्रम्|मन्त्रान्|ऋचम्|यजुर्|शेषम्)\s+(?:आह|पठति)|माहः|माह|गाह|नाह|मृचं\s+पठति)(?:\s|[—–-])",
            line,
        )
        if match:
            before_m = line[:match.start()]
            if "।" not in before_m or "कल्प" in before_m or "अनुवाक" in before_m or "तत्र " in line[:match.start()]:
                marker_index = index
                marker = match.group(1)
                marker_position = match.start()
                break
        match2 = re.search(
            r"(प्रतीक[ंे]\s+दशंयति|प्रतीक[ंे]\s+दर्शय[तप]ि|प्रतीकानि\s+दर्शय[तप]ि|मन्त्रं\s+विनियुङ्क्ते)",
            line,
        )
        if match2:
            before_m = line[:match2.start()]
            if "।" not in before_m or "कल्प" in before_m or "अनुवाक" in before_m or "हवींष्य्" in before_m:
                marker_index = index
                marker = match2.group(1)
                marker_position = match2.start()
                break
        if "पाठस्तु" in line and "कल्पः" not in line and "हे " not in line and "!" not in line:
            p_pos = line.find("पाठस्तु")
            before_m = line[:p_pos]
            if (index > start or before_m.strip()) and ("।" not in before_m or "कल्प" in before_m or "अनुवाक" in before_m):
                marker_index = index
                marker = "पाठस्तु"
                marker_position = p_pos
                break

    if marker_index is None:
        for index in range(start, min(len(body_lines), start + 7)):
            if index > start:
                prev_text = " ".join(body_lines[start:index])
                if not ("अनुवाक" in prev_text or "अथ " in prev_text or "तत्र " in prev_text):
                    break
            if "कल्पः" in body_lines[index] or "इति कल्पे" in body_lines[index]:
                k_pos = body_lines[index].find("कल्प")
                before_m = body_lines[index][:k_pos]
                if "।" not in before_m or len(before_m.split()) <= 5 or "अनुवाक" in before_m:
                    marker_index = index
                    marker = "कल्पः"
                    marker_position = k_pos
                    break

    if marker_index is None:
        first_line = body_lines[start].strip()
        if first_line.startswith("(") and "अनुवाक" in first_line:
            marker_index = start
        elif re.match(
            r"^(प्रथमा|द्वितीया|तृतीया|चतुर्थी|पञ्चमी|षष्ठी|सप्तमी|अष्टमी|नवमी|दशमी)\b",
            first_line,
        ) and re.search(r"[—–-]", first_line):
            marker_index = start
        else:
            return None, body_lines

    end_index = marker_index
    if marker == "कल्पः":
        q_match = re.search(r"[\"”’\x27]\s*इति\s*।", body_lines[marker_index][marker_position:])
        if q_match:
            danda_index = marker_position + q_match.end() - 1
        elif marker_index + 1 < len(body_lines):
            q_match2 = re.search(r"[\"”’\x27]\s*इति\s*।", body_lines[marker_index + 1])
            if q_match2:
                end_index = marker_index + 1
                danda_index = q_match2.end() - 1
            else:
                danda_index = body_lines[marker_index].find("।", marker_position)
                if danda_index == -1:
                    end_index = marker_index + 1
                    danda_index = body_lines[end_index].find("।")
        else:
            danda_index = body_lines[marker_index].find("।", marker_position)
        if end_index + 1 < len(body_lines) and "पाठस्तु" in body_lines[end_index + 1]:
            p_danda = body_lines[end_index + 1].find("।", body_lines[end_index + 1].find("पाठस्तु"))
            if p_danda != -1:
                end_index = end_index + 1
                danda_index = p_danda
    else:
        if marker_position >= 0:
            danda_index = body_lines[marker_index].find("।", marker_position)
            if danda_index == -1:
                dd_idx = body_lines[marker_index].find("॥", marker_position)
                if dd_idx != -1 and ("दर्शय" in (marker or "") or "व्याख्यात" in body_lines[marker_index][marker_position:dd_idx]):
                    danda_index = dd_idx
        else:
            danda_index = body_lines[marker_index].find("।")
        if (
            marker_position >= 0
            and marker
            and ("आह" in marker or "माह" in marker or "गाह" in marker or "नाह" in marker or "पठति" in marker)
        ):
            after_marker_start = marker_position + len(marker)
            if danda_index == -1 or danda_index - marker_position > 45:
                search_end = danda_index if danda_index != -1 else min(len(body_lines[end_index]), after_marker_start + 50)
                iti_match = re.search(r"\S*(?:इति|[ेिी]ति)(?=\s)", body_lines[end_index][after_marker_start:search_end])
                if iti_match and iti_match.end() <= 35 and "हे " not in body_lines[end_index][after_marker_start:after_marker_start + iti_match.end()]:
                    split_at = after_marker_start + iti_match.end()
                    prefix = body_lines[end_index][:split_at] + "।"
                    remainder = body_lines[end_index][split_at:].lstrip()
                    segment = body_lines[start:end_index] + [prefix]
                    remaining = body_lines[:start]
                    if remainder:
                        remaining.append(remainder)
                    remaining.extend(body_lines[end_index + 1:])
                    return "\n".join(segment).strip("\n"), remaining
            m_dash = re.match(r"^\s*[—–-]", body_lines[end_index][after_marker_start:])
            if m_dash and (
                danda_index == -1
                or not re.search(r"(इति|[ेिी]ति)\s*$", body_lines[end_index][after_marker_start:danda_index])
            ) and (
                re.match(r"^(\(SB\)\s*)?[०-९0-9]", body_lines[start].strip())
                or "कल्प" in body_lines[start]
                or "मन्त्र" in body_lines[end_index][:after_marker_start]
                or "मृच" in body_lines[end_index][:after_marker_start]
                or re.match(r"^(अथ\s*|तत्र\s*)*(प्रथमा|द्वितीया|तृतीया|चतुर्थी|पञ्चमी|षष्ठी|सप्तमी|अष्टमी|नवमी|दशमी)", body_lines[start].strip())
            ):
                split_at = after_marker_start + m_dash.end()
                prefix = body_lines[end_index][:split_at].rstrip()
                remainder = body_lines[end_index][split_at:].lstrip()
                segment = body_lines[start:end_index] + [prefix]
                remaining = body_lines[:start]
                if remainder:
                    remaining.append(remainder)
                remaining.extend(body_lines[end_index + 1:])
                return "\n".join(segment).strip("\n"), remaining
        if danda_index != -1 and marker and ("दर्शयति" in marker or "दशंयति" in marker or "विनियुङ्क्ते" in marker):
            after = body_lines[end_index][danda_index + 1:]
            m_extra = re.match(
                r"^(\s*[^।]*इति\s+(?:पुरोनुवाक्या|याज्या)\s*।(?:\s*एतच्चोभयं[^।]*व्याख्यातम्\s*।)?)",
                after,
            )
            if m_extra:
                danda_index += len(m_extra.group(1))

    if danda_index == -1 or end_index - start > 9:
        return None, body_lines

    prefix = body_lines[end_index][:danda_index + 1]
    remainder = body_lines[end_index][danda_index + 1:].lstrip()
    segment = body_lines[start:end_index] + [prefix]

    remaining = body_lines[:start]
    if remainder:
        remaining.append(remainder)
    remaining.extend(body_lines[end_index + 1:])
    return "\n".join(segment).strip("\n"), remaining


def _extract_bhaskara_viniyoga(body_lines):
    start = 0
    while start < len(body_lines) and not body_lines[start].strip():
        start += 1
    if start >= len(body_lines):
        return None, body_lines

    window = body_lines[start:min(len(body_lines), start + 8)]
    joined = "\n".join(window)

    dash_match = re.search(r"\s+[—–-]\s+", joined)
    if dash_match:
        before_dash = joined[:dash_match.start()].strip()
        after_dash = joined[dash_match.end():]
        valid_before = (
            ("॥" not in before_dash or "अतः पर" in before_dash or "समाप्तमनुवाक" in before_dash)
            and not any(b in before_dash for b in BAD_BEFORE_DASH)
            and (
                "।" not in before_dash
                or "(SB)" in before_dash
                or "अतः पर" in before_dash
                or "अतःपर" in before_dash
                or "अनुवाक" in before_dash
                or "ब्राह्मणम्" in before_dash
                or "सूक्त" in before_dash
                or "कल्प" in before_dash
            )
        )
        if valid_before:
            dd_pos = after_dash.find("॥")
            if dd_pos != -1 and dd_pos < 220:
                pratika_part = after_dash[:dd_pos].strip()
                if (
                    " - " not in pratika_part
                    and "\n" not in pratika_part
                    and "।" not in pratika_part
                    and len(pratika_part.split()) <= 12
                    and not re.search(r"(आह|माह|नाह|गाह|दर्शयति|उच्यते|अभिधीयते)$", before_dash)
                ):
                    if PRATIKA_PART_RE.search(pratika_part) and "हे " not in pratika_part:
                        end_pos = dash_match.end() + dd_pos + len("॥")
                        after_dd = joined[end_pos:]
                        m_star = re.match(r"^(\*{1,2})", after_dd)
                        if m_star:
                            end_pos += len(m_star.group(1))
                        vin = joined[:end_pos].strip()
                        rem_text = joined[end_pos:].lstrip(" \t")
                        if rem_text.startswith("\n"):
                            rem_text = rem_text[1:]
                        rem_lines = (rem_text.split("\n") if rem_text else []) + body_lines[start + len(window):]
                        return vin, rem_lines
            d_pos = after_dash.find("।")
            if d_pos != -1 and d_pos < 180:
                pratika_part = after_dash[:d_pos].strip()
                if (
                    PRATIKA_PART_RE.search(pratika_part)
                    and "हे " not in pratika_part
                    and " - " not in pratika_part
                    and "\n" not in pratika_part
                    and len(pratika_part.split()) <= 10
                ):
                    end_pos = dash_match.end() + d_pos + len("।")
                    after_d = joined[end_pos:]
                    m_star = re.match(r"^(\*{1,2})", after_d)
                    if m_star:
                        end_pos += len(m_star.group(1))
                    vin = joined[:end_pos].strip()
                    rem_text = joined[end_pos:].lstrip(" \t")
                    if rem_text.startswith("\n"):
                        rem_text = rem_text[1:]
                    rem_lines = (rem_text.split("\n") if rem_text else []) + body_lines[start + len(window):]
                    return vin, rem_lines
            if VINIYOGA_VERB_RE.search(before_dash) and len(before_dash) < 250:
                end_pos = dash_match.end()
                vin = joined[:end_pos].strip()
                rem_text = joined[end_pos:].lstrip(" \t")
                if rem_text.startswith("\n"):
                    rem_text = rem_text[1:]
                rem_lines = (rem_text.split("\n") if rem_text else []) + body_lines[start + len(window):]
                return vin, rem_lines

    first_line = body_lines[start].strip()
    dd_pos = first_line.find("॥")
    if dd_pos != -1:
        cand = first_line[:dd_pos].strip()
        if (
            "।" not in cand
            and not any(b in cand for b in BAD_BEFORE_DASH)
            and re.match(
                r"^(\(SB\)\s*)?([०-९0-9]+|अथ|तत्र|पुनरपि|उत्तरा|तिसृभिः|द्वाभ्याम्|चतसृभिः|पञ्चभिः|षड्भिः|सप्तभिः|अष्टभिः|दशभिः|एकादशभिः|द्वादशभिः)",
                cand,
            )
        ):
            cand_clean = re.sub(r"^(\(SB\)\s*)?[०-९0-9]+\s*", "", cand).strip()
            words = cand_clean.split()
            if 2 <= len(words) <= 14 and VINIYOGA_VERB_RE.search(cand_clean):
                if not (
                    len(words) <= 4
                    and re.search(r"(इति|[ेिी]ति|त्यादि)$", words[-1])
                    and not re.search(
                        r"(पुरोनुवाक्या|याज्या|सामिधेन्यः|ब्राह्मणम्|सर्वोनुवाकः|होमाः|मन्त्राः|यजुः|यजूँषि)",
                        cand_clean,
                    )
                ):
                    end_pos = dd_pos + len("॥")
                    vin = first_line[:end_pos].strip()
                    rem_first = first_line[end_pos:].strip()
                    rem_lines = ([rem_first] if rem_first else []) + body_lines[start + 1:]
                    return vin, rem_lines

    return None, body_lines


def _extract_viniyoga(body_lines, commentary_label="सायण-टीका"):
    if commentary_label == "भट्टभास्कर-टीका":
        return _extract_bhaskara_viniyoga(body_lines)
    vin, rem = _extract_sayana_viniyoga(body_lines)
    if vin is None:
        return _extract_bhaskara_viniyoga(body_lines)
    return vin, rem


SHEET_CSV = "/tmp/taittiriiya_sheet.csv"


SHEET_URL = "https://docs.google.com/spreadsheets/d/1xFXhg__yitgiECypnO5KAc9Xbe8cTzt-9dZD3AqpmtU/export?format=csv&gid=1729387077"


def _sheet_rows(sheet_csv=SHEET_CSV):
    if not os.path.exists(sheet_csv):
        try:
            urllib.request.urlretrieve(SHEET_URL, sheet_csv)
        except OSError:
            return []
    with open(sheet_csv, encoding="utf-8") as handle:
        return list(csv.reader(handle))


def _file_anuvAka(md_file):
    parts = md_file.file_path.split(os.sep)
    try:
        index = parts.index("sarva-prastutiH")
        kANDa = int(parts[index + 1].split("_")[0])
        prashna = int(parts[index + 2].split("_")[0])
        name = parts[index + 3]
        stem = os.path.splitext(name)[0]
        match = re.match(r"^(\d+)", stem)
        if not match:
            return None
        anuvAka = int(match.group(1))
        return kANDa, prashna, anuvAka
    except (ValueError, IndexError):
        return None


def is_brAhmaNam_anuvAka(md_file):
    """Return True when the sArasvata sheet marks this anuvAka as a brAhmaNam portion."""
    if "brAhmaNam" in os.path.basename(md_file.file_path):
        return True
    work_id = "2" if "brAhmaNam" in md_file.file_path else "1"
    location = _file_anuvAka(md_file)
    if location is None:
        return "brAhmaNam" in md_file.file_path
    if work_id == "1" and location in MANTRA_ANUVAKAS_IN_BRAHMANA_SECTIONS:
        return False
    kANDa, prashna, anuvAka = location
    for row in _sheet_rows():
        if len(row) < 8:
            continue
        try:
            if row[3] == work_id and int(row[4]) == kANDa and int(row[5]) == prashna and int(row[6]) == anuvAka:
                return row[7].strip().endswith("ब्राह्मणम्")
        except ValueError:
            continue
    return False


def _is_commentary(line):
    match = COMMENTARY_PATTERN.match(line)
    if match:
        return match.group(1)
    return None


def _is_viniyoga_block(line):
    match = VINIYOGA_BLOCK_PATTERN.match(line)
    if match:
        return match.group(1)
    return None


def _is_vishvasa(line):
    return (
        (line.startswith("<details") and VISHVASA_PATTERN.search(line))
        or (line.startswith('<div class="js_include"') and ("vishvAsa-prastutiH" in line or "sarva-prastutiH" in line))
    )


def _norm_viniyoga(text):
    return re.sub(r"[^ऀ-ॿ]", "", re.sub(r"[०-९0-9]", "", text))


def _remove_empty_commentaries(lines):
    result = []
    index = 0
    while index < len(lines):
        if _is_commentary(lines[index]):
            end = index + 1
            while end < len(lines) and lines[end].strip() != "</details>":
                end += 1
            if end < len(lines) and not any(line.strip() for line in lines[index + 1:end]):
                index = end + 1
                while index < len(lines) and not lines[index].strip():
                    index += 1
                continue
        result.append(lines[index])
        index += 1
    return result


def _resolve_include_url(div_line):
    match = re.search(r'url="([^"]+)"', div_line)
    if not match:
        return None
    url = match.group(1)
    if url.startswith("/vedAH_yajuH/"):
        return "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/" + url[len("/vedAH_yajuH/"):]
    if url.startswith("/vedAH_Rk/"):
        return "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/" + url[len("/vedAH_Rk/"):]
    return None


def _strip_viniyoga_from_include_target(div_line, commentary_label):
    target_path = _resolve_include_url(div_line)
    if not target_path or not os.path.exists(target_path):
        return
    with open(target_path, encoding="utf-8") as handle:
        t_lines = handle.read().split("\n")
    t_out = []
    idx = 0
    changed = False
    while idx < len(t_lines):
        if _is_commentary(t_lines[idx]) == commentary_label:
            end = idx + 1
            while end < len(t_lines) and t_lines[end].strip() != "</details>":
                end += 1
            if end < len(t_lines) and "_____" not in "\n".join(t_lines[idx + 1:end]):
                vin, rem = _extract_viniyoga(t_lines[idx + 1:end], commentary_label)
                if vin:
                    changed = True
                    t_out.append(t_lines[idx])
                    if rem and rem[0].strip():
                        t_out.append("")
                    t_out.extend(rem)
                    t_out.append(t_lines[end])
                    idx = end + 1
                    continue
        t_out.append(t_lines[idx])
        idx += 1
    if changed:
        t_out = _remove_empty_commentaries(t_out)
        with open(target_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(t_out))


def separate_viniyogas(md_file):
    """Move viniyoga text out of Sāyaṇa/Bhaṭṭa-Bhāskara commentary blocks into विनियोगः blocks before the corresponding विश्वास-प्रस्तुतिः block or include."""
    if is_brAhmaNam_anuvAka(md_file):
        return
    metadata, content = md_file.read()
    lines = content.split("\n")
    output = []
    index = 0
    div_stack = []
    sangraha_texts = []
    current_vishvasa_index = None
    current_unit_viniyogas = {}
    seen_body_since_vishvasa = False

    while index < len(lines):
        line = lines[index]
        if line.startswith('<div class="js_include"'):
            in_normal_scope = not div_stack or "01_kumbheShTakA__" in div_stack[-1]
            if in_normal_scope and "01_kumbheShTakA__" not in line:
                if _is_vishvasa(line):
                    if seen_body_since_vishvasa:
                        current_unit_viniyogas = {}
                        current_vishvasa_index = len(output)
                        seen_body_since_vishvasa = False
                    elif current_vishvasa_index is None:
                        current_vishvasa_index = len(output)
                elif "sarvASh_TIkAH" in line:
                    seen_body_since_vishvasa = True
            div_stack.append(line)
            output.append(line)
            index += 1
            continue
        if div_stack:
            if "</div>" in line:
                div_stack.pop()
                output.append(line)
                index += 1
                continue
            top_div = div_stack[-1]
            if "01_kumbheShTakA__" in top_div:
                pass
            elif "/sarvASh_TIkAH/" in top_div and (("brAhmaNam" in md_file.file_path) == ("brAhmaNam" in top_div)):
                if not _is_commentary(line):
                    output.append(line)
                    index += 1
                    continue
            else:
                output.append(line)
                index += 1
                continue

        if line.strip() == "<details><summary>मूलम् (संयुक्तम्)</summary>":
            if seen_body_since_vishvasa:
                current_unit_viniyogas = {}
                current_vishvasa_index = None
                seen_body_since_vishvasa = False

        v_block_title = _is_viniyoga_block(line)
        if v_block_title:
            if seen_body_since_vishvasa:
                current_unit_viniyogas = {}
                current_vishvasa_index = None
                seen_body_since_vishvasa = False
            end = index + 1
            while end < len(lines) and lines[end].strip() != "</details>":
                end += 1
            v_start = len(output)
            output.extend(lines[index:end + 1])
            v_end = len(output) - 1
            current_unit_viniyogas[v_block_title] = (v_start, v_end)
            index = end + 1
            continue

        if _is_vishvasa(line):
            if seen_body_since_vishvasa:
                current_unit_viniyogas = {}
                current_vishvasa_index = len(output)
                seen_body_since_vishvasa = False
            elif current_vishvasa_index is None:
                current_vishvasa_index = len(output)
            output.append(line)
            index += 1
            continue

        if line.startswith("<details><summary>मूलम्</summary>") or line.startswith("<details><summary>पद-पाठः</summary>"):
            seen_body_since_vishvasa = True

        commentary_label = _is_commentary(line)
        if commentary_label:
            seen_body_since_vishvasa = True
            end = index + 1
            while end < len(lines) and lines[end].strip() != "</details>":
                end += 1
            if end < len(lines) and not (
                div_stack and "/sarvASh_TIkAH/" in div_stack[-1] and "_____" in "\n".join(lines[index + 1:end])
            ):
                viniyoga, remaining = _extract_viniyoga(lines[index + 1:end], commentary_label)
                sangraha_lines = []
                for sangraha_index, sangraha_line in enumerate(remaining):
                    if sangraha_line.strip().startswith("अत्र विनियोगसंग्रहः"):
                        sangraha_lines = remaining[sangraha_index:]
                        remaining = remaining[:sangraha_index]
                        break
                if viniyoga:
                    if div_stack and "/sarvASh_TIkAH/" in div_stack[-1]:
                        _strip_viniyoga_from_include_target(div_stack[-1], commentary_label)
                    title = "भास्करोक्त-विनियोगः" if commentary_label == "भट्टभास्कर-टीका" else "सायणोक्त-विनियोगः"
                    if title in current_unit_viniyogas:
                        v_start, v_end = current_unit_viniyogas[title]
                        existing_body = "\n".join(output[v_start + 1:v_end]).strip()
                        new_body = None
                        if not existing_body:
                            new_body = viniyoga
                        elif (
                            "+++" not in existing_body
                            and "=" not in existing_body
                            and '"' not in existing_body
                            and "," not in existing_body
                        ):
                            ne, nn = _norm_viniyoga(existing_body), _norm_viniyoga(viniyoga)
                            if ne != nn and (not re.match(r"^[०-९0-9]", existing_body) or ne in nn):
                                new_body = viniyoga
                            elif ne != nn and nn not in ne:
                                new_body = existing_body + " " + viniyoga
                        if new_body is not None:
                            replacement_lines = ["", new_body]
                            old_len = v_end - (v_start + 1)
                            delta = len(replacement_lines) - old_len
                            output[v_start + 1:v_end] = replacement_lines
                            if current_vishvasa_index is not None and current_vishvasa_index > v_start:
                                current_vishvasa_index += delta
                            for k, (ks, ke) in list(current_unit_viniyogas.items()):
                                if ks == v_start:
                                    current_unit_viniyogas[k] = (ks, ke + delta)
                                elif ks > v_start:
                                    current_unit_viniyogas[k] = (ks + delta, ke + delta)
                        output.append(line)
                        if remaining and remaining[0].strip():
                            output.append("")
                        output.extend(remaining)
                        output.append(lines[end])
                        index = end + 1
                        if sangraha_lines:
                            sangraha_texts.append("\n".join(sangraha_lines).strip("\n"))
                        continue
                    elif current_vishvasa_index is not None:
                        insert_lines = [
                            f"<details><summary>{title}</summary>",
                            "",
                            viniyoga,
                            "</details>",
                            "",
                        ]
                        ins_at = current_vishvasa_index
                        output[ins_at:ins_at] = insert_lines
                        delta = len(insert_lines)
                        current_vishvasa_index += delta
                        for k, (ks, ke) in list(current_unit_viniyogas.items()):
                            if ks >= ins_at:
                                current_unit_viniyogas[k] = (ks + delta, ke + delta)
                        current_unit_viniyogas[title] = (ins_at, ins_at + 3)
                        output.append(line)
                        if remaining and remaining[0].strip():
                            output.append("")
                        output.extend(remaining)
                        output.append(lines[end])
                        index = end + 1
                        if sangraha_lines:
                            sangraha_texts.append("\n".join(sangraha_lines).strip("\n"))
                        continue
        output.append(line)
        index += 1

    output = _remove_empty_commentaries(output)
    if sangraha_texts:
        output.extend(["", "<details><summary>विनियोगसङ्ग्रहः</summary>", "", "\n\n".join(sangraha_texts), "</details>"])
    md_file.replace_content_metadata(new_content="\n".join(output))
