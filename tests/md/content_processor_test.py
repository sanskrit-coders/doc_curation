import textwrap

from doc_curation.md import content_processor


def test_remove_non_content_text():
  t = textwrap.dedent("""
  +++(=ब्राह्मविवाहित
  )+++  
  +++(=ब्राह्मविवाहित)+++त्रिणाचिकेतः पञ्चाग्निस्  
  त्रिसुपर्णः षडङ्गवित् ।  
  ब्रह्मदेयात्म+++(=ब्राह्मविवाहित)+++-सन्तानो
  +++(=ब्राह्मविवाहित)+++
  """)
  t_cleaned_expected = textwrap.dedent("""
  त्रिणाचिकेतः पञ्चाग्निस्  
  त्रिसुपर्णः षडङ्गवित् ।  
  ब्रह्मदेयात्म-सन्तानो
  """)
  t_cleaned = content_processor.remove_non_content_text(content=t)
  print("\n-------\n")
  print(t_cleaned.strip())
  print("\n-------\n")
  print(t_cleaned_expected.strip())
  print("\n-------\n")
  assert t_cleaned_expected.strip() == t_cleaned.strip()