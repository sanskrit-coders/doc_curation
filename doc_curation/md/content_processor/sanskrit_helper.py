import regex
from indic_transliteration import sanscript


def fix_bad_anunaasikas(text):
  # Beware of निम्न नृम्ण etc..
  replacements = {r"म्([च-ञ])": r"ञ्\1", r"म्([क-ङ])": r"ङ्\1", r"म्([ट-ढ])": r"ण्\1", r"म्([त-ध])": r"न्\1"}
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
  text = regex.sub("म्[\. ]+(?=[अ-औ])")
  return text