import json
import os


def get_subunit_data(json_file, unit_path_list):
    with open(json_file, 'r') as handle:
        unit_data = json.load(handle)
        for unit in unit_path_list:
            unit_data = unit_data[str(unit)]
        return unit_data

def get_subunit_list(json_file, unit_path_list):
    unit_data = get_subunit_data(json_file, unit_path_list)
    return range(1, unit_data["length"] + 1)
