import codecs
import logging
import os

import doc_curation.md
import doc_curation.md.content_processor.section_helper

def get_lines(test_file_name):
    with codecs.open(os.path.join(os.path.dirname(__file__), "data", test_file_name), "r", 'utf-8') as file_obj:
        return list(file_obj.readlines())


def test_get_lines_till_section():
    test_lines = get_lines(test_file_name="test.md")
    (lines_till_section, remaining) = doc_curation.md.content_processor.section_helper.get_lines_till_section(test_lines)
    lines_till_section = list(lines_till_section)
    remaining = list(remaining)
    logging.info(lines_till_section)
    logging.info(remaining)
    assert len(lines_till_section) + len(remaining) == len(test_lines)


def test_split_to_sections():
    test_lines = get_lines(test_file_name="test.md")
    (lines_till_section, remaining) = doc_curation.md.content_processor.section_helper.get_lines_till_section(test_lines)
    sections = doc_curation.md.content_processor.section_helper.split_to_sections(remaining)
    for section in sections:
        logging.info(section.title)
        logging.info(list(section.lines))
    assert len(sections) == 2


def test_split_to_sections_no_title():
    test_lines = get_lines(test_file_name="untitled_sections.md")
    (lines_till_section, remaining) = doc_curation.md.content_processor.section_helper.get_lines_till_section(test_lines)
    sections = doc_curation.md.content_processor.section_helper.split_to_sections(remaining)
    for section in sections:
        logging.info(section.title)
        logging.info(list(section.lines))
    assert len(sections) == 32


def test_get_section_title():
    assert doc_curation.md.content_processor.section_helper.get_section_title("## 1") == "1"
