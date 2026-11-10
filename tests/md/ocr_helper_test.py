from doc_curation.md.content_processor.ocr_helper import (
  get_gemini_flash_mangled_sanskrit_files,
)


def test_get_gemini_flash_mangled_sanskrit_files_filters_and_returns_paths(tmp_path):
  matching = tmp_path / "matching.md"
  matching.write_text(
    "धर्म " + " ".join(f"पूर्व-पश्चिम{i}" for i in range(20))
    + " " + " ".join(f"[[ref{i}|text]]" for i in range(5)),
    encoding="utf-8",
  )
  too_few_links = tmp_path / "too-few-links.md"
  too_few_links.write_text(
    "धर्म " + " ".join(f"पूर्व-पश्चिम{i}" for i in range(20))
    + " [[one|link]]",
    encoding="utf-8",
  )
  hindi = tmp_path / "hindi.md"
  hindi.write_text(
    "यह है और वह में नहीं क्या तुम लोग अपनी हैं थी थे होगा"
    + " " + " ".join(f"पूर्व-पश्चिम{i}" for i in range(20))
    + " " + " ".join(f"[[ref{i}|text]]" for i in range(5)),
    encoding="utf-8",
  )

  assert get_gemini_flash_mangled_sanskrit_files(tmp_path) == [str(matching)]
