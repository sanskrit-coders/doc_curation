import regex


def fix_iast_gb(text):
  # When Google Drive api is used to extract text from copy-pasteable pdfs, certain replacements are needed to recover proper text.
  from doc_curation.utils import patterns
  text = regex.sub(f"(n *\. *)(?={patterns.LOWER_CASE_ISO})", "ṇ", text)
  text = regex.sub(f"(N *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṇ", text)

  text = regex.sub(f"(d *\. *)(?={patterns.LOWER_CASE_ISO})", "ḍ", text)
  text = regex.sub(f"(D *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḍ", text)

  text = regex.sub(f"(t *\. *)(?={patterns.LOWER_CASE_ISO})", "ṭ", text)
  text = regex.sub(f"(T *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṭ", text)

  text = regex.sub(f"(s *\. *)(?={patterns.LOWER_CASE_ISO})", "ṣ", text)
  text = regex.sub(f"(S *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṣ", text)

  text = regex.sub(f"(l *\. *)(?={patterns.LOWER_CASE_ISO})", "ḷ", text)
  text = regex.sub(f"(L *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḷ", text)

  text = regex.sub(f"(r *\. *)(?={patterns.LOWER_CASE_ISO})", "r̥", text)
  text = regex.sub(f"(R *\. *)(?={patterns.UPPER_CASE_ISO})", "R̥", text)

  text = regex.sub(f"(h *\. *)(?={patterns.LOWER_CASE_ISO})", "ḥ", text)
  text = regex.sub(f"(h *\. *)(?=[|:,])", "ḥ", text)
  text = regex.sub(f"(H *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḥ", text)

  text = regex.sub(f"(m *\. *)(?={patterns.LOWER_CASE_ISO})", "ṁ", text)
  # text = regex.sub(f"(m *\. *)(?=[|:,])", "ṁ", text)
  text = regex.sub(f"(M *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṁ", text)

  text = regex.sub("¯a", "ā", text)
  text = regex.sub("¯i", "ī", text)
  text = regex.sub("¯u", "ū", text)
  text = regex.sub("¯r̥", "r̥̄", text)
  text = regex.sub("¯l̥", "l̥̄", text)
  text = regex.sub("¯A", "Ā", text)
  text = regex.sub("¯I", "Ī", text)
  text = regex.sub("¯U", "Ū", text)
  
  # The below are rarer, so substituted later.
  text = regex.sub("¯e", "ē", text)
  text = regex.sub("¯o", "ō", text)
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
  text = regex.sub("^-+", "", text)
  text = regex.sub("\n", "\n\n", text)
  return text
