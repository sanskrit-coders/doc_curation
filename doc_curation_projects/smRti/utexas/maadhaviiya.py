from doc_curation.md import library, content_processor
from doc_curation_projects.smRti import utexas

dir_path = "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/parAsharaH/mAdhavIyam"


def special_fix():
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"\\\*"], replacement=r"*", dry_run=False)


if __name__ == '__main__':
  utexas.general_fix(dir_path=dir_path)
  # special_fix()