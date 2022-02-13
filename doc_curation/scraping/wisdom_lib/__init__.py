

def footnote_extractor(soup):
  footnote_elements = soup.select("section.footnotes div.f")
  content_out = ""
  for tag in footnote_elements:
    footnote_id = tag.find('p', {'class': 'nr'}).text.replace("[", "[^")
    definition = tag.findChild("div").text.strip()
    content_out += "\n\n%s %s" % (footnote_id, definition)
  content_out = content_out.replace("", " - ")
  return content_out