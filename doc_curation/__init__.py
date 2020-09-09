"""
A package for curating doc file collections, with ability to sync with youtube and archive.org doc items. 
"""
import codecs
import logging


def fix_line(line):
    line = line.replace("\r", "")
    line = line.replace(u"\uFEFF", " ")
    line = line.replace(u"\u00A0", " ")
    return line


def clear_bad_chars(file_path, dry_run=False):
    with open(file_path, 'r') as file:
        lines = [fix_line(line=line) for line in file.readlines()]
        if not dry_run:
            with codecs.open(file_path, "w", 'utf-8') as file:
                file.writelines(lines)
        else:
            logging.info(lines)


