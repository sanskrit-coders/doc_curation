"""Demo invocations (all commented out). Run: python -m doc_curation.llm.gemini."""
from doc_curation import llm  # noqa: F401
from doc_curation.llm.gemini import (  # noqa: F401
    process_details_with_keys,
    process_pdf_chunks_with_keys,
    process_text_chunks_with_keys,
)

if __name__ == '__main__':
  pass
  # process_text_chunks_with_keys(file_in="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/lokAchArya-shAkhA/lokAchAryaH/shrI-vachana-bhUShaNam/vyAkhyA/mImAMsA/private/shrInivAsa-mahA-parakAla-yatiH.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md"))
  # process_details_with_keys(file_in="//home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/12k_vAdikesari-jIyar__36k_IDu_nam-piLLai_vaDakkut-tiru-vIdi-piLLai/sa_hi/01.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/bare-hyphenator.md"), detail_pattern="मूलम्.*|.+वतारिका - .+|टीका.+")
  # process_pdf_chunks_with_keys(file_in="/media/vvasuki/vData/text/granthasangrahaH/kAvyam/shrIvaiShNavakRtam/yatirAja-vijaya-nATakam.pdf", dest_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/rUpakam/naDAdUr-ghaTikA-shata-varadaH/yatirAja-vijaya-nATakam.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md"))
