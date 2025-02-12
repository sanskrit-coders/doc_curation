import regex


def fix_iast_for_pdfs(text):
  # When Google Drive api is used to extract text from copy-pasteable pdfs, certain replacements are needed to recover proper text.
  from doc_curation.utils import patterns
  text = regex.sub(rf"(n *\. *)(?={patterns.LOWER_CASE_ISO})", "ṇ", text)
  text = regex.sub(rf"( *\˙n)(?=[kg])", "ṇ", text)
  text = regex.sub(rf"(N *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṇ", text)

  text = regex.sub(rf"(c *\. *)(?={patterns.LOWER_CASE_ISO})", "c̣", text)
  text = regex.sub(rf"(C *\. *)(?={patterns.LOWER_CASE_ISO})", "C̣", text)
  text = regex.sub(rf"(d *\. *)(?={patterns.LOWER_CASE_ISO})", "ḍ", text)
  text = regex.sub(rf"(D *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḍ", text)

  text = regex.sub(rf"(t *\. *)(?={patterns.LOWER_CASE_ISO})", "ṭ", text)
  text = regex.sub(rf"(T *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṭ", text)

  text = regex.sub(rf"(s *\. *)(?={patterns.LOWER_CASE_ISO})", "ṣ", text)
  text = regex.sub(rf"(S *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṣ", text)

  text = regex.sub(rf"(l *\. *)(?={patterns.LOWER_CASE_ISO})", "ḷ", text)
  text = regex.sub(rf"(L *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḷ", text)

  text = regex.sub(rf"(r *\. *)(?={patterns.LOWER_CASE_ISO})", "r̥", text)
  text = regex.sub(rf"(R *\. *)(?={patterns.UPPER_CASE_ISO})", "R̥", text)

  text = regex.sub(rf"(h *\. *)(?={patterns.LOWER_CASE_ISO})", "ḥ", text)
  text = regex.sub(rf"(h *\. *)(?=[|:,])", "ḥ", text)
  text = regex.sub(rf"(H *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḥ", text)

  text = regex.sub(rf"(m *\. *)(?={patterns.LOWER_CASE_ISO})", "ṁ", text)
  text = regex.sub(rf"( *˙m)", "ṁ", text)
  # text = regex.sub(rf"(m *\. *)(?=[|:,])", "ṁ", text)
  text = regex.sub(rf"(M *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṁ", text)

  text = regex.sub(rf"(K\.)(?={patterns.LOWER_CASE_ISO})", "Ḳ", text)
  text = regex.sub(rf"(k\.)(?={patterns.LOWER_CASE_ISO})", "ḳ", text)

  text = regex.sub("¯\s*a", "ā", text)
  text = regex.sub("¯\s*i", "ī", text)
  text = regex.sub("¯?ı", "ī", text)
  text = regex.sub("¯\s*u", "ū", text)
  text = regex.sub("¯r̥", "r̥̄", text)
  text = regex.sub("¯l̥", "l̥̄", text)
  text = regex.sub("¯\s*A", "Ā", text)
  text = regex.sub("¯\s*I", "Ī", text)
  text = regex.sub("¯\s*U", "Ū", text)
  
  # The below are rarer, so substituted later.
  text = regex.sub("¯\s*e", "ē", text)
  text = regex.sub("¯\s*o", "ō", text)
  text = regex.sub("l¯", "ḻ", text)
  text = regex.sub("n¯", "ṉ", text)
  text = regex.sub("N¯", "Ṉ", text)
  text = regex.sub("r¯", "ṟ", text)
  text = regex.sub("R¯", "ṟ", text)


  text = regex.sub("¨a", "ä", text)
  text = regex.sub("¨A", "Ä", text)
  text = regex.sub("¨u", "ü", text)
  text = regex.sub("¨U", "Ü", text)

  text = regex.sub("˜n", "ñ", text)
  text = regex.sub("˜N", "Ñ", text)

  return text


def fix_google_ocr_devanaagarii(text, new_line_substitute="\n\n"):
  text = fix_dandas(text)
  text = regex.sub(r"(?<=\n)[\-=]+ *(?=\n)", "", text)
  text = regex.sub("(?<=\n)([०-९\d]+) *(?=\n)", r"[[\1]]", text)
  text = regex.sub("(?<=[ँ-९]):", "ः", text)
  text = regex.sub("(?<=\S ?)\n", new_line_substitute, text)
  text = regex.sub("(?<=[a-zA-Z])\- +(?=[a-zA-Z])", "", text)
  return text

def fix_mid_shloka_empty_lines(text):
  text = regex.sub(r"।\n\n+", "।  \n", text)
  return text

