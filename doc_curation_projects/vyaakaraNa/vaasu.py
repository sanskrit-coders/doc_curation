from doc_curation.md import library, content_processor


def fix_suutra_ids(dir_path):
  pass
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"([VI]+)\. *(\d+)\. *(\d+)"], replacement=r"\1.\2.\3")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"([VI]+)\. *I\. *(\d+)"], replacement=r"\1.1.\2")
  def deromanize(match):
    import roman
    return str(roman.fromRoman(match.group(0)))
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"[VI]+(?=\.\d+\.\d+)"], replacement=deromanize)



if __name__ == '__main__':
  pass
  fix_suutra_ids(dir_path="/home/vvasuki/sanskrit/raw_etexts/vyAkaraNam/aShTAdhyAyI_central-repo/vAsu")
