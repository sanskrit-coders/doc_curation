import regex
from indic_transliteration import sanscript, sacred_texts_scheme


def deduce_root(text):
  root = regex.sub(r"([^ा]+)(ः|ं|म्)$", r"\1", text)
  root = regex.sub(r"(.+)(श्रव|मन)ाः$", r"\1\2स्", root)
  root = regex.sub(r"(.+)(त्म|शर्म)ा$", r"\1\2न्", root)
  return root


def fix_bad_anunaasikas(text):
  # Beware of निम्न नृम्ण, गम्यते, तन्मध्य, अस्मिन्काले, मृण्मय, प्राङ्मुखं etc.. - so can't do - r"(?<!्)म्(\**[क-नय-ह])": r"ं\1" etc..
  replacements = {r"[ञणम](्[क-घ])": r"ङ\1", r"[ङनणम](्[च-झ])": r"ञ\1", r"[ञङनम](्[ट-ढ])": r"ण\1", r"म्([श])": r"ं\1", r"ं$": "म्", r"ं(\**\s*[अ-औ।॥])": r"म्\1", r"म्(\**\s+[क-नय-ह])": r"ं\1", }
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_lazy_anusvaara(text, script=sanscript.DEVANAGARI):
  text = regex.sub("ं+", "ं", text)
  text = regex.sub("ंऽ", "ऽं", text)
  text = regex.sub("ं(?= +[।॥])", "म्", text)
  text = sanscript.SCHEMES[script].fix_lazy_anusvaara(text, ignore_padaanta=True, omit_yrl=True)
  return text


def fix_bad_visargas(text):
  replacements = {r"(?<=[ि-ौ])ः(?=\s+[अ-औगघङजझञदधनडढणबभमयलवह])": r"र्", r"(?<=[ा])ः(?=\s+[अ-औगघङजझञदधनडढणबभमयरलवह])": r"", r"(?<=[क-ह])ः(\s+)अ": r"ो\1ऽ", r"ः(?=\s+[चछ])": r"श्", r"ः(?=\s+[टठ])": r"ष्", r"ः(?=\s+[तथ])": r"स्", r"(?<=[क-ह])ः(?=\s+[आ-औ])": r"", r"(?<=[क-ह])ः(?=\s*ऽ)": r"ो", }
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_bad_vyanjanaantas(text):
  replacements = {r"त्(?=\s+[चछ])": r"च्", r"त्(?=\s+[जझ])": r"ज्", r"त्(?=\s+[टठ])": r"ट्", r"त्(?=\s+[डढ])": r"ड्", r"त्(?=\s+[अ-औगघदधबभयरलव])": r"द्", r"त्(?=\s+[मन])": r"न्"}
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_yaNs(text):
  replacements = { r"[ुू](?=\s+[अ-ईऋ-औ])": r"्व्", r"[िी](?=\s+[अआउ-औ])": r"्य्", r"[ृॄ](?=\s+[अ-ऊऌ-औ])": r"्र्", r"[ॢॣ](?=\s+[अ-ॠए-औ])": r"्ल्", }
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_anunaasikaadi(text, level=0):
  text = fix_bad_anunaasikas(text)
  text = fix_lazy_anusvaara(text)
  text = fix_bad_vyanjanaantas(text)
  if level > 0:
    text = fix_yaNs(text)
    text = fix_bad_vyanjanaantas(text)
  return text

def numerify_shloka_numbering(text, encoding="कखगघङचछजझञ"):
  def transformer(match):
    return "॥%s.%d॥" % (match.group(1), encoding.index(match.group(2)) + 1)
  c = regex.sub(r"॥ *(\d+)[ (]*([%s])[ )]*॥" % encoding, transformer, text)
  return c

def undo_gretil_analysis(text):
  """
  Given text like: "अस्मिन्.वै.लोक.उभये.देव.मनुष्या.आसुः  । ते.देवाः.स्वर्गल्ँ.लोकम्.यन्तो.अग्निम्.ऊचुः  । ",  
  produce : "अस्मिन् वै लोक उभये देव मनुष्या आसुः  । ते देवाः स्वर्गल्ँ लोकं यन्तो ऽग्निम् ऊचुः  । ", 
  though, ideally, it ought to be "देव-मनुष्या". 
  
  :param text: 
  :return: 
  """
  text = text.replace("ंल्", "ल्ँ")
  text = regex.sub(r"म्[\. ]+(?=[अ-औ])", text)
  return text


def seperate_uvaacha(text):
  text = regex.sub(r"वाच॥\s*", r"वाच॥\n\n", text)
  return text


def fix_repha_duplication(text):
  text = regex.sub("र्क्ख्", "र्ख्", text)
  text = regex.sub("र्ग्घ्", "र्घ्", text)
  text = regex.sub("र्च्छ्", "र्छ्", text)
  text = regex.sub("र्ज्झ्", "र्झ्", text)
  text = regex.sub("र्त्थ्", "र्थ्", text)
  text = regex.sub("र्द्ध्", "र्ध्", text)
  text = regex.sub("र्ड्ढ्", "र्ढ्", text)
  text = regex.sub("र्प्फ्", "र्फ्", text)
  text = regex.sub("र्ब्भ्", "र्भ्", text)
  text = regex.sub("र्व्व", "र्व", text)
  text = regex.sub("र्य्य", "र्य", text)
  text = regex.sub(r"र्([ङञणनमयवशषसहल])्\1", r"र्\1", text)
  return text


def fix_sacred_texts_transliteration(text):
  def italicized_fixer(match):
    return sacred_texts_scheme.decode_italicized_text(match.group(1))

  text = regex.sub("_(..?)_", italicized_fixer, text)
  text = sacred_texts_scheme.decode_nonitalicized(text)
  return text
