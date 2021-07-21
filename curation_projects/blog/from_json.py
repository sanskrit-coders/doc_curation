import codecs
import json
import os

from doc_curation.blog import json_importer
from doc_curation.md import library


def dump_svaasthya_posts(sheet_index, sheet_title_optitrans):
  base_dir = "/home/vvasuki/vishvAsa/rahashtippanyah/content/ghaTanAH/svAsthyam"
  post_field_to_json_field = {
    "date_start": "Start date",
    "date_end": "End date",
    "location": "sthAnam",
    "title": "Diagnosis"
  }
  section_fields = ["Diagnosis", "Circumstance", "Symptoms", "Treatment", "Response", "Long term Recovery/ avoidance", "Cause"]
  with codecs.open("/home/vvasuki/vishvAsa/rahashtippanyah/content/ghaTanAH/svAsthyam/full_data.json", "r") as sheet_json:
    full_sheet = json.load(sheet_json)
    json_importer.dump_posts(objs=full_sheet[sheet_index], dest_dir=os.path.join(base_dir, sheet_title_optitrans), post_field_to_json_field=post_field_to_json_field, section_fields=section_fields, dry_run=False)
  library.fix_index_files(dir_path=base_dir)


if __name__ == '__main__':
  pass
  dump_svaasthya_posts(sheet_index=0, sheet_title_optitrans="nidrA")