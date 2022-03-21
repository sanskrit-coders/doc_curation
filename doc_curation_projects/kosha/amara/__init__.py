import logging
import os

import pandas

from doc_curation.md import library

varga_names_file = os.path.join(os.path.dirname(__file__), "varga_names.tsv")
varga_names = pandas.read_csv(varga_names_file, sep='\t', dtype={"id": str})
varga_names = varga_names.set_index("id")

