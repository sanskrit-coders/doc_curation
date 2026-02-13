import re
import subprocess, tempfile, os
import shutil
from curation_utils import file_helper


def from_md(md_text, title, author=None) -> str:
  """
  Convert custom Markdown with <details><summary>...</summary>...</details>
  into LaTeX with tcolorbox environments and proper heading mapping.
  """
  # Convert <details> blocks into tcolorbox
  pattern = re.compile(r"<details.*?><summary>(.*?)</summary>(.*?)</details>", re.DOTALL)

  def details_to_box(match):
    title = match.group(1).strip()
    content = match.group(2).strip()
    content = content.replace("&", "\\&").replace("%", "\\%")
    return f"\\begin{{tcolorbox}}[title={{{title}}}]\n{content}\n\\end{{tcolorbox}}\n"

  latex_text = pattern.sub(details_to_box, md_text)

  # Headings mapping
  latex_text = re.sub(r"^# (.*)$", r"\\part{\1}\n", latex_text, flags=re.MULTILINE)
  latex_text = re.sub(r"^## (.*)$", r"\\chapter{\1}", latex_text, flags=re.MULTILINE)
  latex_text = re.sub(r"^### (.*)$", r"\\section{\1}", latex_text, flags=re.MULTILINE)
  latex_text = re.sub(r"^#### (.*)$", r"\\subsection{\1}", latex_text, flags=re.MULTILINE)
  latex_text = re.sub(r"^##### (.*)$", r"\\subsubsection{\1}", latex_text, flags=re.MULTILINE)
  latex_text = re.sub(r"^###### (.*)$", r"\\subsubsection{\1}", latex_text, flags=re.MULTILINE)


  latex_text = f"{title}\\maketitle\n\n{latex_text}"

  return latex_text


def to_pdf(latex_body, dest_path, **kwargs):
  """
  Wrap LaTeX body into a full book-style document and compile to PDF.
  """
  
  template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/template.tex')


  with tempfile.TemporaryDirectory() as tmpdir:
    tex_path = os.path.join(tmpdir, "doc.tex")
    with open(tex_path, "w", encoding="utf-8") as f, open(template_path, "r", encoding="utf-8") as template:
      content = template.read()
      content = content.replace("__LATEX_BODY__", latex_body)
      f.write(content)

    subprocess.run(["xelatex", "-interaction=nonstopmode", tex_path], cwd=tmpdir)
    subprocess.run(["xelatex", "-interaction=nonstopmode", tex_path], cwd=tmpdir)

    pdf_path = os.path.join(tmpdir, "doc.pdf")
    # At this point pdf_path points to something like /tmp/.../doc.pdf
    # and dest_path is the final location.
    file_helper.move_file_cross_device_safe(tex_path, dest_path+".tex")
    file_helper.move_file_cross_device_safe(pdf_path, dest_path)

    # At this point pdf_path points to something like /tmp/.../doc.pdf
    # and dest_path is the final location.
    if os.path.exists(dest_path):
      pass
      # os.replace(pdf_path, dest_path)
      # logging.info(f"PDF generated: {dest_path}")
    else:
      raise RuntimeError("PDF generation failed")
