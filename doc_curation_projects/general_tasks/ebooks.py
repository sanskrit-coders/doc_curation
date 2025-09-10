import os

import doc_curation.ebook
from doc_curation import ebook
from doc_curation.md.file import MdFile
from doc_curation.ebook import epub

css_path = "/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/md/epub_style.css"
out_path_base = f"/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/vv_ebook_pub/"
appendix_dg = "/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/_index.md"


def make_epub(dir_path, author=None):

  out_path = doc_curation.ebook.make_out_path(author, dir_path)
  # epub.make_epubs_recursively(source_dir=dir_path, out_path=out_path, metadata=metadata, css_path=css_path, recursion_depth=3)
  epub.epub_from_full_md(source_dir=dir_path, out_path=out_path, metadata={"author": author}, css_path=css_path, appendix=appendix_dg)


if __name__ == '__main__':
  # make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sarva-prastutiH", author="venkaTanAthaH", )
  make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", author="yAmunaH")
  # ebook.from_dir("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", out_path=os.path.join(out_path_base, "yAmunaH/Agama-prAmANyam"), dest_format="html", pandoc_extra_args=[f'--css={css_path}'], appendix=appendix_dg, cleanup=False, overwrite=True)
  # ebook.from_dir("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", out_path=os.path.join(out_path_base, "yAmunaH/Agama-prAmANyam"), pandoc_extra_args=[f'--css={css_path}'], dest_format="pdf", appendix=appendix_dg, cleanup=False, overwrite=False)
  