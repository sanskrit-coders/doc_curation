import regex
from doc_curation.md.library.metadata_helper import title_from_text
from indic_transliteration import sanscript


def remove_non_content_text(content, remove_parenthized_text=True):
  # For correct regex matching.
  content = "\n%s\n\n" % content
  from doc_curation.utils import patterns
  # remove summary tags
  content = regex.sub(patterns.SUMMARY, "", content)
  # Remove remaining tags
  content = regex.sub("<[^>\n]+?>", "", content)
  # remove footnote definitions
  content = regex.sub(patterns.FOOTNOTE_DEFINITION, "", content)
  # Remove footnote markers
  content = regex.sub(r"\[\^.+?\]", "", content)
  # Remove section titles
  content = regex.sub(r"\n#.+?\n", "\n", content)
  # Remove quote markers
  content = regex.sub(r"\n> +", "\n", content)
  # Remove js comments
  content = regex.sub(patterns.JS_COMMENTS, "", content)
  if remove_parenthized_text:
    # Remove paranthesized text
    content = regex.sub(r"\(.+?\)", "", content)
  # Remove final digits
  content = regex.sub(r"[\d०-९]+\s*$", "", content)

  # Undo initial additions
  content = regex.sub(r"^\n", "", content)
  content = regex.sub(r"\n\n$", "", content)
  return content


def get_comparison_text(text):
  text = sanscript.SCHEMES[sanscript.DEVANAGARI].remove_numerals(in_string=text)
  text = title_from_text(text=text, num_words=40, target_title_length=1000, title_id=None)
  return text.strip()
