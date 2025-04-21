import json
import logging

# Remove all handlers associated with the root logger object.
import toml

import os
import json

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_subunit_data(file_path, unit_path_list):
  with open(file_path, 'r') as handle:
    if file_path.endswith('.json'):
      unit_data = json.load(handle)
    if file_path.endswith('.toml'):
      unit_data = toml.load(handle)
    for unit in unit_path_list:
      if str(unit) not in unit_data:
        return None
      unit_data = unit_data[str(unit)]
    return unit_data


def get_subunit_list(file_path, unit_path_list, length_fields=["length"]):
  unit_data = get_subunit_data(file_path, unit_path_list)
  if unit_data is None:
    return []
  else:
    for field in length_fields:
      if field in unit_data:
        return range(1, unit_data[field] + 1)


def get_subunit_path_list(file_path, unit_path_list):
  subunit_list = get_subunit_list(file_path, unit_path_list)
  if len(subunit_list) == 0:
    return []  # unit_path_list is a leaf node
  subunit_path_list = []
  for subunit in subunit_list:
    subsubunit_path_list = get_subunit_path_list(file_path=file_path, unit_path_list=unit_path_list + [subunit])
    if len(subsubunit_path_list) == 0:
      subunit_path_list.append([subunit])
    else:
      for subsubunit_path in subsubunit_path_list:
        subunit_path_list.append([subunit] + subsubunit_path)
  return subunit_path_list

def dump_structure(dir_path, output_file):
  """
  Traverse the directory tree rooted at dir_path, count the number of files
  whose names start with numbers in each directory, and dump this structure
  into a JSON file.
  
  Parameters:
  - dir_path: The root directory to start traversing from.
  - output_file: The path to the JSON file where the structure will be dumped.
  """

  def traverse_dir(path):
    # Initialize the structure for the current directory
    dir_structure = {}

    # Iterate over all items in the directory
    for item in os.listdir(path):
      item_path = os.path.join(path, item)

      # If the item is a directory, recursively traverse it
      if os.path.isdir(item_path):
        dir_structure[item] = traverse_dir(item_path)
      # If the item is a file and its name starts with a number, count it
      elif os.path.isfile(item_path) and item[0].isdigit():
        # If 'files' key doesn't exist, create it
        if 'files' not in dir_structure:
          dir_structure['length'] = 0
        dir_structure['length'] += 1

    return dir_structure

  # Traverse the directory and dump the structure to a JSON file
  structure = traverse_dir(dir_path)
  with open(output_file, 'w') as file:
    json.dump(structure, file, indent=4)


# Example usage
if __name__ == "__main__":
  dump_structure('/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/sarvASh_TIkAH', output_file="/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/data/book_data/vedaH/vAjasaneyi/samhitA.json")
