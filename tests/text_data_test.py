import json
import logging
import os

import pytest

from doc_curation import text_data


def test_get_subunit_list():
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "shatapatha.json")
    assert text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]) == range(1, 15)
    assert text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[2]) == range(1, 7)