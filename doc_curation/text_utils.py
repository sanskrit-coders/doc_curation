import doc_curation.md.content_processor.sanskrit_helper
from indic_transliteration import sanscript
import regex


def remove_parenthized_text(text):
  text = regex.sub(r"\[[^\]]+?\]", "", text)
  text = regex.sub(r"\+\+\+\([^)]+?\)\+\+\+", "", text)
  text = regex.sub(r"\([^)]+?\)", "", text)
  return text


def title_from_text(text, num_words=2, target_title_length=24, depunctuate=True, title_id=None, script=sanscript.DEVANAGARI):
  from indic_transliteration import detect
  from doc_curation.md.content_processor.sanskrit_helper import fix_lazy_anusvaara
  if script is None:
    script = detect.detect(text=text)
  if depunctuate:
    devanaaagari_scheme = sanscript.SCHEMES[sanscript.DEVANAGARI]
    text = devanaaagari_scheme.remove_svaras(in_string=text)
    text = devanaaagari_scheme.remove_punctuation(in_string=text)
  text = remove_parenthized_text(text)
  text = fix_lazy_anusvaara(text=text, script=script)
  init_words = text.split()[0:num_words]
  title = None
  if len(init_words) > 0:
    title = " ".join(init_words)
    if target_title_length is not None:
      # TODO: Call get_approx_deduplicating_key ?
      while len(title) > target_title_length and len(title.split()) > 1:
        title = " ".join(title.split()[:-1])
    title = sanscript.SCHEMES[script].replace_terminal_anusvaara(data_in=title)
  if title_id is not None:
    title = "%s %s" % (title_id, title)
  return title
