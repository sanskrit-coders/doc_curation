import collections
import copy
import logging

import regex
from bs4 import BeautifulSoup, NavigableString
from bs4.element import PageElement
from doc_curation.md import content_processor
from doc_curation.md.content_processor.details.common import _denumerify, _get_number, _normalize_spaces
from doc_curation.md.content_processor.details.model import Detail
from doc_curation.md.content_processor.details.seeker import get_nieghbor_detail
from doc_curation.md.content_processor.footnote.helper import Footnote
from doc_curation.scraping.html_scraper import souper
from indic_transliteration import sanscript


def transform_details_with_soup(content, content_str_transformer=None, title_transformer=None, title_pattern=None, details_css="body>details", *args, **kwargs):
  metadata = kwargs.get("metadata", None)

  # Stray usage of < can fool the soup parser. Keep this as a cheap guard,
  # but make it a bit more specific than "details" in content.
  if "<details" not in content.lower():
    return content

  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content

  # Note - fixes only top level details (by default selector).
  details = soup.select(details_css)

  for detail_tag in details:
    if title_pattern is not None and not regex.fullmatch(title_pattern, detail_tag.select_one("summary").text):
        continue

    if title_transformer is not None:
      detail_tag.select_one("summary").string = title_transformer(detail_tag.select_one("summary").text)
    if content_str_transformer is not None:
      # Transform descendant text nodes, excluding anything inside <summary>.
      # Snapshot the strings since we'll mutate the tree during replacement.
      for s in list(detail_tag.find_all(string=True)):
        if isinstance(s, NavigableString):
          if s.parent is not None and s.parent.name == "summary":
            continue
          if str(s).strip() == "":
            continue
          s.replace_with(
            content_str_transformer(str(s), *args, **kwargs)
          )

    # Prevent repeated runs from accumulating extra newlines.
    nxt = detail_tag.next_sibling
    if not (isinstance(nxt, NavigableString) and str(nxt) == "\n"):
      detail_tag.insert_after("\n")

  return content_processor._make_content_from_soup(soup=soup)

def open_attribute_fixer(detail_tag, *args, **kwargs):
  if "open" in detail_tag.attrs:
    detail_tag["open"] = ""

def transform_detail_tags_with_soup(content, transformer, title_pattern=None, details_css="body>details", *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=kwargs.get('metadata', None))
  if soup is None:
    return content
  details = soup.select(details_css)

  details = sorted(
    details,
    key=lambda tag: len(list(tag.parents)),
    reverse=True
  )
  
  for detail_tag in list(details):
    if detail_tag.parent is None:
      # detail_tag.decompose() may have been called.
      continue
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    if title_pattern is None or regex.fullmatch(title_pattern, detail.title):
      transformer(detail_tag, *args, **kwargs)
  return content_processor._make_content_from_soup(soup=soup)

def detail_remover(content, title_pattern, *args, **kwargs):
  return transform_detail_tags_with_soup(content=content, title_pattern=title_pattern, transformer=lambda x, *args, **kwargs: x.decompose(), *args, **kwargs)

def adjascent_inserter(detail_tag, metadata, neighbor_maker, inserter=PageElement.insert_after):
  detail = Detail.from_soup_tag(detail_tag=detail_tag)
  neighbor = neighbor_maker(detail)
  if neighbor is None:
    return 
  inserter(detail_tag, "\n\n")
  inserter(detail_tag, neighbor)
  inserter(detail_tag, "\n\n")

