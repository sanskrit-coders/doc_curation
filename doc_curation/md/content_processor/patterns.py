# Can't have look-behind (?<=\n|^) because: "Invalid regular expression: look-behind requires fixed-width pattern" (Which regex environment??)
PATTERN_SHLOKA = r"(?<=\n)([^#\s<>\[\(][\s\S]+?)॥\s*([०-९\d\.]+)\s*॥.*?(?=\n|$)"
PATTERN_2LINE_SHLOKA = r"(?<=\n|^)([^#\s<>\[\(][ \S]+?)।  +\n([^#\s<>\[\(][ \S]+?)॥\s*([०-९\d\.]+)\s*॥.*?(?=\n|$)"

FOOTNOTE_DEFINITION = r"\n(\[\^.+?\]):[\s\S]+?(?=[\n\[])"

JS_COMMENTS = r"\+\+\+\([\s\S]+?\)\+\+\+"

DEVANAGARI = r"[\u0900-ॿ]"
DEVANAGARI_NON_DIGITS = r"[\u0900-॥॰-ॿ]"
DEVANAGARI_NON_DIGITS_NON_DANDA = r"[\u0900-ॣ॰-ॿ]"
DEVANAGARI_OR_LATIN_WORD = r"[\u0900-\u097F\w]+"
DEVANAGARI_NON_MATRA = r"[\u0900-हॐ-ॡॲ-ॿ़]"
DEVANAGARI_MATRA = r"[ऺऻा-ॏॢॣ]"
DEVANAGARI_DIGITS = "[०-९]"
LOWER_CASE_ISO = "[a-zāīūṛr̥ēōṅñṇṭḍṣśḷṁṃḥḻṉṟäü]"
UPPER_CASE_ISO = "[A-ZĀĪŪṚR̥ĒŌṄÑṆṬḌṢŚḶṀṂḤḺṈṞÜ]"


def get_word_count(md_file, wc=None):
  if wc is None:
    from wordcloud import WordCloud
    wc = WordCloud()
  (metadata, content) = md_file.read()
  return wc.process_text(content)
