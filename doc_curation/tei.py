import os

import lxml.etree as ET

from doc_curation import md_helper


def dump_md(tei_path, md_path, xsl=os.path.join(os.path.dirname(__file__), "tei_xsl/markdown/tei-to-markdown-sarit.xsl")):
    import subprocess
    # subprocess.call([os.path.join(os.path.dirname(__file__), "tei_xsl/bin/transformtei"),"--odd", tei_path, md_path])
    subprocess.call(["saxon", "-o:"+md_path, "-s:"+tei_path, xsl])

