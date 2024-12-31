"""
A package for curating doc file collections, with ability to sync with youtube and archive.org doc items. 
"""
import codecs
import json
import logging

configuration = {}

def init_configuration(file_path='/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/site_config.json'):
  with open(file_path, 'r') as handle:
    configuration = json.load(handle)

init_configuration()
