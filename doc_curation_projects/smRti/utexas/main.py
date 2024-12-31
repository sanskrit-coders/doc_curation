from doc_curation.md import library, content_processor
from doc_curation_projects.general_tasks.content.transliteration_fix import devanaagarify
from doc_curation_projects.smRti import utexas
from indic_transliteration import sanscript


# dir_path = "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/parAsharaH/mAdhavIyam"


def special_fix(dir_path):
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"\\\*"], replacement=r"*", dry_run=False)


if __name__ == '__main__':
  # devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/kriyA/govindaH_yati-dharma-samuchchayaH/00/202412-ed.md", source_script=sanscript.IAST)

  utexas.general_fix(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/kriyA/govindaH_yati-dharma-samuchchayaH/00/202412-ed.md")
  # special_fix()