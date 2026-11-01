import csv
import os
import re
import urllib.request

COMMENTARY_PATTERN = re.compile(r"<details[^>]*><summary>(सायण-टीका|भट्टभास्कर-टीका)</summary>")
VISHVASA_PATTERN = re.compile(r"<summary>विश्वास-प्रस्तुतिः")


def _extract_viniyoga(body_lines):
    start = 0
    while start < len(body_lines) and not body_lines[start].strip():
        start += 1
    if start >= len(body_lines):
        return None, body_lines

    marker_index = None
    marker = None
    marker_position = -1
    for index in range(start, min(len(body_lines), start + 6)):
        line = body_lines[index]
        match = re.search(r"(माह|गाह)(?:\s|[—–-])", line)
        if match:
            marker_index = index
            marker = match.group(1)
            marker_position = match.start()
            break
        if "पाठस्तु" in line:
            marker_index = index
            marker = "पाठस्तु"
            marker_position = line.find("पाठस्तु")
            break

    if marker_index is None:
        for index in range(start, min(len(body_lines), start + 6)):
            if "कल्पः" in body_lines[index]:
                marker_index = index
                marker = "कल्पः"
                marker_position = body_lines[index].find("कल्पः")
                break

    if marker_index is None:
        first_line = body_lines[start].strip()
        if first_line.startswith("(") and "अनुवाक" in first_line:
            marker_index = start
        elif re.match(r"^(प्रथमा|द्वितीया|तृतीया|चतुर्थी|पञ्चमी|षष्ठी|सप्तमी|अष्टमी|नवमी|दशमी)", first_line):
            marker_index = start
        else:
            return None, body_lines

    end_index = marker_index
    if marker_position >= 0:
        danda_index = body_lines[marker_index].find("।", marker_position)
    else:
        danda_index = body_lines[marker_index].find("।")

    if danda_index == -1 and marker == "कल्पः" and marker_index + 1 < len(body_lines):
        end_index = marker_index + 1
        danda_index = body_lines[end_index].find("।")

    if danda_index == -1:
        return None, body_lines
    if end_index - start > 7:
        return None, body_lines

    prefix = body_lines[end_index][:danda_index + 1]
    remainder = body_lines[end_index][danda_index + 1:].lstrip()
    segment = body_lines[start:end_index] + [prefix]

    remaining = body_lines[:start]
    if remainder:
        remaining.append(remainder)
    remaining.extend(body_lines[end_index + 1:])
    return "\n".join(segment).strip("\n"), remaining


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
        kANDa = int(parts[index + 1])
        prashna = int(parts[index + 2])
        name = parts[index + 3]
        anuvAka = int(name.split("_")[0])
        return kANDa, prashna, anuvAka
    except (ValueError, IndexError):
        return None


def is_brAhmaNam_anuvAka(md_file):
    """Return True when the sArasvata sheet marks this anuvAka as a brAhmaNam portion."""
    if "brAhmaNam" in md_file.file_path:
        return True
    location = _file_anuvAka(md_file)
    if location is None:
        return False
    kANDa, prashna, anuvAka = location
    for row in _sheet_rows():
        if len(row) < 8:
            continue
        try:
            if int(row[4]) == kANDa and int(row[5]) == prashna and int(row[6]) == anuvAka:
                return row[3] == "2" or "ब्राह्मण" in row[7]
        except ValueError:
            continue
    return False


def _is_commentary(line):
    match = COMMENTARY_PATTERN.match(line)
    if match:
        return match.group(1)
    return None


def _is_vishvasa(line):
    return (
        (line.startswith("<details") and VISHVASA_PATTERN.search(line))
        or (line.startswith('<div class="js_include"') and "vishvAsa-prastutiH" in line)
    )


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


def separate_viniyogas(md_file):
    """Move viniyoga text out of Sāyaṇa/Bhaṭṭa-Bhāskara commentary blocks into विनियोगः blocks before the corresponding विश्वास-प्रस्तुतिः block or include."""
    if is_brAhmaNam_anuvAka(md_file):
        return
    metadata, content = md_file.read()
    lines = content.split("\n")
    output = []
    index = 0
    div_depth = 0
    sangraha_texts = []

    while index < len(lines):
        line = lines[index]
        if line.startswith('<div class="js_include"'):
            div_depth += 1
            output.append(line)
            index += 1
            continue
        if div_depth > 0:
            if "</div>" in line:
                div_depth -= 1
            output.append(line)
            index += 1
            continue

        commentary_label = _is_commentary(line)
        if commentary_label:
            end = index + 1
            while end < len(lines) and lines[end].strip() != "</details>":
                end += 1
            if end < len(lines):
                viniyoga, remaining = _extract_viniyoga(lines[index + 1:end])
                sangraha_lines = []
                for sangraha_index, sangraha_line in enumerate(remaining):
                    if sangraha_line.strip().startswith("अत्र विनियोगसंग्रहः"):
                        sangraha_lines = remaining[sangraha_index:]
                        remaining = remaining[:sangraha_index]
                        break
                if viniyoga:
                    vishvasa_index = None
                    for candidate in range(len(output) - 1, -1, -1):
                        if _is_vishvasa(output[candidate]):
                            vishvasa_index = candidate
                            break
                    if vishvasa_index is not None:
                        title = "भास्करोक्त-विनियोगः" if commentary_label == "भट्टभास्कर-टीका" else "सायणोक्त-विनियोगः"
                        output[vishvasa_index:vishvasa_index] = [
                            f"<details><summary>{title}</summary>",
                            "",
                            viniyoga,
                            "</details>",
                            "",
                        ]
                        output.append(line)
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