def fix_dandas(text):
  text = regex.sub("ll(?= +\n|$)", "॥", text)
  text = regex.sub("l(?= +\n|$)", "।", text)
  text = regex.sub(r"\|\|", "॥", text)
  # Pipes are used in md tables. So, taking care below.
  lines = text.split("\n")
  lines_out = []
  for line in lines:
    if line.strip().startswith("|") and line.strip().endswith("|"):
      lines_out.append(line)
    else:
      lines_out.append(regex.sub(r"\|", "।", line))
  text = "\n".join(lines_out)
  text = regex.sub(r"।।।+", r"…", text)
  text = regex.sub(r"।।", "॥", text)
  return text


def fix_tables(text):
  # Fix md tables with pipes and colons erroneously transliterated
  lines = text.split("\n")
  lines_out = []
  for line in lines:
    if len(line.strip()) >= 2 and line.strip()[0] in ("|", "।") and line.strip()[-1] in ("|", "।"):
      l = regex.sub(r"।", "|", line)
      l = regex.sub("-ः", "-:", l)
      l = regex.sub("ः-", ":-", l)
      lines_out.append(l)
    else:
      lines_out.append(line)
  return "\n".join(lines_out)

def misc_manipravaala_typos(text):
  text = fix_dandas(text)
  text = regex.sub("[ञनम](्[क-घ])\n", r"ङ\1", text)
  text = regex.sub("[ङनम](्[च-झ])\n", r"ञ\1", text)
  text = regex.sub("[ञङम](्[त-न])\n", r"न\1", text)
  text = regex.sub("[ञनङ](्[प-म])\n", r"म्\1", text)
  # text = regex.sub(":-", "--", text)
  text = regex.sub("(?<=[ँ-ॣ]):", "ः", text)
  text = regex.sub("(?<=[ँ-ॣ])[sS]", "ऽ", text)
  return text

def misc_sanskrit_typos(text):
  text = misc_manipravaala_typos(text=text)
  text = regex.sub("ळ", "ल", text)
  text = regex.sub("(?<=[ँ-९]):", "ः", text)
  # text = regex.sub("(?<=[ँ-ॣ])\- +(?=[ँ-ॣ])", "", text)
  return text

def fix_avagraha_quotations(text):
  text = regex.sub("(?<=\s)ऽ", "\"", text)
  text = regex.sub("ऽ(?=\s)", "\"", text)
  return text

def replace_casewise(text, pattern, replacement):
  text = regex.sub(pattern.lower(), replacement.lower(), text)
  text = regex.sub(pattern.upper(), replacement.upper(), text)
  return text


def fix_google_ocr_iast_iso(text):
  text = replace_casewise(text, "ş", "ṣ")
  text = regex.sub("ń(?=[kg])", "ṅ", text)
  text = regex.sub("ń(?=[cj])", "ñ", text)
  text = replace_casewise(text, "ņ", "ṇ")
  text = replace_casewise(text, "Š|Ç", "Ś")
  text = replace_casewise(text, "Ş|ș", "Ṣ")
  text = replace_casewise(text, "ț|ṱ", "ṭ")
  text = replace_casewise(text, "ḑ", "ḍ")
  text = replace_casewise(text, "ä|ă|å|Ã", "ā")
  text = replace_casewise(text, "ü|û", "ū")
  text = replace_casewise(text, "Ï|ī|î", "Ī")
  text = regex.sub("(?<=[a-z])\- +(?=[a-z])", "", text)
  return text


def strip_word_continuation_dashes(text):
  text = regex.sub("(?<=\S)\- +(?=\S)", "", text)
  return text

def fix_typos(text):
  import doc_curation
  typos_df = pandas.read_csv(os.path.join(os.path.dirname(doc_curation.__file__), "data/ocr_typos/sa/iast/manual.tsv"), sep="\t")
  typos_df = typos_df.set_index("correct")
  for typo in tqdm.tqdm(typos_df.index):
    ta_words = typos_df.loc[typo, "typo"].split(",")
    for ta_word in ta_words:
      text = text.replace(ta_word, sa_word)
  return text


def fix_foxit(text):
  text = regex.sub(r"(\S) ᐀्", r"र्\1", text)
  return text

def fix_poppler_ocular(text):
  text = regex.sub(r"([ \-])\�(([क-ह]्)*([क-ह]))(?<![ा-ॏ])", r"\1\2ि", text)
  text = regex.sub("(([क-ह]्)*([क-ह][ा-ॏ]?))\�(?=[ \-])", r"र्\1", text)
  return text

def fix_dangling_maatraas(text):
  text = regex.sub(r"(\*+)(\s+)([ऀ-ःऺ-ॏ])", r"\3\1", text)
  return text

def fix_pandoc_md(text):
  text = regex.sub(r" ", r" ", text)
  text = regex.sub(r"\\\*", r"_", text)
  text = regex.sub(r"\\_", r"_", text)
  text = regex.sub("(?<=\n) +", "", text)
  text = regex.sub("\*\*\*\*", "", text)
  from doc_curation.md.content_processor import space_helper
  text = space_helper.fix_markup(text=text)
  return text