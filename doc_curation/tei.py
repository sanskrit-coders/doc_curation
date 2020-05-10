import os

import lxml.etree as ET

from doc_curation import md_helper


def dump_md(tei_path, md_path):
    import subprocess
    # subprocess.call([os.path.join(os.path.dirname(__file__), "tei_xsl/bin/transformtei"),"--odd", tei_path, md_path])
    subprocess.call(["saxon", "-o:"+md_path, "-s:"+tei_path, os.path.join(os.path.dirname(__file__), "tei_xsl/markdown/tei-to-markdown-sarit.xsl")])


def dump_md_with_lxml(tei_path, md_path):
    dom = ET.parse(tei_path)
    xslt = ET.parse( os.path.join(os.path.dirname(__file__), "tei_xsl/markdown/tei-to-markdown.xsl"))
    transformer = ET.XSLT(xslt)
    newdom = transformer(dom)
    content = ET.tostring(newdom, pretty_print=True)
    md_file = md_helper.MdFile(file_path=md_path)
    md_file.dump_to_file(yml={}, md=content)
