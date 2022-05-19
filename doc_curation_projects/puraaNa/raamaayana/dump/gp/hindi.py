from doc_curation.scraping import html_scraper

detail_map = {
  "सूचना (हिन्दी)": [""],
  "भागसूचना": ["Numbers"],
  "विषय (हिन्दी)": ["Numbers"],
  "मूलम् (वचनम्)": ["Uwach"],
  "मूलम्": ["Shlok-Color-2", "SHLOK-Black", "SHLOK-Black-1"],
  "अनुवाद (हिन्दी)": ["TXT", "TXT-Right"],
  "मूलम् (समाप्तिः)": ["para-style-override-5"],
  "अनुवाद (समाप्ति)": ["Chapter-End-Text"],
  "प्रकाशनसूचना": [""],
  "पादटिप्पनी": ["Footnotes", "Footnotes-Bold", "Footnotes-Right-1"],
}

headings_map = {
  "## %s\n\n": ["Heading"],
  "### %s\n\n": ["Nayash", "Sub-Heading"],
  "": ["Page-Break-1"]
}


if __name__ == '__main__':
  html_scraper.get_class_counts(html="/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/goraxapura-pAThaH/raw/hindi.html", css_selector="p")
