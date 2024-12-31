"""
A package for curating doc file collections, with ability to sync with youtube and archive.org doc items. 
"""
import codecs
import json
import logging

configuration = {}
with open('/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/site_config.json', 'r') as handle:
  configuration = json.load(handle)

