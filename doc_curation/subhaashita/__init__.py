import logging
import sys
import textwrap

from bs4 import BeautifulSoup
from curation_utils import file_helper
from sanskrit_data.schema import common
from sanskrit_data.schema.common import JsonObject

from doc_curation import text_utils
from indic_transliteration import deduplication, sanscript


class Rating(JsonObject):
  def __init__(self, name, value):
    self.name = name
    self.value = value


class Commentary(JsonObject):
  def __init__(self, name, content):
    self.name = name
    self.content = content

  def to_details_tag(self):
    return textwrap.dedent("""
    <details><summary>%s</summary>
    
    %s
    </details>
    """) % (self.name, self.content)


HARD_MAX_KEY_LENGTH = 20
MAX_KEY_LENGTH = 10


class Quote(JsonObject):

  def __init__(self, text, variants=None, topics=None, sources=None, secondary_sources=None, commentaries=None, types=None, ratings=None, ornaments=None, sentiments=None, meter=None):
    self.text = text
    self.variants = variants
    self.topics = topics
    self.sources = sources
    self.secondary_sources = secondary_sources
    self.commentaries = commentaries
    self.types = types
    self.ratings = ratings
    self.ornaments = ornaments
    self.sentiments = sentiments
    self.meter = meter
    self._script = None
  
  def __repr__(self):
    return self.text
  
  def get_key(self, max_length=MAX_KEY_LENGTH):
    return file_helper.get_storage_name(text=self.text.toLowerCase(), max_length=max(max_length, HARD_MAX_KEY_LENGTH), source_script=self._script)

  def make_title(self):
    return text_utils.title_from_text(text=self.text, script=self._script)

  def to_metadata_md(self):
    metadata = self.to_json_map()
    core_text = metadata.pop("text")
    metadata["title"] = self.make_title()
    md = textwrap.dedent("""
    <details><summary>Text</summary>
    
    %s
    </details>
    """) % (core_text)
    commentaries = metadata.pop('commentaries', [])
    for commentary in commentaries:
      md += "\n%s" % commentary.to_details_tag()
    return (metadata, md)

  @classmethod
  def from_metadata_md(cls, metadata, md):
    soup = BeautifulSoup(md, features="lxml")
    commentaries = []
    text = None
    for detail in soup.find("body").findChildren("details", recursive=False):
      summary = detail.find("summary")
      summary.extract()
      if summary.text.strip() == "Text":
        text = detail.text.strip()
      else:
        commentaries.append(Commentary(name=summary.text, content=detail.text.strip()))
    metadata.pop("title", None)
    obj = common.JsonObject.make_from_dict(input_dict=metadata)
    obj.commentaries = commentaries
    obj.text = text
    return obj


class Subhaashita(Quote):
  def __init__(self, text, variants=None, topics=None, sources=None, secondary_sources=None, commentaries=None, types=None, ratings=None, ornaments=None, sentiments=None, meter=None, script=sanscript.DEVANAGARI):
    super(Subhaashita, self).__init__(text=text, variants=variants, topics=topics, sources=sources, secondary_sources=secondary_sources, commentaries=commentaries, types=types, ratings=ratings, ornaments=ornaments, sentiments=sentiments, meter=meter)
    self._script=script

  def get_key(self, max_length=MAX_KEY_LENGTH):
    approx_key = deduplication.get_approx_deduplicating_key(text=self.text)
    return file_helper.get_storage_name(text=approx_key, max_length=max_length, source_script=self._script)


# Essential for depickling to work.
common.update_json_class_index(sys.modules[__name__])
logging.debug(common.json_class_index)
