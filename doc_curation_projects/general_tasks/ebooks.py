import os



from doc_curation.md.file import MdFile
from doc_curation.ebook import epub

css_path = "/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/md/epub_style.css"


def make_epub(dir_path, author=None):

  metadata, out_path = epub.get_epub_metadata_path(author, dir_path)
  # epub.make_epubs_recursively(source_dir=dir_path, out_path=out_path, metadata=metadata, css_path=css_path, recursion_depth=3)
  epub.epub_from_full_md(source_dir=dir_path, out_path=out_path, metadata=metadata, css_path=css_path)


if __name__ == '__main__':
  # make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sarva-prastutiH", author="venkaTanAthaH", )
  make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", author="yAmunaH", appendix="/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/_index.md")