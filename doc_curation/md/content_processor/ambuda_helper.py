import regex

def replace_tags(content):
  content = regex.sub("<error>[^<]*?</error>", "", content)
  content = regex.sub("<flag>([^<]*?)</flag>", r"\1[??]", content)
  return content