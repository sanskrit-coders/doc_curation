from indic_transliteration import sanscript
import regex

def title_from_text(text, num_words=2, target_title_length=24, depunctuate=True, title_id=None):
  text = regex.sub("\+\+\+\(.+?\)\+\+\+", "", text)
  init_words = text.split()[0:num_words]
  title = None
  if len(init_words) > 0:
    title = " ".join(init_words)
    if depunctuate:
      devanaaagari_scheme = sanscript.SCHEMES[sanscript.DEVANAGARI]
      title = devanaaagari_scheme.remove_svaras(in_string=title)
      title = devanaaagari_scheme.remove_punctuation(in_string=title)
      title = devanaaagari_scheme.fix_lazy_anusvaara(data_in=title, omit_yrl=True)
      if target_title_length is not None:
        # TODO: Call get_approx_deduplicating_key ?
        while len(title) > target_title_length and len(title.split()) > 1:
          title = " ".join(title.split()[:-1])
  if title_id is not None:
    title = "%s %s" % (title_id, title)
  return title
