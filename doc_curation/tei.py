"""
lxml does not support xslt 2.0, which is used by TEI. So, we're forced to use saxon.

NOTE:
  - xmlns of the xslt should match that of the xml. Eg. xmlns="http://www.tei-c.org/ns/1.0" . Else, the xslt won't be applied properly.

"""

import os


def dump_md(tei_path, md_path,
            xsl=os.path.join(os.path.dirname(__file__), "tei_xsl/markdown/tei-to-markdown-sarit.xsl")):
  # ALERT: Note that for this to work, it is essential that the below xmlns attribute be present:
  # <TEI xmlns="http://www.tei-c.org/ns/1.0">
  import subprocess
  # subprocess.call([os.path.join(os.path.dirname(__file__), "tei_xsl/bin/transformtei"),"--odd", tei_path, md_path])
  subprocess.call(["saxon", "-o:" + md_path, "-s:" + tei_path, xsl])


# noinspection PyUnresolvedReferences
def dump_md_via_lib(tei_path, md_path,
                    xsl=os.path.join(os.path.dirname(__file__), "tei_xsl/markdown/tei-to-markdown-sarit.xsl")):
  # To install the below:
  # Install Cython. 
  # ln -s /usr/share/Saxonica/SaxonHEC1.2.1/libsaxonhec.so /usr/lib
  # sudo ln -s /usr/share/Saxonica/SaxonHEC1.2.1/rt /usr/lib
  # Then follow https://www.saxonica.com/saxon-c/documentation/index.html#!starting/installingpython .
  import sys
  sys.path.append("/usr/share/Saxonica/SaxonHEC1.2.1/Saxon.C.API/python-saxon")
  import saxonc
  with saxonc.PySaxonProcessor(license=False) as proc:
    processor = proc.new_xslt30_processor()
    processor.set_cwd(".")
    processor.transform_to_file(source_file=tei_path, stylesheet_file=xsl, output_file=md_path)

