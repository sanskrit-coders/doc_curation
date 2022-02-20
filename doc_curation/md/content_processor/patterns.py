
# Can't have look-behind (?<=\n|^) because: Invalid regular expression: look-behind requires fixed-width pattern
PATTERN_SHLOKA = r"\n([^#\s<>\[\(][\s\S]+?)॥\s*([०-९\d\.]+)\s*॥.*?(?=\n|$)"

FOOTNOTE_DEFINITION = r"\n(\[\^.+?\]):[\s\S]+?(?=[\n\[])"

JS_COMMENTS = r"\+\+\+\([\s\S]+?\)\+\+\+"