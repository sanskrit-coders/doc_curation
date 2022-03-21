import logging

import regex

from doc_curation.md import library


def get_rks(content):
  rks = [x for x in content.split('\n') if "॥" in x and x.strip() != "" and not x.startswith("#")]
  return rks


def add_file_index(md_file):
  (metadata, content) = md_file.read()
  rks = get_rks(content=content)
  for index, rk in enumerate(rks):
    saMhitaa_id = "%04d" % int(regex.search("॥ *(\d+)", rk).group(1))
    new_rk = regex.sub("॥ *(\d+)", "॥ %02d:%s" % (index+1, saMhitaa_id), rk)
    content = content.replace(rk, new_rk)
  md_file.replace_content_metadata(new_content=content, dry_run=False)


def add_group_index(md_file):
  (metadata, content) = md_file.read()
  rks = get_rks(content=content)
  group_index = 1
  for index, rk in enumerate(rks):
    if regex.search("॥ *(\d+)", rk) is None:
      logging.fatal("%s", rk)
      exit(1)
    rk_id = "%d" % int(regex.search("॥ *(\d+)", rk).group(1))
    new_rk = regex.sub("([^॥]+)॥ *(\d+) *॥", "\\1॥ %02d-%s ॥" % (group_index, rk_id), rk)

    group_match = regex.search("॥.+?॥.+?(\d+)", rk)
    if group_match is not None:
      if str(group_index) != group_match.group(1):
        logging.fatal("%s: group id %s vs %s", rk, str(group_index), group_match.group(1))
        exit(1)
      group_index += 1

    content = content.replace(rk, new_rk)
  md_file.replace_content_metadata(new_content=content, dry_run=False)


def add_saMhitaa_index(md_file, init_index):
  (metadata, content) = md_file.read()
  rks = get_rks(content=content)
  final_index = init_index
  for index, rk in enumerate(rks):
    final_index = init_index + index
    saMhitaa_id = "%04d" % final_index
    new_rk = regex.sub("(^[^॥]+)॥ *([\d-]+)", "\\1॥ \\2:%s" % (saMhitaa_id), rk)
    content = content.replace(rk, new_rk)
  md_file.replace_content_metadata(new_content=content, dry_run=False)
  return final_index


def check_format(md_file):
  (metadata, content) = md_file.read()
  non_rks = [x for x in content.split('\n') if "॥" not in x and x.strip() != "" and not x.startswith("#")]
  if len(non_rks) != 0:
    logging.fatal("\n".join(non_rks))


def set_uttaraarchika_saMhitaa_indices():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/sAma/kauthumam/saMhitA/4_uttarArchikaH", file_pattern="**/[0-9].md")
  logging.info("Processing %d files.", len(md_files))
  final_index = 650
  from tqdm import tqdm
  for md_file in tqdm(md_files):
    logging.info("Processing %s", md_file)
    final_index = add_saMhitaa_index(md_file, final_index + 1)


if __name__ == '__main__':
  # library.apply_function(fn=add_group_index, file_pattern="**/[0-9].md", dir_path=PATH_ALL_SAMHITA)
  set_uttaraarchika_saMhitaa_indices()