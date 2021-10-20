from indic_transliteration import sanscript
import regex


def remove_parenthized_text(text):
  text = regex.sub("\[[^\]]+?\]", "", text)
  text = regex.sub("\+\+\+\([^)]+?\)\+\+\+", "", text)
  text = regex.sub("\([^)]+?\)", "", text)
  return text


def title_from_text(text, num_words=2, target_title_length=24, depunctuate=True, title_id=None, script=sanscript.DEVANAGARI):
  if depunctuate:
    devanaaagari_scheme = sanscript.SCHEMES[sanscript.DEVANAGARI]
    text = devanaaagari_scheme.remove_svaras(in_string=text)
    text = devanaaagari_scheme.remove_punctuation(in_string=text)
  text = remove_parenthized_text(text)
  text = sanscript.SCHEMES[script].fix_lazy_anusvaara(data_in=text, omit_yrl=True)
  init_words = text.split()[0:num_words]
  title = None
  if len(init_words) > 0:
    title = " ".join(init_words)
    if target_title_length is not None:
      # TODO: Call get_approx_deduplicating_key ?
      while len(title) > target_title_length and len(title.split()) > 1:
        title = " ".join(title.split()[:-1])
  if title_id is not None:
    title = "%s %s" % (title_id, title)
  return title
