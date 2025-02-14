# Can't have look-behind (?<=\n|^) because: "Invalid regular expression: look-behind requires fixed-width pattern" (Which regex environment??)
from indic_transliteration.sanscript.schemes.brahmic import accent

PATTERN_NUM_SUTRA = r"(?<=\n)([०-९]+) +.+(?=\n|$)"
PATTERN_SHLOKA = r"(?<=\n)([^#\s<>\[\(][^#<>]+?)॥\s*([०-९\d\.]+)\s*॥.*?(?=\n|$)"
PATTERN_2LINE_SHLOKA = r"(?<=\n|^)([^#\s<>\[\(][ \S]+?)।  +\n([^#\s<>\[\(][ \S]+?)[।॥ ]+\s*([०-९\d\.]+)\s*[।॥ ].*?(?=\n|$)"
PATTERN_2LINE_SHLOKA_NUM_END = r"(?<=\n|^)([^#\s<>\[\(][ \S]+?)।?  +\n([^#\s<>\[\(][ \S]+?)\s*([०-९\d\.]+)\s*[।॥ ]*?(?=\n|$)"
PATTERN_2LINE_SHLOKA_2LINE_SEP_NUM_END = r"(?<=\n|^)([^#\s<>\[\(][ \S]+?)।? *\n\n([^#\s<>\[\(][ \S]+?)\s*([०-९\d\.]+)\s*[।॥ ]*?(?=\n|$)"
PATTERN_2LINE_SHLOKA_NO_NUM = r"(?<=\n|^)([^#\s<>\[\(][ \S]+?)।  +\n([^#\s<>\[\(][ \S]+?)[॥।].*?(?=\n|$)"
PATTERN_4LINE_SHLOKA_2LINE_SEP_NUM_END = r"(?<=\n|^)([^#\s<>\[\(][ \S]+?) *\n\n([^#\s<>\[\(][ \S]+?) *। *\n\n([^#\s<>\[\(][ \S]+?) *\n\n([^#\s<>\[\(][ \S]+?)\s*([०-९\d\.]+)\s*[।॥ ]*?(?=\n|$)"
PATTERN_MULTI_LINE_SHLOKA_DOUBLE_DANDA = r"(?<=\n|^)(([^#\s<>\[][ \S]+?)।?  +\n)+?([^#\s<>\[\(][ \S]+?)॥(.*?)(?=\n|$)"
PATTERN_4LINE_SHLOKA = r"(?<=\n|^)(([^#\s<>\[][ \S]+?)।?  +\n){3}([^#\s<>\[\(][ \S]+?)॥ *([०-९\d\.\-–]+) *॥?.*?(?=\n|$)"
PATTERN_MULTI_LINE_SHLOKA = fr"(?<=\n|^)(([^#\s<>\[][ \S]+?)।?  +\n)+?([^#\s<>\[\(][ \S]+?)॥ *([०-९\d\.\-–]+) *॥?.*?(?=\n|$)"
PATTERN_MULTI_LINE_SHLOKA_BOLDED = r"(?<=\n|^)\*\*(([^#\s<>\[][ \S]+?)।?  +\n){1,3}([^#\s<>\[\(][ \S]+?)॥ *([०-९\d\.]+) *॥\*\*.*?(?=\n|$)"

## * instead of {1,4} would lead to timeouts.
PATTERN_DANDA_END_SHLOKA = r"(?<=\n|^)([^#\s<>\[\(][ \S।॥]+?[।॥\s]*){1,4}॥\s*([०-९\d\.]+)\s*॥"

PATTERN_BOLDED_QUOTED_SHLOKA = r"(?<=\n\n|^)\> \*\*([\s\S]+?[०-९ ]+॥.*)(?=\n\n)"

FOOTNOTE_DEFINITION = r"\n(\[\^.+?\]):[\s\S]+?(?=[\n\[])"
SUMMARY = r"<summary>.+?</summary>"
DETAILS_SUMMARY = r"<summary>.+?</summary>"
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
ALL_DIGITS = r"[०-९\d೦-೯]"
DEVANAGARI_DANDAS = "[।॥]"
LOWER_CASE_ISO = "[a-zāīūṛr̥ēōṅñṇṭḍṣśḷṁṃḥḻṉṟäü]"
UPPER_CASE_ISO = "[A-ZĀĪŪṚR̥ĒŌṄÑṆṬḌṢŚḶṀṂḤḺṈṞÜ]"
ACCENTS = accent.ACCENTS_PATTERN
NON_DEV_PUNCT = r"[\.\(\)\[\],;+\*_\-:'\"]"
PUNCT = rf"[।॥{NON_DEV_PUNCT}]"

TAMIL = "[ஂ-௺]"
TAMIL_ENG_DIGITS = "[ஂ-௺0-9]" # \d matches ०-९ in py, but not in intellij!

DEVANAGARI_MANIPRAVALA_MID_K_L = f"(?<=[^\\s्])क(?={DEVANAGARI_MATRA}?ळ)"