def add_detail_footnotes(content, remove_detail=False, *args, **kwargs):
  def transformer(detail_tag, *args, **kwargs):
    if detail_tag.get("open") is not None:
      return 
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    previous_details = detail_tag.find_all_previous(name=detail_tag.name)
    footnote = Footnote(id_str=f"fn_det_{detail.title[:3]}_{len(previous_details)}", content=detail.content)

    detail_tag.insert_after(f"\n\n({detail.title}{footnote.get_reference()})\n\n{footnote.to_definition()}\n\n")

  detail_css = "details:not([open])"
  content = transform_detail_tags_with_soup(content=content, metadata=None, transformer=transformer, details_css=detail_css)

  if remove_detail:
    # We don't want to affect len(previous_details) in footnote numbering - so we remove the details separately.
    def remover(detail_tag, *args, **kwargs):
      if detail_tag.get("open") is not None:
        return
      detail_tag.decompose()
    content = transform_detail_tags_with_soup(content=content, metadata=None, transformer=remover, details_css=detail_css)


  return content

def details_to_latex(content, *args, **kwargs):
  def transformer(detail_tag, *args, **kwargs):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    detail_tag.insert_after(f"\\begin{{tcolorbox}}[title={{{detail.title}}}]\n{detail.content}\n\\end{{tcolorbox}}\n")

  detail_css = "details"
  content = transform_detail_tags_with_soup(content=content, metadata=None, transformer=transformer, details_css=detail_css)
  def remover(detail_tag, *args, **kwargs):
    detail_tag.decompose()
  content = transform_detail_tags_with_soup(content=content, metadata=None, transformer=remover, details_css=detail_css)
  return content

def dedetailsify(content, title_pattern=None, title_maker=None, *args, **kwargs):
  if title_maker is None:
    title_maker = lambda x: f"**{x}**—\n"
  def transformer(detail_tag, *args, **kwargs):
    # Remove all details contents and place them next to the details tag.
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    summary = detail_tag.select_one("summary")
    if summary is None:
      # Nothing reliable to move; let the later "remover" decompose the tag.
      return

    # IMPORTANT:
    # - summary.find_next_siblings() returns only *tags* (skips text nodes),
    #   so text would stay inside <details> and get destroyed by decompose().
    # - Using summary.next_siblings preserves BOTH tags and NavigableStrings.
    nodes_to_move = list(summary.next_siblings)
    if isinstance(nodes_to_move[0], NavigableString):
      nodes_to_move[0] = NavigableString(title_maker(detail.title) + nodes_to_move[0].lstrip())
    else:
      nodes_to_move = [NavigableString(title_maker(detail.title))] + nodes_to_move

    # Move nodes out of <details> while preserving their original order.
    # We insert in reverse so the final order after detail_tag matches the original.
    for node in reversed(nodes_to_move):
      node.extract()
      detail_tag.insert_after(node)

  detail_css = "details"
  content = transform_detail_tags_with_soup(content=content, metadata=None, transformer=transformer, title_pattern=title_pattern, details_css=detail_css)
  def remover(detail_tag, *args, **kwargs):
    detail_tag.decompose()
  content = transform_detail_tags_with_soup(content=content, metadata=None, title_pattern=title_pattern, transformer=remover, details_css=detail_css)
  return content

def transliterate_details(content, source_script, dest_script=sanscript.DEVANAGARI, title=None):
  def transformer(detail_tag, *args, **kwargs):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    new_text = content_processor.transliterate(text=detail.content, source_script=source_script, dest_script=dest_script)
    new_text = f"\n\n{new_text}\n"
    for child in list(detail_tag.children)[1:]:
      child.extract()
    list(detail_tag.children)[0].insert_after(new_text)

  return transform_detail_tags_with_soup(content=content, transformer=transformer, title_pattern=title)

