import logging
import os
import shutil
import subprocess

import regex
import yaml

from doc_curation.md.file import MdFile


os.environ.setdefault('PYPANDOC_PANDOC', '/usr/bin/pandoc')



def get_md_with_pandoc(content_in, source_format="html-native_divs-native_spans", pandoc_extra_args=['--markdown-headings=atx']):
  """
  
  :param content_in: 
  :param source_format: html-native_divs-native_spans ensures that there are no divs and span tags in the output. 
  :param pandoc_extra_args: 
  :return: 
  """
  import pypandoc
  logger = logging.getLogger('pypandoc')
  logger.setLevel(logging.CRITICAL)

  filters = None
  content = pypandoc.convert_text(source=content_in, to="gfm-raw_html", format=source_format,
                                  extra_args=pandoc_extra_args,
                                  filters=filters)
  # content = regex.sub(r"</?div[^>]*?>", "", content)
  content = regex.sub(r"\n\n+", "\n\n", content)
  # Careful to exclude |-ending-lines in tables.
  content = regex.sub(r"([^\s|])\n([^\-\s|>])", r"\1 \2", content)
  return content


def pandoc_dump_md(md_file, content, source_format, dry_run=False, metadata={},
                               pandoc_extra_args=['--markdown-headings=atx']):
  content = get_md_with_pandoc(content_in=content, source_format=source_format, pandoc_extra_args=pandoc_extra_args)
  md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)

def import_with_pandoc(md_file, source_file, source_format, dry_run, metadata={},
                       pandoc_extra_args=['--markdown-headings=atx']):
  if source_format == "rtf":
    html_path = str(source_file).replace(".rtf", ".html")
    subprocess.call(['Ted', '--saveTo', source_file, html_path])
    source_file = html_path
    source_format = "html"
    if not os.path.exists(html_path):
      logging.warning("Could not convert rtf to html, skipping %s", source_file)
      return

  with open(source_file, 'r') as fin:
    md_file.import_content_with_pandoc(content=fin.read(), source_file=source_file, source_format=source_format,
                                    dry_run=dry_run, metadata=metadata, pandoc_extra_args=pandoc_extra_args)




def pandoc_from_md_file(md_file, dest_path, dest_format="epub", metadata=None, pandoc_extra_args=None, content_maker=None, *args, **kwargs):
  if pandoc_extra_args is None:
    pandoc_extra_args = []
  import pypandoc
  logger = logging.getLogger('pypandoc')
  logger.setLevel(logging.INFO)
  logger.info(f"Converting {md_file} to {dest_path}...")

  logging.info(f"pandoc {pypandoc.get_pandoc_version()} at {pypandoc.get_pandoc_path()}.")

  [metadata_in, content_in] = md_file.read()
  if metadata is not None:
    metadata_in.update(metadata)
  if content_maker is not None:
    content_in = content_maker(content_in, *args, **kwargs)
  filters = None
  # prepend metadata as yaml string to content_in
  content_in = "\n".join([f"---\n{yaml.dump(metadata_in)}\n---\n# ॐ\n", content_in])

  os.makedirs(os.path.dirname(dest_path), exist_ok=True)
  
  if dest_format == "pdf":
    pandoc_extra_args.extend(["--pdf-engine=xelatex", "-V", "mainfont=Noto Sans", "-V", "devanagarifont=Noto Sans Devanagari"])

  logging.info(f"Converting to {dest_format} with args {pandoc_extra_args} ...")
  # -smart disables smart quotes and emdashification of --.
  # raw_html allows raw html tags.
  pypandoc.convert_text(source=content_in, to=dest_format, format="gfm+raw_html-smart+footnotes",extra_args=pandoc_extra_args,filters=filters, outputfile=dest_path)
  logging.info(f"Successfully created '{dest_path}'!")


