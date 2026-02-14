import regex

def get_quote_level(line):
  """
  Calculates the nesting level of a markdown blockquote line.
  For example, '>> quote' is level 2.
  """
  # Match one or more '>' characters, each possibly followed by a space
  match = regex.match(r'^(>\s*)+', line)
  if not match:
    return 0
  # The level is the number of '>' characters found
  return match.group(0).count('>')

def strip_quote_markers(line):
  """Removes all markdown quote markers (e.g., '>', '>> ') from a line."""
  # Repeatedly strip one level of quote marker until none are left
  while line.lstrip().startswith('>'):
      line = line.lstrip()[1:].lstrip()
  return line

def convert_markdown_to_latex_leftbar(content):
  """
  Converts a string with markdown blockquotes (including nested ones)
  to a LaTeX string using the appropriate nested {leftbar} environments.

  Args:
    content: A string containing text with markdown blockquotes.

  Returns:
    A string formatted for LaTeX with {leftbar} environments.
  """
  lines = content.split('\n')
  latex_lines = []
  current_level = 0

  for line in lines:
    line_level = get_quote_level(line)

    # 1. Close environments if the nesting level has decreased
    while line_level < current_level:
      latex_lines.append(r'\end{leftbar}')
      current_level -= 1

    # 2. Open new environments if the nesting level has increased
    while line_level > current_level:
      latex_lines.append(r'\begin{leftbar}')
      current_level += 1

    # 3. Add the processed line content (with '>' markers removed)
    processed_line = strip_quote_markers(line)
    latex_lines.append(processed_line)

  # 4. Close any remaining open environments at the end of the text
  while current_level > 0:
    latex_lines.append(r'\end{leftbar}')
    current_level -= 1

  return '\n'.join(latex_lines)