def insert_duplicate_adjascent(content, old_title_pattern="मूलम्(.*)", new_title=r"विश्वास-प्रस्तुतिः\1", inserter=PageElement.insert_before, content_transformer=lambda x:x, *args, **kwargs):
  if new_title in content:
    logging.error(f"{new_title} already present. returning")
    return content
  def transformer(detail_tag, *args, **kwargs):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    detail.title = regex.sub(old_title_pattern, new_title, detail.title)
    detail.content = content_transformer(detail.content)
    attribute_str = None
    if new_title.startswith("विश्वास-प्रस्तुतिः"):
      attribute_str = "open"
    inserter(detail_tag, "\n\n")
    inserter(detail_tag, detail.to_soup(attributes_str=attribute_str))
    inserter(detail_tag, "\n\n")
    if "open" in detail_tag and "मूलम्" in old_title_pattern:
      del detail_tag["open"]

  content = transform_detail_tags_with_soup(content=content, transformer=transformer, title_pattern=old_title_pattern, *args, **kwargs)
  content.replace("open=\"\"", "open")
  if "मूलम्" in old_title_pattern:
    content.replace("<details open><summary>मूलम्", "<details><summary>मूलम्")
  return content

def insert_adjascent_element(content, metadata, title, new_element, inserter=PageElement.insert_after):
  # Stray usage of < can fool the soup parser. Hence the below.
  def _get_soup_element(new_element):
    if isinstance(new_element, str):
      new_element = BeautifulSoup(new_element, 'html.parser')
    if isinstance(new_element, Detail):
      new_element = new_element.to_soup()
    return new_element

  if title is None:
    new_element = _get_soup_element(new_element)
    soup = content_processor._soup_from_content(content=content, metadata=metadata)
    soup.body.append(new_element)
    return content_processor._make_content_from_soup(soup=soup)
  if "details" not in content or not regex.search(title, content):
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  new_element = _get_soup_element(new_element)
  details = soup.select("details")
  for detail in details:
    if regex.fullmatch(title, detail.select_one("summary").text.strip()):
      inserter(detail, "\n\n")
      inserter(detail, copy.copy(new_element))
      inserter(detail, "\n\n")
    # inserter(detail, "\n")
  return content_processor._make_content_from_soup(soup=soup)

def remove_adjascent_duplicates(content):
  content = regex.sub(r"(<details><summary>.+</summary>[^<]+</details>)\n+(?=\1)", "", content)
  return content

def rearrange_details(content, metadata, titles, *args, if_adjacent=False, **kwargs):
  # UNTESTED
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  # Don't pick up details within details.
  details = soup.find_all(lambda x: x.name == 'details' and x.find_parent("details") is None)
  if if_adjacent:
    return _rearrange_adjacent_details(soup=soup, details=details, titles=titles)
  final_details = []
  title_to_detail = collections.defaultdict(lambda:collections.defaultdict(list))
  for detail in details:
    title = detail.select_one("summary").text
    number = _get_number(title=title)
    title_denumerified = _denumerify(title)
    if title in titles:
      title_to_detail[title_denumerified][number].append(detail)
    else:
      title_to_detail["unarranged"][number].append(detail)
  def _get_details_with_id(id):
    details_list = []
    for title in titles + ["unarranged"]:
      details_list.extend(title_to_detail[title][id])
    details_list.extend(title_to_detail["unarranged"][id])
    return details_list
  for title in titles + ["unarranged"]:
    for id in title_to_detail[title].keys():
      if detail not in final_details:
        final_details.extend(_get_details_with_id(id=id))
  current_detail = final_details[0]
  for index, detail in enumerate(final_details[1:]):
    spacer = NavigableString("\n\n")
    current_detail.insert_after(spacer)
    spacer.insert_after(detail)
    current_detail = detail
  # for index, detail in enumerate(final_details[1:]):
  #   detail.decompose()
  content_out = content_processor._make_content_from_soup(soup=soup)
  return content_out

