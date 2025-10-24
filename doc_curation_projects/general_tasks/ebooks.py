import os

import doc_curation.ebook
from doc_curation import ebook
from doc_curation.md.file import MdFile
from doc_curation.ebook import epub

CSS_PATH = "/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/ebook/epub_style.css"
OUT_PATH_BASE = f"/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/vv_ebook_pub/"
appendix_dg = "/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/_index.md"


def rAmAnujIyam():
  pass
  out_path = os.path.join(OUT_PATH_BASE, "rAmAnujIyam")
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sarva-prastutiH", metadata={"author": "वेङ्कटनाथः"}, out_path=os.path.join(out_path, "venkaTanAthaH/rahasya-traya-sAraH"), css_path=CSS_PATH, appendix=appendix_dg,)
  epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH", out_path=os.path.join(out_path, "yAmunaH/Agama-prAmANyam"),css_path=CSS_PATH, metadata={"author": "यामुनः"},appendix=appendix_dg, file_split_level=2)
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/parichaya-sanxepAH/kRShNamAchAryoktA_mata-prakriyA", metadata={"author": "कृष्णमाचार्यः"}, file_split_level=1, css_path=CSS_PATH, appendix=appendix_dg, out_path=os.path.join(out_path, "kRShNamAchAraH/mata-prakriyA"),)
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/parichaya-sanxepAH/venkaTArya-vedAnta-kArikAvalI/sarva-prastutiH", metadata={"author": "वेङ्कटार्यः"}, out_path=os.path.join(out_path, "venkaTAryaH/vedAnta-kArikAvalI"), file_split_level=1, detail_pattern_to_remove=r"मूलम्.*|.*\(सं\).*", css_path=CSS_PATH, appendix=appendix_dg, )
  # 
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/parakAla-shAkhA/vijayIndra-parAjayaH", metadata={"author": "परकाल-यतिः"}, out_path=os.path.join(out_path, "parakAla-yatiH/vijayIndra-parAjayaH"), file_split_level=1, css_path=CSS_PATH, appendix=appendix_dg, )
  # 
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/koLHiyAla-ranga-rAmAnujaH/heyopAdeyadarpaNaH", file_split_level=1, omit_pattern=".*_ta", out_path=os.path.join(out_path, "koLHiyAla-ranga-rAmAnujaH/heyopAdeyadarpaNaH"), metadata={"author": "कोऴियाल-रङ्गरामानुजः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")
  # 
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/koLHiyAla-ranga-rAmAnujaH/laghvAhnikam", file_split_level=1, omit_pattern=".*_ta", out_path=os.path.join(out_path, "koLHiyAla-ranga-rAmAnujaH/laghvAhnikam"), metadata={"author": "कोऴियाल-रङ्गरामानुजः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")
  # 
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/shrI-nivAsa-tAtAryaH_pancha-kAla-kriyA-dIpaH", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "shrI-nivAsa-tAtAryaH/pancha-kAla-kriyA-dIpaH"), metadata={"author": "श्रीनिवास-तातार्यः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")
  # 
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/tirumalai-tAtAryaH_sampradAya-pradIpaH", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "tirumalai-tAtAryaH/sampradAya-pradIpaH"), metadata={"author": "तिरुमलै-तातार्यः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")
  # 
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/uttamUru-vIrarAghavArya-prayoga-mAlA", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "uttamUru-vIrarAghavAryaH/prayoga-mAlA"), metadata={"author": "उत्तमूरु-वीरराघवः", "title": "प्रयोगमाला (पाञ्चरात्र-भागः)"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")
  # 
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/vaikuNTha-dIxita-prapanna-dharma-sAra-samuchchayaH", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "vaikuNTha-dIxitaH/prapanna-dharma-sAra-samuchchayaH"), metadata={"author": "वैकुण्ठ-दीक्षितः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")
  # epub.epub_from_full_md(source_dir="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/vyAsaH/goraxapura-pAThaH/hindy-anuvAdaH/12_shAntiparva/03_moxadharmaparva/335-351_nArAyaNIyam/347_hayashira-upAkhyAnam_abhinava-ranganAtha-TIkA", file_split_level=1, omit_pattern=".*/00", out_path=os.path.join(out_path, "abhinava-ranganAthaH/hayashira-upAkhyAnam_abhinava-ranganAtha-TIkA"), metadata={"author": "अभिनव-रङ्गनाथः"}, css_path=CSS_PATH, appendix=appendix_dg, detail_pattern_to_remove=r"मूलम्.*|.*परिष्कार्यम्.*")


def vedAH_yajuH():
  pass
  out_path = os.path.join(OUT_PATH_BASE, "vedAH_yajuH")
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/dharma-sUtram/sarva-prastutiH", metadata={"author": "ApastambaH", "title": "आपस्तम्ब-धर्म-सूत्राणि"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path, css_path=CSS_PATH, appendix=appendix_dg, )
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/sarva-prastutiH", metadata={"author": "ApastambaH", "title": "आपस्तम्ब-गृह्य-सूत्राणि"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path, css_path=CSS_PATH, appendix=appendix_dg, )
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/sarva-prastutiH", metadata={"author": "ApastambaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path, css_path=CSS_PATH, appendix=appendix_dg, )
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/DenkaNi-koTTai-shrInivAsaH", metadata={"author": "DenkaNi-koTTai-shrInivAsaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path, css_path=CSS_PATH, appendix=appendix_dg, )
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/gopAla-deshika-shrAddha-prayogaH", metadata={"author": "gopAla-deshikaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path, css_path=CSS_PATH, appendix=appendix_dg, )
  # epub.epub_from_full_md("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/gopAla-deshika-shrAddha-prayogaH", metadata={"author": "gopAla-deshikaH"}, file_split_level=1, detail_pattern_to_remove=r"मूलम्.*", out_path=out_path, css_path=CSS_PATH, appendix=appendix_dg, )


if __name__ == '__main__':
  rAmAnujIyam()
  # vedAH_yajuH()
  pass