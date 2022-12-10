from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile


def prose():
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/gadyam/veda-bhAShyam/taittirIyam/saMhitA/misc", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["भट्टभास्करटीका", "सायण-भाष्यम्"]))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/gadyam/veda-bhAShyam/shakala-saMhitA", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["भट्टभास्करटीका", "सायण-भाष्यम्"]))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/gadyam/smRtiH/manu-bhAShyam", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["मेधातिथिः"]))
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/gadyam/veda-bhAShyam/taittirIyam/saMhitA/sAyaNaH", patterns=["[^\n]+[॒॑][^\n]+"], replacement="")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/gadyam/", patterns=["\+\+\+\(.+?\)\+\+\+"], replacement="")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/champUH/", patterns=["\+\+\+\(.+?\)\+\+\+"], replacement="")

  pass


def verse():
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/padyam/anuShTup-shlokaH/purANam/rAmAyaNam", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["मूलम्"]))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/padyam/anuShTup-shlokaH/purANam/mahAbhAratam", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["मूलम्"]))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/padyam/anuShTup-shlokaH/purANam/durgA-saptashatI", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["मूलम्"]))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/padyam/anuShTup-shlokaH/purANam/adhyAtma-rAmAyaNam", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["मूलम्"]))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/tts-corpus/padyam/anuShTup-shlokaH/purANam/viShNu-purANam", content_transformer=lambda c, m: details_helper.get_detail_content(content=c, metadata=m, titles=["मूलम्"]))

  pass


if __name__ == '__main__':
  # prose()
  verse()