def _rearrange_adjacent_details(soup, details, titles):
  """Reorder only directly-adjacent details, in place.

  Top-level details are partitioned into runs: consecutive details separated
  by whitespace alone whose titles are all in `titles`. Anything else (other
  titles, headings, text, footnote definitions) splits runs and is never
  crossed. Within each run, details are stably sorted by `titles` order.
  Single-element and already-ordered runs are untouched. Idempotent.
  """
  def _title(tag):
    summary = tag.select_one("summary")
    return summary.text.strip() if summary is not None else ""

  def _gap_is_blank(a, b):
    sib = a.next_sibling
    while sib is not None and sib is not b:
      if not (isinstance(sib, NavigableString) and not str(sib).strip()):
        return False
      sib = sib.next_sibling
    return sib is b

  runs, cur = [], []
  for tag in details:
    if _title(tag) in titles and cur and _gap_is_blank(cur[-1], tag):
      cur.append(tag)
    elif _title(tag) in titles:
      if cur:
        runs.append(cur)
      cur = [tag]
    else:
      if cur:
        runs.append(cur)
        cur = []
  if cur:
    runs.append(cur)
  changed = False
  for run in runs:
    ordered = sorted(run, key=lambda t: titles.index(_title(t)))
    if [id(t) for t in ordered] == [id(t) for t in run]:
      continue
    parent = run[0].parent
    nxt = run[-1].next_sibling
    for tag in run:
      tag.extract()
    for tag in ordered:
      if nxt is not None:
        nxt.insert_before(tag)
      else:
        parent.append(tag)
    changed = True
  if changed:
    return _normalize_spaces(content_processor._make_content_from_soup(soup=soup))
  return content_processor._make_content_from_soup(soup=soup)

def merge_details(content, titles):
  """Merge source details into the corresponding target detail of the same unit.

  titles[0] is the target title (eg. "अनुवाद (हिन्दी)"); titles[1:] are source
  titles (eg. "पादटिप्पनी"). Each source block's content is appended to the
  nearest preceding target-titled block in the same verse unit (units are split
  at विश्वास-प्रस्तुतिः blocks; wrapper blocks such as सर्वाष् टीकाः are
  transparent); if no target precedes it, the nearest following target in the
  unit is used instead. Source blocks are removed. Units without any target
  block are left untouched. Idempotent.
  """
  if "details" not in (content or "") or not titles:
    return content
  if isinstance(titles, str):
    titles = [titles]
  target_title = titles[0].strip()
  source_titles = {t.strip() for t in titles[1:]}
  if not source_titles:
    return content
  tag_re = regex.compile(r"</details>|<details[^>]*>")
  summary_re = regex.compile(r"<summary>(.*?)</summary>", flags=regex.DOTALL)

  def split_top_level(text, base=0):
    spans, depth, start = [], 0, None
    for m in tag_re.finditer(text):
      if m.group().startswith("</"):
        if depth > 0:
          depth -= 1
          if depth == 0:
            spans.append((base + start, base + m.end()))
            start = None
      else:
        if depth == 0:
          start = m.start()
        depth += 1
    return spans

  def title_of(s, e):
    m = summary_re.search(content[s:e])
    return (m.group(1) or "").strip() if m else ""

  # Flat unit-flow sequence, descending into wrappers (one level).
  seq = []
  for (s, e) in split_top_level(content):
    t = title_of(s, e)
    inner_start = content.find("</summary>", s, e)
    inner_start = inner_start + len("</summary>") if inner_start != -1 else e
    if t and t not in source_titles and t != target_title and inner_start < e:
      inner = content[inner_start:e]
      kids = [k for k in split_top_level(inner, base=inner_start)
              if title_of(*k)]
      if kids and all(title_of(*k) != "विश्वास-प्रस्तुतिः" for k in kids):
        seq.extend([(ks, ke, title_of(ks, ke), True) for (ks, ke) in kids])
        continue
    seq.append((s, e, t, False))
  # Units split at विश्वास-प्रस्तुतिः.
  units, cur = [], []
  for item in seq:
    if item[2] == "विश्वास-प्रस्तुतिः":
      if cur:
        units.append(cur)
      cur = []
    else:
      cur.append(item)
  if cur:
    units.append(cur)

  def inner_of(s, e):
    m = summary_re.search(content[s:e])
    close = content.rfind("</details>", s, e)
    if m is None or close == -1:
      return ""
    return content[s + m.end():close]

  # (target_span, [source_spans]) in document order.
  merges = []
  for u in units:
    targets = [i for (i, x) in enumerate(u) if x[2] == target_title]
    if not targets:
      continue
    for (i, x) in enumerate(u):
      if x[2] not in source_titles:
        continue
      prev = [t for t in targets if t < i]
      tgt = prev[-1] if prev else min([t for t in targets if t > i])
      merges.append((u[tgt], x))
  if not merges:
    return content
  # Group sources per target, preserving document order.
  by_target = collections.OrderedDict()
  for (tgt, src) in merges:
    by_target.setdefault((tgt[0], tgt[1]), []).append(src)
  edits = []
  for ((ts, te), srcs) in by_target.items():
    m = summary_re.search(content[ts:te])
    close = content.rfind("</details>", ts, te)
    mend = ts + m.end()
    head = content[ts:mend]
    body = content[mend:close].rstrip()
    for (ss, se, _st, _w) in srcs:
      src_body = inner_of(ss, se).strip()
      if src_body:
        body = body + "\n\n" + src_body
    edits.append((ts, te, head + body + "\n</details>"))
    for (ss, se, _st, _w) in srcs:
      edits.append((ss, se, ""))
  out = content
  for (s, e, rep) in sorted(edits, key=lambda x: -x[0]):
    out = out[:s] + rep + out[e:]
  out = _normalize_spaces(out)
  return out

