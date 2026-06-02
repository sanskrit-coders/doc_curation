import os

from curation_utils.file_helper import clean_file_path
from doc_curation.md.file import MdFile


def dump_posts(objs, dest_dir, post_field_to_json_field, section_fields, dry_run=False):
  if isinstance(objs, dict):
    objs = objs.values()
  for obj in objs:
    json_obj_to_post(obj=obj, dest_dir=dest_dir, post_field_to_json_field=post_field_to_json_field, section_fields=section_fields, dry_run=dry_run)


def json_obj_to_post(obj, dest_dir, post_field_to_json_field, section_fields, dry_run=False):

  metadata = {}
  for post_field in post_field_to_json_field:
    json_field = post_field_to_json_field[post_field]
    value = obj.get(json_field, "")
    if "date" in post_field:
      value = obj[json_field][:len("2020-02-20")]
    if value is not None and value != "":
      metadata[post_field] = value 

  content = ""
  for field in section_fields:
    if obj.get(field, "") == "":
      continue
    content = "%s\n## %s\n%s\n\n" % (content, field, obj[field].replace("\n", "\n\n"))

  file_name = metadata["title"].replace("/", "\\").replace("\n", " ")
  if "date_start" in metadata:
    file_name = "_".join([metadata["date_start"], file_name])
  file_path = os.path.join(dest_dir, "%s.md" % file_name)
  file_path = clean_file_path(file_path=file_path)
  md_file = MdFile(file_path=file_path)
  md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)


if __name__ == '__main__':
    pass