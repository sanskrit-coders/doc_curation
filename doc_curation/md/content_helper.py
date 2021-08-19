import logging

import regex


def make_paras(content):
  lines = content.splitlines(keepends=False)
  lines_out = [""]
  for line in lines:
    line = line.rstrip()
    previous_line = lines_out[-1]
    if line == "":
      lines_out.append(line)
    elif regex.fullmatch("^[#>\-\+\*].+",  line):
      if not regex.fullmatch("^[#>\-\*].+",  previous_line):
        lines_out.append("")
      lines_out.append(line)
    else:
      if regex.fullmatch(".+\.",  previous_line):
        lines_out.append("")
        lines_out.append(line)
      else:
        if not regex.fullmatch("^[#>\-\*].+[^.]",  previous_line) and previous_line.strip() != "":
          lines_out[-1] = "%s %s" % (previous_line, line)
          lines_out[-1] = lines_out[-1].strip()
        else:
          lines_out.append(line)
  return "\n".join(lines_out)


def transform_footnote_marks(content, transformer):
  content = regex.sub("\[\^(.+?)\]", transformer, content)
  return content


def define_footnotes_near_use(content):
  # For correct regex matching.
  content = "\n%s\n\n" % content
  definition_pattern = "\n(\[\^.+?\]):[\s\S]+?\n(?=[\n\[])"
  definitions = regex.finditer(definition_pattern, content)
  content = regex.sub(definition_pattern, "", content)
  for definition in definitions:
    content = regex.sub("%s.+\n\n" % regex.escape(definition.group(1)), "\g<0>%s\n" % definition.group(0), content)
  # Undo initial additions
  content = regex.sub("^\n", "", content)
  content = regex.sub("\n\n$", "", content)
  return content