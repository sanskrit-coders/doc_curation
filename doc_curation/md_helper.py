import codecs
import logging
import os
from typing import Tuple, Dict

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
        with codecs.open(self.file_path, "r", 'utf-8') as file:
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
        self.set_title(dry_run=dry_run, title=title)
    
    def dump_to_file(self, yml, md, dry_run):
        if not dry_run:
            with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
                import yaml
                yamlout = yaml.dump(yml, default_flow_style=False, indent=2, allow_unicode=True)
                dump = "---\n{yml}\n---\n{markdown}".format(yml=yamlout, markdown=md)
                out_file_obj.write(dump)
                # out_file_obj.write(yamldown.dump(yml, md)) has a bug - https://github.com/dougli1sqrd/yamldown/issues/5
        else: 
            logging.info(yml)
            logging.info(md)
    
    def set_title(self, title, dry_run):
        yml, md = self.read_md_file()
        yml["title"] = title
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.dump_to_file(yml=yml, md=md, dry_run=dry_run)

    def prepend_to_content(self, prefix_text, dry_run=True):
        (yml, md) = self.read_md_file()
        self.dump_to_file(yml=yml, md=prefix_text + md, dry_run=dry_run)


    def replace_in_content(self, pattern, replacement, dry_run=True):
        (yml, md) = self.read_md_file()
        md = regex.sub(pattern=pattern, repl=replacement, string=md)
        self.dump_to_file(yml=yml, md=md, dry_run=dry_run)

    
    @classmethod
    def get_md_files_from_path(cls, dir_path, file_pattern, file_name_filter=None):
        from pathlib import Path
        md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
        return [MdFile(path) for path in md_file_paths]