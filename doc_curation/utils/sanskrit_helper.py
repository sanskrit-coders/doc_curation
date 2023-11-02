import regex
from indic_transliteration import sanscript


def deduce_root(text):
  root = regex.sub(r"([^ा]+)(ः|ं|म्)$", r"\1", text)
  root = regex.sub(r"(.+)(श्रव|मन)ाः$", r"\1\2स्", root)
  root = regex.sub(r"(.+)(त्म|शर्म)ा$", r"\1\2न्", root)
  return root


def fix_bad_anunaasikas(text):
  # Beware of निम्न नृम्ण, गम्यते etc..
  replacements = {r"म्([च-ञ])": r"ञ्\1", r"म्([क-ङ])": r"ङ्\1", r"म्([ट-ढ])": r"ण्\1", r"म्([त-ध])": r"न्\1", r"म्([श])": r"ं\1", r"ं$": "म्", r"ं(\**\s+[अ-औ।॥])": r"म्\1", r"म्(\**\s+[क-नय-ह])": r"ं\1"}
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_lazy_anusvaara(text, script=sanscript.DEVANAGARI):
  text = regex.sub("ंऽ", "ऽं", text)
  text = sanscript.SCHEMES[script].fix_lazy_anusvaara(text, ignore_padaanta=True, omit_yrl=True)
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
  text = regex.sub("म्[\. ]+(?=[अ-औ])", text)
  return text


def seperate_uvaacha(text):
  text = regex.sub("वाच॥\s*", "वाच॥\n\n", text)
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
  