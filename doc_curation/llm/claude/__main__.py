"""Demo invocations (all commented out). Run: python -m doc_curation.llm.claude."""
from doc_curation import llm  # noqa: F401
from doc_curation.llm.claude import (  # noqa: F401
    process_details_with_keys,
    process_pdf_chunks_with_keys,
    process_text_chunks_with_keys,
)

if __name__ == '__main__':
  pass
  # process_text_chunks_with_keys(file_in="/path/to/doc.md", prompt=llm.get_prompt("/path/to/prompt.md"))
  # process_details_with_keys(file_in="/path/to/doc.md", prompt=llm.get_prompt("/path/to/prompt.md"), detail_pattern="मूलम्.*")
