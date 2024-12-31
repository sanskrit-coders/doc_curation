import regex


def translate(text, source_language="en", dest_language="es", translator="google"):
  import translators
  if not regex.search(r"[^\d\s*&%\^$#@!~`';:\[\]{}\-]", text):
    return text
  return translators.translate_text(text, from_language=source_language, to_language=dest_language, translator=translator)


def translate_partwise(text, part_pattern=r"\n", result_pattern = "%s  \n{%s}\n", source_language="en", dest_language="es", translator="google"):
  result = ""
  parts = regex.split(part_pattern, text)
  for part in parts:
    if not regex.search(r"[^\d\s*&%\^$#@!~`';:\[\]{}\-]", part):
      result += part + "\n"
    else:
      result += result_pattern % (part, translate(part, source_language, dest_language, translator))
  return result
