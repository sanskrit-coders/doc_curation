import json
import logging
import os

# Remove all handlers associated with the root logger object.
from pathlib import Path

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



def get_subunit_data(json_file, unit_path_list):
    with open(json_file, 'r') as handle:
        unit_data = json.load(handle)
        for unit in unit_path_list:
            if str(unit) not in unit_data:
                return None
            unit_data = unit_data[str(unit)]
        return unit_data


def get_subunit_list(json_file, unit_path_list):
    unit_data = get_subunit_data(json_file, unit_path_list)
    if unit_data is None:
        return []
    else:
        return range(1, unit_data["length"] + 1)


def get_subunit_path_list(json_file, unit_path_list):
    subunit_list = get_subunit_list(json_file, unit_path_list)
    if len(subunit_list) == 0:
        return [] # unit_path_list is a leaf node
    subunit_path_list = []
    for subunit in subunit_list:
        subsubunit_path_list = get_subunit_path_list(json_file=json_file, unit_path_list=unit_path_list + [subunit])
        if len(subsubunit_path_list) == 0:
            subunit_path_list.append([subunit])
        else:
            for subsubunit_path in subsubunit_path_list:
                subunit_path_list.append([subunit] + subsubunit_path)
    return subunit_path_list


def clean_file_names(dir_path, dry_run=False):
    paths = list(Path(dir_path).glob("**/*"))
    logging.info("Got %d paths", len(paths))
    for path in paths:
        path = str(path)
        # logging.debug("Checking '%s'", path)
        import regex
        dest_path = regex.sub("[^a-zA-Z0-9 _\\-~./]", "", path)
        if path != dest_path:
            logging.info("Changing '%s' to '%s'", path, dest_path)
            if not dry_run:
                os.rename(path, dest_path)
