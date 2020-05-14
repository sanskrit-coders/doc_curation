import codecs
import logging
import os
from pathlib import Path
from typing import Tuple, Dict
import itertools
from more_itertools import peekable

import regex
import yamldown
from indic_transliteration import sanscript

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



def get_lines_till_section(lines_in):
    lines = list(lines_in)
    lines_till_section = itertools.takewhile(lambda line: not line.startswith("#"), lines)
    remaining = itertools.dropwhile(lambda line: not line.startswith("#"), lines)
    return (peekable(lines_till_section), peekable(remaining))


def reduce_section_depth(lines_in):
    for line in lines_in:
        if line.startswith("#"):
            yield line[1:]
        else:
            yield line


def get_section(lines_in):
    lines = list(lines_in)
    if not lines[0].startswith("#"):
        return lines_in
    header_prefix = lines[0].split()[0] + " "
    title = get_section_title(lines[0])
    lines_in_section = []
    remaining = []
    if len(lines) > 1:
        lines_in_section = itertools.takewhile(lambda line: not line.startswith(header_prefix), lines[1:])
        remaining = itertools.dropwhile(lambda line: not line.startswith(header_prefix), lines[1:])
    return (title, peekable(lines_in_section), peekable(remaining))


def split_to_sections(lines_in):
    remaining = peekable(lines_in)
    sections = []
    while(remaining):
        (title, lines_in_section, remaining) = get_section(remaining)
        sections.append((title, lines_in_section))
    return sections


def get_section_title(title_line):
    splits = title_line.split()
    if len(splits) == 1:
        return None
    title = " ".join(splits[1:])
    title = regex.sub("[।॥. ]+", " ", title)
    title = regex.sub("\\s+", " ", title)
    return title.strip()


