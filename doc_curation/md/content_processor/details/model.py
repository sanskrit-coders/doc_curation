import logging

from bs4 import BeautifulSoup


class Detail(object):
  def __init__(self, title, content):
    self.title = title
    self.content = content

  def __str__(self):
    return f"{self.title}: {self.content}"

  def to_md_html(self, attributes_str=None):
    if self.title is None:
      title = "Misc Detail"
      logging.warning(f"Unknown detail type for: {self.content}")
    else:
      title = self.title
    if attributes_str is None:
      if self.title in ["विश्वास-प्रस्तुतिः", "मूलम् (वचनम्)"]:
        attributes_str = "open"
      else:
        attributes_str = ""
    if attributes_str.strip() != "":
      attributes_str = " " + attributes_str
    return f"<details{attributes_str}><summary>{title}</summary>\n\n{self.content.strip()}\n</details>"

  def to_soup(self, attributes_str=None):
    return BeautifulSoup(self.to_md_html(attributes_str=attributes_str), 'html.parser')

  @classmethod
  def from_soup_tag(cls, detail_tag):
    if detail_tag == None or detail_tag.name != "details":
      return None
    title = detail_tag.select_one("summary").text.strip()
    detail_text = "".join([x.text for x in list(detail_tag.children)[1:]]).strip()
    return Detail(title=title, content=detail_text)
