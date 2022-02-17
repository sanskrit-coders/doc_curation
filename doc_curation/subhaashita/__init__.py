from curation_utils import file_helper

from indic_transliteration import deduplication


class Quote(object):
  def __init__(self, text, variants=[], topics=[], authors=[], sources=[], commentaries={}, types=[], ratings={}, ornaments=[], sentiments=[], meter=""):
    self.text = text
    self.variants = variants
    self.topics = topics
    self.authors = authors
    self.sources = sources
    self.commentaries = commentaries
    self.types = types
    self.ratings = ratings
    self.ornaments = ornaments
    self.sentiments = sentiments
    self.meter = meter
  
  def get_key(self):
    return file_helper.get_storage_name(text=self.text)


class Subhaashita(Quote):
  def __init__(self, text, variants=[], topics=[], authors=[], sources=[], commentaries={}, types=[], ratings={}, ornaments=[], sentiments=[], meter=""):
    super(Subhaashita, self).__init__(text=text, variants=variants, topics=topics, authors=authors, sources=sources, commentaries=commentaries, types=types, ratings=ratings, ornaments=ornaments, sentiments=sentiments, meter=meter)

  def get_key(self):
    approx_key = deduplication.get_approx_deduplicating_key(text=self.text)
    return file_helper.get_storage_name(text=approx_key)
