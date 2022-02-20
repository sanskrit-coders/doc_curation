import logging
import sys
import textwrap

import methodtools
from bs4 import BeautifulSoup
from curation_utils import file_helper
from sanskrit_data.schema import common
from sanskrit_data.schema.common import JsonObject

from doc_curation import text_utils
from indic_transliteration import deduplication, sanscript



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


class CommentaryKey(object):
  TEXT = "Text"
  VARIANT_JOINER = "\n_________\n"
  VISH = "विश्वास-प्रस्तुतिः"
  pass


class Quote(JsonObject):

  def __init__(self, variants, topics=None, sources=None, secondary_sources=None, commentaries=None, types=None, ratings=None, ornaments=None, sentiments=None, meter=None):
    self.topics = topics
    self.sources = sources
    self.secondary_sources = secondary_sources
    self.commentaries = commentaries if commentaries is not None else {}
    self.set_variants(variants=variants)
    self.types = types
    self.ratings = ratings
    self.ornaments = ornaments
    self.sentiments = sentiments
    self.meter = meter
    self._script = None
  
  def __repr__(self):
    return self.commentaries[CommentaryKey.TEXT]

  @methodtools.lru_cache()
  def get_variants(self):
    return self.commentaries[CommentaryKey.TEXT].split(CommentaryKey.VARIANT_JOINER)

  def get_variant_keys(self):
    return [file_helper.get_storage_name(text=x, max_length=None, source_script=self._script) for x in self.get_variants()]

  def set_variants(self, variants):
    self.commentaries[CommentaryKey.TEXT] = CommentaryKey.VARIANT_JOINER.join(variants)

  def get_text(self):
    return self.get_variants()[0]
  
  def get_key(self, max_length=MAX_KEY_LENGTH):
    return file_helper.get_storage_name(text=self.get_text().toLowerCase(), max_length=max(max_length, HARD_MAX_KEY_LENGTH), source_script=self._script)

  def make_title(self):
    return text_utils.title_from_text(text=self.get_text(), script=self._script)

  def to_metadata_md(self):
    metadata = self.to_json_map()
    metadata["title"] = self.make_title()
    commentaries = metadata.pop('commentaries', {})
    commentary_order = [CommentaryKey.VISH, "MT"]
    commentaries_sorted = [Commentary(name=name, content=commentary) for name, commentary in commentaries.items() if name in commentary_order]
    commentaries_sorted.extend([Commentary(name=name, content=commentary) for name, commentary in commentaries.items() if name not in commentary_order])
    detail_elements = [commentary.to_details_tag() for commentary in commentaries_sorted]
    md = "\n\n".join(detail_elements)
    return (metadata, md)

  @classmethod
  def from_metadata_md(cls, metadata, md):
    soup = BeautifulSoup(md, features="lxml")
    commentaries = {}
    for detail in soup.find("body").findChildren("details", recursive=False):
      summary = detail.find("summary")
      summary.extract()
      comment_key = summary.text
      if comment_key == "मूलम्":
        comment_key = CommentaryKey.TEXT
      commentaries[comment_key] = detail.text.strip()
    metadata.pop("title", None)
    obj = common.JsonObject.make_from_dict(input_dict=metadata)
    obj.commentaries = commentaries
    return obj


class Subhaashita(Quote):
  def __init__(self, variants, topics=None, sources=None, secondary_sources=None, commentaries=None, types=None, ratings=None, ornaments=None, sentiments=None, meter=None, script=sanscript.DEVANAGARI):
    super(Subhaashita, self).__init__(variants=variants, topics=topics, sources=sources, secondary_sources=secondary_sources, commentaries=commentaries, types=types, ratings=ratings, ornaments=ornaments, sentiments=sentiments, meter=meter)
    self._script=script

  def get_key(self, max_length=MAX_KEY_LENGTH):
    approx_key = deduplication.get_approx_deduplicating_key(text=self.get_text())
    return file_helper.get_storage_name(text=approx_key, max_length=max_length, source_script=self._script)

  def get_variant_keys(self):
    return [deduplication.get_approx_deduplicating_key(text=x) for x in self.get_variants()]


# Essential for depickling to work.
common.update_json_class_index(sys.modules[__name__])
logging.debug(common.json_class_index)
