"""
A package for curating doc file collections, with ability to sync with youtube and archive.org doc items. 
"""

def clear_bad_chars(file_path, dry_run=False):
    with open(file_path, 'r') as file:
        content = file.read()

    with open(file_path, 'w', newline='\n') as file:
        file.write(content)
    # def fix_line(line):
    #     line = line.replace("\r", "")
    #     return line
    # lines = [fix_line(line=line) for line in lines]
    # if not dry_run:
    #     with codecs.open(file_path, "w", 'utf-8') as file:
    #         file.writelines(lines)
    # else:
    #     logging.info(lines)