def lift_details_out_of_wrapper(content, titles, wrapper_title="सर्वाष् टीकाः"):
  """Move matching child details out of wrapper blocks, placing them above.

  Direct children of top-level <details><summary>wrapper_title</summary> blocks
  whose stripped summary title is in `titles` are lifted out and placed
  immediately above their wrapper, in original order. If a wrapper is left with
  no children (and no other content), it is removed. Child block text
  (including attributes like `open`) is preserved byte-for-byte. Everything
  else — including already-outside blocks — is untouched. Idempotent.
  """
  if "<details" not in (content or "") or not titles:
    return content
  if isinstance(titles, str):
    titles = [titles]
  wanted = {t.strip() for t in titles}
  tag_re = regex.compile(r"</details>|<details[^>]*>")
  summary_re = regex.compile(r"<summary>(.*?)</summary>", flags=regex.DOTALL)

  def split_level(text, base=0, level=0):
    """Spans at relative depth `level` (top-level = 0)."""
    spans, depth, start = [], 0, None
    for m in tag_re.finditer(text):
      if m.group().startswith("</"):
        if depth > 0:
          depth -= 1
          if depth == level and start is not None:
            spans.append((base + start, base + m.end()))
            start = None
      else:
        if depth == level:
          start = m.start()
        depth += 1
    return spans

  def title_of(s, e):
    m = summary_re.search(content[s:e])
    return (m.group(1) or "").strip() if m else ""

  edits = []
  for (s, e) in split_level(content):
    if title_of(s, e) != wrapper_title:
      continue
    m = summary_re.search(content[s:e])
    whead_end = s + m.end()
    close = content.rfind("</details>", s, e)
    inner = content[whead_end:close]
    kids = split_level(inner, base=whead_end, level=0)
    # (absolute spans of direct children with titles)
    kids = [(ks, ke) for (ks, ke) in kids if title_of(ks, ke)]
    if not kids:
      continue
    lifts = [(ks, ke) for (ks, ke) in kids if title_of(ks, ke) in wanted]
    if not lifts:
      continue
    keeps = [(ks, ke) for (ks, ke) in kids if title_of(ks, ke) not in wanted]
    # Non-details residue inside wrapper (stray text)?
    rest = inner
    for (ks, ke) in sorted(kids, reverse=True):
      rest = rest[:ks - whead_end] + rest[ke - whead_end:]
    lifted = "\n\n".join(content[ks:ke] for (ks, ke) in lifts)
    if keeps or rest.strip():
      kept = "\n\n".join(content[ks:ke] for (ks, ke) in keeps)
      body = (kept + ("\n\n" + rest.strip() if rest.strip() else ""))
      new_wrapper = content[s:whead_end] + "\n\n" + body + "\n</details>"
      edits.append((s, e, lifted + "\n\n" + new_wrapper))
    else:
      edits.append((s, e, lifted))
  if not edits:
    return content
  out = content
  for (s, e, rep) in sorted(edits, key=lambda x: -x[0]):
    out = out[:s] + rep + out[e:]
  out = _normalize_spaces(out)
  return out

