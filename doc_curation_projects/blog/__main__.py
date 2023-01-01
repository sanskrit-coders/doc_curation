import logging

from curation_utils import file_helper


def print_usage_report(src_dir, dest_dir):
  (matching_paths, unmatched_paths) = file_helper.find_files_with_same_basename(src_dir=src_dir, dest_dir=dest_dir)
  
  unmatched_paths_str = "\n".join(unmatched_paths)
  logging.info(f"Unmatched paths: {len(unmatched_paths)}\n{unmatched_paths_str}")

  logging.info(f"Matched paths:")
  for src_file, matches in matching_paths.items():
    print(f"{src_file} : {str(matches[:5])}")


print_usage_report(src_dir="/home/vvasuki/hindu-comm/weblogs/manasataramgini", dest_dir="/home/vvasuki/gitland/vishvAsa")