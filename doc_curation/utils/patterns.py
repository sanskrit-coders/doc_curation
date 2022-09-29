# Can't have look-behind (?<=\n|^) because: "Invalid regular expression: look-behind requires fixed-width pattern" (Which regex environment??)
PATTERN_SHLOKA = r"(?<=\n)([^#\s<>\[\(][\s\S]+?)॥\s*([०-९\d\.]+)\s*॥.*?(?=\n|$)"
PATTERN_2LINE_SHLOKA = r"(?<=\n|^)([^#\s<>\[\(][ \S]+?)।  +\n([^#\s<>\[\(][ \S]+?)॥\s*([०-९\d\.]+)\s*॥.*?(?=\n|$)"

FOOTNOTE_DEFINITION = r"\n(\[\^.+?\]):[\s\S]+?(?=[\n\[])"
SUMMARY = r"<summary>.+?</summary>"
DETAILS = r"<details>.+?</details>"

JS_COMMENTS = r"\+\+\+\([\s\S]+?\)\+\+\+"

DEVANAGARI = r"[\u0900-ॿ]"
DEVANAGARI_NON_DIGITS = r"[\u0900-॥॰-ॿ]"
DEVANAGARI_NON_DIGITS_NON_DANDA = r"[\u0900-ॣ॰-ॿ]"
DEVANAGARI_OR_LATIN_WORD = r"[\u0900-\u097F\w]+"
DEVANAGARI_NON_MATRA = r"[\u0900-हॐ-ॡॲ-ॿ़]"
DEVANAGARI_MATRA = r"[ऺऻा-ॏॢॣ]"
DEVANAGARI_YOGAVAHA = "[\u0900-\u0903\uA8F2-\uA8F7ᳩ-ᳶ]"
DEVANAGARI_MATRA_YOGAVAHA = r"[ऺऻा-ॏॢॣ\u0900-\u0903\uA8F2-\uA8F7ᳩ-ᳶ]"
DEVANAGARI_DIGITS = "[०-९]"
DEVANAGARI_DANDAS = "[।॥]"
LOWER_CASE_ISO = "[a-zāīūṛr̥ēōṅñṇṭḍṣśḷṁṃḥḻṉṟäü]"
UPPER_CASE_ISO = "[A-ZĀĪŪṚR̥ĒŌṄÑṆṬḌṢŚḶṀṂḤḺṈṞÜ]"
ACCENTS = "[\u1CD0-\u1CE8\u1CF9\u1CFA\uA8E0-\uA8F1\u0951-\u0954\u0957]" # included  ॗ , which is used as svara for weber's shatapatha
PUNCT = "[।॥\.\(\)\[\],;+\*_\-:]"

DEVANAGARI_MANIPRAVALA_MID_K_L = f"(?<=[^\s्])क(?={DEVANAGARI_MATRA}?ळ)"

