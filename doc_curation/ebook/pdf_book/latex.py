import regex
import subprocess, tempfile, os
import shutil
from curation_utils import file_helper
from doc_curation.md.content_processor import footnote_helper, quote_helper, details_helper


def md_links_to_latex(content: str) -> str:
    """
    Convert Markdown links [text](url) into LaTeX \href{url}{text}.
    """
    pattern = regex.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    
    def repl(match):
        text = match.group(1)
        url = match.group(2)
        # Escape LaTeX special characters in text minimally
        text = text.replace("&", "\\&").replace("%", "\\%")
        return f"\\href{{{url}}}{{{text}}}"
    
    return pattern.sub(repl, content)


def escape_latex(text: str) -> str:
  """
  Escape LaTeX special characters in text.
  """
  replacements = {
    '\\': r'\textbackslash{}',
    '{': r'\{',
    '}': r'\}',
    # '#': r'\#', messes with heading replacement
    '$': r'\$',
    '%': r'\%',
    '&': r'\&',
    '_': r'\_',
    '^': r'\^{}',
    '~': r'\textasciitilde{}',
  }
  for char, repl in replacements.items():
    text = text.replace(char, repl)
  return text




def from_md(content, appendix=None) -> str:
  """
  Convert custom Markdown with <details><summary>...</summary>...</details>
  into LaTeX with tcolorbox environments and proper heading mapping.
  """

  content = escape_latex(content)
  content = regex.sub(r"\+\+\+(\(.+?\))\+\+\+", r'\\inlinecomment{\1}', content, flags=regex.DOTALL)

  # Should be called before # is escaped.
  content = headings_to_sections(content)
  content = quote_helper.convert_markdown_to_latex_leftbar(content=content)
  content = details_helper.details_to_latex(content)
  content = footnote_helper.to_latex_footnotes(content=content)
  content = md_links_to_latex(content)
  return content


def headings_to_sections(content: str) -> str:
  # Headings mapping
  content = regex.sub(r"^# (.*)$", r"\\part{\1}\n", content, flags=regex.MULTILINE)
  content = regex.sub(r"^## (.*)$", r"\\part{\1}", content, flags=regex.MULTILINE)
  content = regex.sub(r"^### (.*)$", r"\\chapter{\1}", content, flags=regex.MULTILINE)
  content = regex.sub(r"^#### (.*)$", r"\\section{\1}", content, flags=regex.MULTILINE)
  content = regex.sub(r"^##### (.*)$", r"\\subsection{\1}", content, flags=regex.MULTILINE)
  content = regex.sub(r"^###### (.*)$", r"\\subsubsection{\1}", content, flags=regex.MULTILINE)

  content = regex.sub(r"^###### (.*)$", r"\\subsubsection{\1}", content, flags=regex.MULTILINE)
  content = regex.sub("#", "\\#", content)
  return content


def details_to_colorbox(md_text) -> str:
  # Convert <details> blocks into tcolorbox
  pattern = regex.compile(r"<details.*?><summary>(.*?)</summary>(.*?)</details>", regex.DOTALL)


def to_pdf(latex_body, dest_path, metadata, paper_size="a5", **kwargs):
  """
  Wrap LaTeX body into a full book-style document and compile to PDF.
  """
  
  template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/template.tex')

  paper_geometry = f"\\usepackage[{paper_size}paper,left=16mm,right=16mm,top=16mm,bottom=10mm]{{geometry}}"

  with tempfile.TemporaryDirectory() as tmpdir:
    tex_path = os.path.join(tmpdir, "doc.tex")
    with open(tex_path, "w", encoding="utf-8") as f, open(template_path, "r", encoding="utf-8") as template:
      content = template.read()
      content = content.replace("__PAPER_GEOMETRY__", paper_geometry)
      metadata_str = f"\\title{{{metadata['title']}}}"
      if "author" in metadata:
        metadata_str = f"{metadata_str}\n\\author{{{metadata['author']}}}"
      if "date" in metadata:
        metadata_str = f"{metadata_str}\n\\date{{{metadata['date']}}}"
      content = content.replace("__METADATA__", metadata_str)
      content = content.replace("__LATEX_BODY__", latex_body)
      f.write(content)

    subprocess.run(["xelatex", "-interaction=nonstopmode", tex_path], cwd=tmpdir)
    subprocess.run(["xelatex", "-interaction=nonstopmode", tex_path], cwd=tmpdir)

    pdf_path = os.path.join(tmpdir, "doc.pdf")
    # At this point pdf_path points to something like /tmp/.../doc.pdf
    # and dest_path is the final location.
    file_helper.move_file_cross_device_safe(tex_path, dest_path.replace(".pdf", ".tex"))
    file_helper.move_file_cross_device_safe(os.path.join(tmpdir, "doc.log"), dest_path.replace(".pdf", ".log"))
    file_helper.move_file_cross_device_safe(pdf_path, dest_path)

    # At this point pdf_path points to something like /tmp/.../doc.pdf
    # and dest_path is the final location.
    if os.path.exists(dest_path):
      pass
      # os.replace(pdf_path, dest_path)
      # logging.info(f"PDF generated: {dest_path}")
    else:
      raise RuntimeError("PDF generation failed")