class MdFile(object):
    def __init__(self, file_path):
        self.file_path = file_path

    def __str__(self):
        return self.file_path


    def read_md_file(self) -> Tuple[Dict, str]:
        yml = {}
        md = ""
        if os.path.exists(self.file_path):
            with codecs.open(self.file_path, "r", 'utf-8') as file:
                (yml, md) = yamldown.load(file)
                # logging.info((yml, md))
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
    
    
    def set_title_from_filename(self, transliteration_target, dry_run):
        logging.info(self.file_path)
        if os.path.basename(self.file_path) == "_index.md":
            dir_name = os.path.basename(os.path.dirname(self.file_path)).replace(".md", "")
            title_optitrans = "+" + dir_name
        else:
            title_optitrans = os.path.basename(self.file_path).replace(".md", "")
        title = title_optitrans.replace("_", " ")
        if transliteration_target is not None:
            title = sanscript.transliterate(data=title, _from=sanscript.OPTITRANS, _to=transliteration_target)
        self.set_title(dry_run=dry_run, title=title)
    
    def fix_title_numbering(self, dry_run):
        title = self.get_title()
        if title is None:
            return

        import regex
        new_title = regex.sub("(^[०-९][^०-९])", "०\\1", title)
        if title != new_title:
            logging.info("Changing '%s' to '%s'", title, new_title)
            self.set_title(title=new_title, dry_run=dry_run)

    def dump_mediawiki(self, outpath=None, dry_run=False):
        (yml, md) = self.read_md_file()
        import pypandoc
        output = pypandoc.convert_text(md, 'mediawiki', format='md')
        if outpath is None:
            outpath = self.file_path.replace(".md", ".wiki")
        if not dry_run:
            with codecs.open(outpath, "w", 'utf-8') as out_file_obj:
                out_file_obj.write(output)
        else:
            logging.info(output)


    def dump_to_file(self, yml, md, dry_run):
        logging.info(self.file_path)
        if not dry_run:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
                import yaml
                yamlout = yaml.dump(yml, default_flow_style=False, indent=2, allow_unicode=True)
                dump = "---\n{yml}\n---\n{markdown}".format(yml=yamlout, markdown=md)
                out_file_obj.write(dump)
                # out_file_obj.write(yamldown.dump(yml, md)) has a bug - https://github.com/dougli1sqrd/yamldown/issues/5
        else:
            logging.info(yml)
            # logging.info(md)
    
    def set_title(self, title, dry_run):
        yml, md = self.read_md_file()
        yml["title"] = title
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.dump_to_file(yml=yml, md=md, dry_run=dry_run)

    def prepend_to_content(self, prefix_text, dry_run=True):
        (yml, md) = self.read_md_file()
        self.dump_to_file(yml=yml, md=prefix_text + md, dry_run=dry_run)

    def replace_content(self, new_content, dry_run=True):
        (yml, _) = self.read_md_file()
        self.dump_to_file(yml=yml, md=new_content, dry_run=dry_run)

    def replace_in_content(self, pattern, replacement, dry_run=True):
        (yml, md) = self.read_md_file()
        md = regex.sub(pattern=pattern, repl=replacement, string=md)
        self.dump_to_file(yml=yml, md=md, dry_run=dry_run)

    def split_to_bits(self, source_script = sanscript.DEVANAGARI, indexed_title_pattern="%02d %s", dry_run=False):
        """
        
        Implementation notes: md parsers oft convert to html or json. Processing that output would be more complicated than what we need here.
        :return: 
        """
        logging.debug("Processing file: %s", self.file_path)
        if os.path.basename(self.file_path) == "_index.md":
            out_dir = os.path.dirname(self.file_path)
        else:
            out_dir = os.path.join(os.path.dirname(self.file_path), os.path.basename(self.file_path).replace(".md", ""))
        (yml, md) = self.read_md_file()
        lines = md.splitlines(keepends=False)
        (lines_till_section, remaining) = get_lines_till_section(lines)
        sections = split_to_sections(remaining)
        for section_index, (title, section_lines) in enumerate(sections):
            if indexed_title_pattern is not None:
                title = sanscript.transliterate(indexed_title_pattern % (section_index + 1, title), sanscript.OPTITRANS, source_script)
            file_name = regex.sub("[ .]", "_", sanscript.transliterate(title, source_script, sanscript.OPTITRANS)) + ".md"
            file_path = os.path.join(out_dir, file_name)
            section_yml = {"title": title}
            section_md = "\n".join(reduce_section_depth(section_lines))
            md_file = MdFile(file_path=file_path)
            md_file.dump_to_file(yml = section_yml, md=section_md, dry_run=dry_run)
        
        remainder_file_path = os.path.join(out_dir, "_index.md")
        md = "\n".join(lines_till_section)
        logging.debug(yml)
        if not yml["title"].startswith("+"):
            yml["title"] = "+" + yml["title"] 
        MdFile(file_path=remainder_file_path).dump_to_file(yml=yml, md=md, dry_run=dry_run)
        if str(self.file_path) != str(remainder_file_path):
            logging.info("Removing %s as %s is different ", self.file_path, remainder_file_path)
            if not dry_run:
                os.remove(path=self.file_path)

    @classmethod
    def get_md_files_from_path(cls, dir_path, file_pattern, file_name_filter=None):
        from pathlib import Path
        # logging.debug(list(Path(dir_path).glob(file_pattern)))
        md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
        return [MdFile(path) for path in md_file_paths]

    @classmethod
    def fix_title_numbering_in_path(cls, dir_path, file_pattern="**/*.md",  dry_run=False):
        from pathlib import Path
        # logging.debug(list(Path(dir_path).glob(file_pattern)))
        md_files = MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern)
        for md_file in md_files:
            md_file.fix_title_numbering(dry_run=dry_run)


    @classmethod
    def set_titles_from_filenames(cls, dir_path, transliteration_target, file_pattern="**/*.md", dry_run=False):
        md_files = MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern)
        for md_file in md_files:
            md_file.set_title_from_filename(transliteration_target=transliteration_target, dry_run=dry_run)

    @classmethod
    def fix_index_files(cls, dir_path, transliteration_target=sanscript.DEVANAGARI, dry_run=False):
        # Get all non hidden directories.
        dirs = [x[0] for x in os.walk(dir_path) if "/." not in x[0]]
        # set([os.path.dirname(path) for path in Path(dir_path).glob("**/")])
        for dir in dirs:
            index_file = MdFile(file_path=os.path.join(dir, "_index.md"))
            index_file.set_title_from_filename(transliteration_target=transliteration_target, dry_run=dry_run)


    @classmethod
    def devanaagarify_titles(cls, md_files, dry_run=False):
        logging.info("Fixing titles of %d files", len(md_files))
        for md_file in md_files:
            # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
            logging.debug(md_file.file_path)
            title_fixed = sanscript.transliterate(data=md_file.get_title(), _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
            md_file.set_title(title=title_fixed, dry_run=dry_run)

    @classmethod
    def fix_titles(cls, md_files, 
                  spreadhsheet_id, worksheet_name, id_column, title_column, 
                  md_file_to_id, google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json', dry_run=False):
        # logging.debug(adhyaaya_to_mp3_map)
        logging.info("Fixing titles of %d files", len(md_files))
        from curation_utils.google import sheets
        doc_data = sheets.IndexSheet(spreadhsheet_id=spreadhsheet_id, worksheet_name=worksheet_name, google_key=google_key, id_column=id_column)
        for md_file in md_files:
            # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
            logging.debug(md_file.file_path)
            adhyaaya_id = md_file_to_id(md_file)
            if adhyaaya_id != None:
                logging.debug(adhyaaya_id)
                title = doc_data.get_value(adhyaaya_id, column_name=title_column)
                if title != None:
                    md_file.set_title(title=title, dry_run=dry_run)

    @classmethod
    def split_all_to_bits(cls, dir_path, file_pattern="*.md", dry_run=False):
        """
        
        :param dir_path: 
        :param file_pattern: For recursive splitting, use "**/*.md"
        :param dry_run: 
        :return: 
        """
        for md_file in MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern):
            md_file.split_to_bits(dry_run=dry_run)