# TODO: Getting TOFUS for devanAgarI
# CSS styles not being applied.
def to_pdf(epub_path, paper_size="a4"):
  dest_path = regex.sub("(_min.*)?.epub", f"_{paper_size}.pdf", epub_path)
  if shutil.which("pandoc") is None:
    raise RuntimeError("pandoc not found in PATH. Please install Pandoc.")

  # Prefer LuaLaTeX (HarfBuzz shaping) for complex scripts; fallback to XeLaTeX.
  pdf_engine = "lualatex" if shutil.which("lualatex") is not None else "xelatex"
  if shutil.which(pdf_engine) is None:
    raise RuntimeError(f"{pdf_engine} not found in PATH. Please install a LaTeX distribution with {pdf_engine} (e.g., TeX Live).")

  paper_token = f"{paper_size}paper" if not paper_size.endswith("paper") else paper_size
  geometry = f"{paper_token},left=0.5in,right=0.5in,top=0.33in,bottom=0.33in"

  # Pick font exactly from fc-list full font family entries
  def _pick_font(candidates):
    if shutil.which("fc-list") is None:
      return candidates[0]
    try:
      out = subprocess.run(["fc-list", ":family"], capture_output=True, text=True).stdout
      for name in candidates:
        # Use exact match ignoring case and trimming spaces/newlines
        for line in out.splitlines():
          if line.strip().lower() == name.lower():
            return name
    except Exception:
      pass
    return candidates[0]

  mainfont = _pick_font([
    "Siddhanta",
    "Adishila San",
    "Sanskrit 2003",
    "Chandas",
  ])
  devanagarifont = _pick_font([
    "Noto Serif Devanagari",
    "Noto Sans Devanagari",
    "Siddhanta",
    "Chandas",
    "Murty Sanskrit",
    "Sanskrit 2003",
  ])
  sansfont = _pick_font([
    "Noto Sans",
    "DejaVu Sans",
    "FreeSans",
  ])
  monofont = _pick_font([
    "Noto Sans Mono",
    "DejaVu Sans Mono",
    "Nimbus Mono PS",
  ])

  def build_command(engine, mf, devf, sf, mono):
    return [
      "pandoc",
      epub_path,
      "-o", dest_path,
      "--pdf-engine", engine,
      "-V", f"geometry={geometry}",
      "-V", f"mainfont={mf}",
      "-V", f"devanagarifont={devf}",
      "-V", f"sansfont={sf}",
      "-V", f"monofont={mono}",
      "-V", "Script=Devanagari,Language=DFLT,Renderer=Harfbuzz",
      # Added Language=DFLT and Renderer=Harfbuzz for better shaping on LuaLaTeX
      "-V", "devanagarifontoptions=Script=Devanagari,Language=DFLT,Renderer=Harfbuzz",
      "--toc",
      "-V", "colorlinks=true",
      "-V", "date=",
    ]

  command = build_command(pdf_engine, mainfont, devanagarifont, sansfont, monofont)
  logging.info(f"Converting {os.path.basename(epub_path)} to PDF via Pandoc/{pdf_engine} for per-page footnotes and proper Indic shaping...")
  try:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
  except subprocess.CalledProcessError as e:
    logging.error("Pandoc/LaTeX failed on first attempt.")
    if e.stdout:
      logging.error(f"pandoc stdout:\n{e.stdout}")
    if e.stderr:
      logging.error(f"pandoc stderr:\n{e.stderr}")
    fallback_engine = "xelatex"
    if shutil.which(fallback_engine) is None:
      raise RuntimeError(f"Pandoc/LaTeX failed with exit code {e.returncode}, and no fallback engine available. See logs for details.") from e
    fallback_command = build_command(
      fallback_engine,
      mf="Noto Serif",
      devf="Noto Serif Devanagari",
      sf="Noto Sans",
      mono="Noto Sans Mono",
    )
    logging.info("Retrying with XeLaTeX and Noto font stack for maximum compatibility...")
    try:
      result = subprocess.run(fallback_command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e2:
      logging.error("Fallback Pandoc/XeLaTeX also failed.")
      if e2.stdout:
        logging.error(f"pandoc stdout (fallback):\n{e2.stdout}")
      if e2.stderr:
        logging.error(f"pandoc stderr (fallback):\n{e2.stderr}")
      raise RuntimeError(f"Pandoc/LaTeX failed (initial engine {pdf_engine}) and fallback XeLaTeX also failed. See logs for details.") from e2
  logging.info("Conversion successful!")
  return dest_path


if __name__ == '__main__':
  pandoc_from_md_file(md_file=MdFile(file_path="/doc_curation/md/library/test_local.md"), dest_path="/doc_curation/md/library/test_local.md.epub", dest_format="epub", metadata={"title": "mUlam-1.1", "author": "mUlam"})


