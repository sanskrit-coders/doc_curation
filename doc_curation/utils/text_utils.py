from indic_transliteration import sanscript
import regex
import editdistance
from doc_curation.utils import patterns


def remove_parenthized_text(text):
  text = regex.sub(r"\[[^\]]+?\]", "", text)
  text = regex.sub(r"\+\+\+\([^)]+?\)\+\+\+", "", text)
  text = regex.sub(r"\([^)]+?\)", "", text)
  return text


def title_from_text(text, num_words=2, target_title_length=24, depunctuate=True, title_id=None, script=sanscript.DEVANAGARI):
  from indic_transliteration import detect
  from doc_curation.utils.sanskrit_helper import fix_lazy_anusvaara
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


def normalized_edit_distance(a, b, strip_svaras):
  a = regex.sub(r"\s", "", a)
  b = regex.sub(r"\s", "", b)
  a = regex.sub(fr"{patterns.DEVANAGARI_DANDAS}|{patterns.DEVANAGARI_DIGITS}|\d|{patterns.PUNCT}", "", a)
  b = regex.sub(fr"{patterns.DEVANAGARI_DANDAS}|{patterns.DEVANAGARI_DIGITS}|\d|{patterns.PUNCT}", "", b)
  if strip_svaras:
    a = regex.sub(fr"{patterns.ACCENTS}", "", a)
    b = regex.sub(fr"{patterns.ACCENTS}", "", b)
  if a.strip() == b.strip():
    return 0
  return round(editdistance.eval(a, b)/max(len(a), len(b)), 3)


def edit_distance_match(a, b, cutoff=.001, strip_svaras=True):
  distance = normalized_edit_distance(a=a, b=b, strip_svaras=strip_svaras)
  return (distance < cutoff, distance)


def get_word_count(md_file, wc=None):
  if wc is None:
    from wordcloud import WordCloud
    wc = WordCloud()
  (metadata, content) = md_file.read()
  return wc.process_text(content)


def detect_vishvaasa_mods(content, cutoff=0.001):
  mod_likelihood = 0
  if "+++(" in content or "+++\\(" in content:
    mod_likelihood += 1
  else:
    if "**" in content:
      mod_likelihood += .5
    if "-" in content:
      mod_likelihood += .1
    if "<details>" in content:
      mod_likelihood += .25
  return (mod_likelihood >= cutoff, mod_likelihood)


def fix_svara_duplicates(text):
  for svara in "꣡꣢꣣꣯꣫" + "॒॑":
    text = regex.sub(f"{svara}{svara}+", svara, text)
  return text


def svara_post_yogavaaha(text):
  text = regex.sub(f"({patterns.ACCENTS})({patterns.DEVANAGARI_YOGAVAHA}+)", r"\2\1", text)
  return text
