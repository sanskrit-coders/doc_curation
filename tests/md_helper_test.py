import codecs
import logging
import os

import doc_curation.md
import doc_curation.md.section

test_lines = []
with codecs.open(os.path.join(os.path.dirname(__file__), "test.md"), "r", 'utf-8') as file_obj:
    test_lines = list(file_obj.readlines())


def test_get_lines_till_section():
    (lines_till_section, remaining) = doc_curation.md.section.get_lines_till_section(test_lines)
    lines_till_section = list(lines_till_section)
    remaining = list(remaining)
    logging.info(lines_till_section)
    logging.info(remaining)
    assert len(lines_till_section) + len(remaining) == len(test_lines)


def test_split_to_sections():
    (lines_till_section, remaining) = doc_curation.md.section.get_lines_till_section(test_lines)
    sections = doc_curation.md.section.split_to_sections(remaining)
    for (title, section_lines) in sections:
        logging.info(title)
        logging.info(list(section_lines))
    assert len(sections) == 2


def test_get_section_title():
    assert doc_curation.md.section.get_section_title("## 1") == "1"
