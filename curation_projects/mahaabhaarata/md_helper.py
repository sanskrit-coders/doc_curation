from typing import Tuple, Dict
import codecs
import logging
import os

import regex
import yamldown
from indic_transliteration import sanscript

class MdFile(object):
    def __init__(self, file_path):
        self.file_path = file_path

    def __str__(self):
        return self.file_path

    def read_md_file(self) -> Tuple[Dict, str]:
        yml = {}
        md = ""
        with open(self.file_path, 'r') as file:
            (yml, md) = yamldown.load(file)
            logging.info((yml, md))
            if yml is None: yml = {}
        return (yml, md)
    
    
    def get_title(self, omit_chapter_id=True):
        (yml, md) = self.read_md_file()
        title = yml.get("title", None)
        if omit_chapter_id and title is not None:
            title = regex.sub("^[+०-९]+ +", "", title)
        return title
    
    
    def get_upaakhyaana(self, omit_id=True):
        upaakhyaana_optitrans = os.path.basename(os.path.dirname(self.file_path))
        upaakhyaana = sanscript.transliterate(data=upaakhyaana_optitrans, _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
        if omit_id:
            upaakhyaana = regex.sub("^[+०-९]+-+", "", upaakhyaana)
        return upaakhyaana
    
    
    def set_title_from_filename(self, dry_run):
        logging.info(self.file_path)
        if os.path.basename(self.file_path) == "_index.md":
            dir_name = os.path.basename(os.path.dirname(self.file_path)).replace(".md", "")
            title_optitrans = "+" + dir_name.replace("-", " ", 1)
        else:
            title_optitrans = os.path.basename(self.file_path).replace("-", " ", 1).replace(".md", "")
        title = sanscript.transliterate(data=title_optitrans, _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
        self.set_title(dry_run, title)
    
    
    def set_title(self, dry_run, title):
        md, yml = self.read_md_file()
        yml["title"] = title
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not dry_run:
            with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
                out_file_obj.write(yamldown.dump(yml, md))
        else:
            logging.info(yml)
            logging.info(md)
    
    @classmethod
    def get_md_files_from_path(cls, dir_path, file_pattern, file_name_filter=None):
        from pathlib import Path
        md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
        return [MdFile(path) for path in md_file_paths]