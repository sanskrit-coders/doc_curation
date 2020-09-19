import subprocess

CALIBRE = 'ebook-convert'

def metadata_to_calibre_args(metadata):
    args = []
    for key, value in metadata.items():
        args.append('--%s' % key)
        args.append(value)
    return args


def make_kindle_file(content_file, outfile_path, metadata):
    base_args = [CALIBRE, content_file]
    # print(' '.join(base_args + [azw3_file] + options))
    options = metadata_to_calibre_args(metadata=metadata)
    subprocess.run(base_args + [outfile_path] + options, check=True)
    
