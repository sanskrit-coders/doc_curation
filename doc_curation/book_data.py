import json
import logging

# Remove all handlers associated with the root logger object.
import toml

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
