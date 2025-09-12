import os

import doc_curation.ebook
from doc_curation import ebook
from doc_curation.md.file import MdFile
from doc_curation.ebook import epub

CSS_PATH = "/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/ebook/epub_style.css"
OUT_PATH_BASE = f"/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/vv_ebook_pub/"
appendix_dg = "/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/_index.md"


def make_epub(dir_path, out_path, metadata={}, omit_pattern=None, file_split_level=4, detail_pattern_to_remove="मूलम्.*"):

  out_path = doc_curation.ebook.make_out_path(metadata["author"], dir_path, out_path)
  # epub.make_epubs_recursively(source_dir=dir_path, out_path=out_path, metadata=metadata, css_path=css_path, recursion_depth=3)
  epub.epub_from_full_md(source_dir=dir_path, file_split_level=file_split_level, omit_pattern=omit_pattern, out_path=out_path, metadata=metadata, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=detail_pattern_to_remove)


def rAmAnujIyam():
  pass
  out_path = os.path.join(OUT_PATH_BASE, "rAmAnujIyam")
  # make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sarva-prastutiH", metadata={"author": "venkaTanAthaH"}, )
  # make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", metadata={"author": "yAmunaH"}, out_path=out_path,)
  # ebook.from_dir("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", out_path=os.path.join(out_path, "yAmunaH/Agama-prAmANyam"), dest_format="html", pandoc_extra_args=[f'--css={css_path}'], appendix=appendix_dg, cleanup=False, overwrite=True)
  # ebook.from_dir("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", out_path=os.path.join(out_path, "yAmunaH/Agama-prAmANyam"), pandoc_extra_args=[f'--css={css_path}'], dest_format="pdf", appendix=appendix_dg, cleanup=False, overwrite=False)
  # make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/parichaya-sanxepAH/kRShNamAchAryoktA_mata-prakriyA", metadata={"author": "kRShNamAchAryaH"}, file_split_level=1)
  # make_epub("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/parichaya-sanxepAH/venkaTArya-vedAnta-kArikAvalI/sarva-prastutiH", metadata={"author": "venkaTAryaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*|.*\(सं\).*")

  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/koLHiyAla-ranga-rAmAnujaH/heyopAdeyadarpaNaH", file_split_level=1, omit_pattern=".*_ta", out_path=os.path.join(out_path, "koLHiyAla-ranga-rAmAnujaH/heyopAdeyadarpaNaH"), metadata={"author": "कोऴियाल-रङ्गरामानुजः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")
  # 
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/koLHiyAla-ranga-rAmAnujaH/laghvAhnikam", file_split_level=1, omit_pattern=".*_ta", out_path=os.path.join(out_path, "koLHiyAla-ranga-rAmAnujaH/laghvAhnikam"), metadata={"author": "कोऴियाल-रङ्गरामानुजः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")

  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/shrI-nivAsa-tAtAryaH_pancha-kAla-kriyA-dIpaH", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "shrI-nivAsa-tAtAryaH/pancha-kAla-kriyA-dIpaH"), metadata={"author": "श्रीनिवास-तातार्यः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")

  epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/tirumalai-tAtAryaH_sampradAya-pradIpaH", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "tirumalai-tAtAryaH/sampradAya-pradIpaH"), metadata={"author": "तिरुमलै-तातार्यः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")

  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/uttamUru-vIrarAghavArya-prayoga-mAlA", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "uttamUru-vIrarAghavAryaH/prayoga-mAlA"), metadata={"author": "उत्तमूरु-वीरराघवः", "title": "प्रयोगमाला (पाञ्चरात्र-भागः)"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")

  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/vaikuNTha-dIxita-prapanna-dharma-sAra-samuchchayaH", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "vaikuNTha-dIxitaH/prapanna-dharma-sAra-samuchchayaH"), metadata={"author": "वैकुण्ठ-दीक्षितः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")


def vedAH_yajuH():
  pass
  out_path = os.path.join(OUT_PATH_BASE, "vedAH_yajuH")
  # make_epub("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/dharma-sUtram/sarva-prastutiH", metadata={"author": "ApastambaH", "title": "आपस्तम्ब-धर्म-सूत्राणि"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path)
  make_epub("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/sarva-prastutiH", metadata={"author": "ApastambaH", "title": "आपस्तम्ब-गृह्य-सूत्राणि"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path)
  # make_epub("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/sarva-prastutiH", metadata={"author": "ApastambaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path)
  # make_epub("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/DenkaNi-koTTai-shrInivAsaH", metadata={"author": "DenkaNi-koTTai-shrInivAsaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path)
  # make_epub("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/gopAla-deshika-shrAddha-prayogaH", metadata={"author": "gopAla-deshikaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path)
  # make_epub("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/gopAla-deshika-shrAddha-prayogaH", metadata={"author": "gopAla-deshikaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path)


if __name__ == '__main__':
  rAmAnujIyam()
  # vedAH_yajuH()
  pass