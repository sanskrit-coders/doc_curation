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


def fix_google_ocr(text):
  text = regex.sub(r"(?<=\n)[\-=]+ *(?=\n)", "", text)
  text = regex.sub("(?<=\n)([०-९\d]+) *(?=\n)", r"[[\1]]", text)
  text = regex.sub("(?<=[ँ-९]):", "ः", text)
  text = regex.sub(r"\|\|", "॥", text)
  text = regex.sub(r"\|", "।", text)
  text = regex.sub(r"।।", "॥", text)
  text = regex.sub("(?<=\S ?)\n", "\n\n", text)
  return text

def fix_mid_shloka_empty_lines(text):
  text = regex.sub(r"।\n\n+", "।  \n", text)
  return text

def misc_sanskrit_typos(text):
  text = regex.sub(r"\|\|", "॥", text)
  text = regex.sub(r"\|", "।", text)
  text = regex.sub(r"।।", "॥", text)
  text = regex.sub("[ञनम](्[क-घ])\n", r"ङ\1", text)
  text = regex.sub("[ङनम](्[च-झ])\n", r"ञ\1", text)
  text = regex.sub("[ञङम](्[त-न])\n", r"न\1", text)
  text = regex.sub("[ञनङ](्[प-म])\n", r"म्\1", text)
  return text

def fix_google_ocr_iast_iso(text):
  text = regex.sub("ş", "ṣ", text)
  text = regex.sub("ń(?=[kg])", "ṅ", text)
  text = regex.sub("ń(?=[cj])", "ñ", text)
  text = regex.sub("ņ", "ṇ", text)
  text = regex.sub("Š", "Ś", text)
  text = regex.sub("Ş", "Ṣ", text)
  text = regex.sub("š", "ś", text)
  text = regex.sub("ș", "ṣ", text)
  text = regex.sub("ț|ṱ", "ṭ", text)
  text = regex.sub("Ç", "Ś", text)
  text = regex.sub("ç", "ś", text)
  text = regex.sub("ḑ", "ḍ", text)
  text = regex.sub("ä|ă", "ā", text)
  text = regex.sub("ü", "ū", text)
  text = regex.sub("(?<=[a-z])\- +(?=[a-z])", "", text)
  return text
