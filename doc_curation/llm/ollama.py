import json
import textwrap
import requests
from pypdf import PdfReader
from tqdm import tqdm

from doc_curation import llm
from doc_curation.md.file import MdFile


def process_file_ollama_chunks(file_in, prompt, dest_path, start_page=1, pages_per_chunk=5, model_id="qwen2.5:3b"):
  """Processes a PDF using a local Ollama model by extracting text page-by-page."""
  reader = PdfReader(file_in)
  total_pages = len(reader.pages)

  all_text_parts = []

  # Convert 1-indexed start_page to 0-indexed for Python logic
  start_index = max(0, start_page - 1)

  for i in tqdm(range(start_index, total_pages, pages_per_chunk), desc="Processing PDF Chunks via Ollama"):
    end_page = min(i + pages_per_chunk, total_pages)

    # Qwen2.5 via Ollama doesn't natively parse PDF files directly.
    # We must extract the raw text from the pages first.
    chunk_text = ""
    for j in range(i, end_page):
      page = reader.pages[j]
      chunk_text += f"\n--- Page {j+1} ---\n"
      chunk_text += page.extract_text() or ""

    # Construct the full prompt combining instructions and the extracted text
    full_prompt = f"{prompt}\n\nProcess the following text from pages {i + 1} to {end_page}:\n\n{chunk_text}"

    # Endpoint for local Ollama instance
    url = "http://localhost:11434/api/generate"
    payload = {
      "model": model_id,
      "prompt": full_prompt,
      "stream": False
    }

    try:
      response = requests.post(url, json=payload)
      response.raise_for_status()

      result = response.json()
      generated_text = result.get("response", "")

      if generated_text:
        all_text_parts.append(generated_text)

    except requests.exceptions.RequestException as e:
      print(f"\nError connecting to local Ollama on pages {i+1}-{end_page}. Ensure 'ollama serve' is running.")
      print(e)
      break

  combined_text = "\n\n".join(all_text_parts)

  md_file = MdFile(dest_path)

  llm.dump_to_md(dest_path, prompt=prompt, metadata=f"**Model:** {model_id}, **Pages Processed:** {total_pages}", content=combined_text)
  return all_text_parts


if __name__ == '__main__':
  main_prompt = llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md")

  process_file_ollama_chunks(
    file_in="/media/vvasuki/vData/text/granthasangrahaH/kAvyam/shrIvaiShNavakRtam/yatirAja-vijaya-nATakam.pdf",
    dest_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/rUpakam/naDAdUr-ghaTikA-shata-varadaH/yatirAja-vijaya-nATakam.md",
    prompt=main_prompt,
    pages_per_chunk=3,
    model_id="qwen2.5:3b"
  )