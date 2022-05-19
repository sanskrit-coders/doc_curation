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


def test_rehyphenate_sanskrit_line_endings():
  t = textwrap.dedent("""
  यदाश्रौषं स्नातकानां सहस्रै-  
  रन्वागतं धर्मराजं वनस्थम् ।  
  """)
  t_cleaned_expected = textwrap.dedent("""
  यदाश्रौषं स्नातकानां सहस्रैर्  
  अन्वागतं धर्मराजं वनस्थम् ।  
  """)
  t_cleaned = content_processor.rehyphenate_sanskrit_line_endings(content=t)
  assert t_cleaned_expected.strip() == t_cleaned.strip()

  t = textwrap.dedent("""
  यस्येमां गां विक्रममेकमाहु-  
  स्तदा नाशंसे विजयाय संजय ॥
  """)
  t_cleaned_expected = textwrap.dedent("""
  यस्येमां गां विक्रममेकमाहुस्  
  तदा नाशंसे विजयाय संजय ॥
  """)
  t_cleaned = content_processor.rehyphenate_sanskrit_line_endings(content=t)
  assert t_cleaned_expected.strip() == t_cleaned.strip()

  t = textwrap.dedent("""
  यदाश्रौषं व्यूहमभेद्यमन्यै-  
  र्भारद्वाजेनात्तशस्त्रेण गुप्तम् । 
  """)
  t_cleaned_expected = textwrap.dedent("""
  यदाश्रौषं व्यूहमभेद्यमन्यैर्  
  भारद्वाजेनात्तशस्त्रेण गुप्तम् । 
  """)
  t_cleaned = content_processor.rehyphenate_sanskrit_line_endings(content=t)
  assert t_cleaned_expected.strip() == t_cleaned.strip()