def merge_successive(content, title_filter=".*"):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content)
  if soup is None:
    return content
  details = soup.select("details")
  final_details = []
  prev_detail = None
  prev_detail_tag = None
  
  
  
  for index, detail_tag in enumerate(details):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    title = _denumerify(detail.title)
    if prev_detail is not None:
      prev_title = _denumerify(prev_detail.title)
    if prev_detail is not None and title == prev_title and regex.fullmatch(title_filter, prev_title) and souper.is_prev_sibling(prev_detail_tag, detail_tag):
      prev_detail_tag.append(f"\n{detail.content}\n")
      detail_tag.decompose()
    else:
      prev_detail = detail
      prev_detail_tag = detail_tag
  content = content_processor._make_content_from_soup(soup=soup)
  content = _normalize_spaces(content)
  return content

def set_id_from_neighbor(content, target_title_pattern=".*", ref_title_pattern="मूलम्.+", seek_before=True, metadata=None):
  def copy_id(detail_tag, *args, **kwargs):
    ref_detail_tag = get_nieghbor_detail(detail_tag, seek_before=seek_before)
    ref_detail = Detail.from_soup_tag(detail_tag=ref_detail_tag)
    while ref_detail is not None and ref_detail.title is not None and not regex.fullmatch(ref_title_pattern, ref_detail.title):
      ref_detail_tag = get_nieghbor_detail(ref_detail_tag, seek_before=seek_before)
      ref_detail = Detail.from_soup_tag(detail_tag=ref_detail_tag)

    if ref_detail is None or not regex.fullmatch(ref_title_pattern, ref_detail.title):
      ref_detail = None
      return
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    base_title = detail.title.split(" - ")[0]
    ids = ref_detail.title.split(" - ")
    detail_tag.select_one("summary").string = " - ".join([base_title] + ids[1:])
  content = transform_detail_tags_with_soup(title_pattern=target_title_pattern, content=content, transformer=copy_id, metadata=metadata)
  return content

def autonumber_details(content, title_filter=".*", number_pattern=None, script = sanscript.DEVANAGARI):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content)
  if soup is None:
    return content
  details = soup.select("details")
  detail_counts = {}
  prev_detail = None
  prev_detail_tag = None
  for index, detail_tag in enumerate(details):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    title  = detail.title
    title = _denumerify(title)
    title_index = detail_counts.get(title, 0) + 1
    detail_counts[title] = title_index
    if number_pattern is not None:
      matches = list(regex.finditer(number_pattern, detail.content))
      if len(matches) == 0:
        title_index = None
      else:
        title_index = sanscript.get_number(matches[-1].group(1))
    if title_index is not None:
      index_str = "%02d" % title_index
      index_str = sanscript.transliterate(index_str, _to=script)
      list(detail_tag.children)[0].string = f"{title} - {index_str}"
  content = content_processor._make_content_from_soup(soup=soup)
  content = _normalize_spaces(content)
  return content

def detail_content_replacer_soup(detail_tag, replacement):
  summary = detail_tag.select_one("summary")
  detail = Detail.from_soup_tag(detail_tag=detail_tag)
  for x in summary.find_next_siblings():
    x.extract()
  for x in detail_tag.contents:
    if isinstance(x, NavigableString):
      x.extract()
  if callable(replacement):
    replacement = replacement(detail.content)
  summary.insert_after(f"\n\n{replacement}\n")
