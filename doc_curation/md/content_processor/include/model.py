class Include(object):
  def __init__(self, url, field_names=None, classes=None, title=None, h1_level=2, extra_attributes=""):
    self.url = url
    self.field_names=field_names
    self.classes = classes
    self.title = title
    self.h1_level = h1_level
    self.extra_attributes = extra_attributes


  def to_html_str(self):
    field_names_str = ""
    if self.field_names is not None:
      field_names_str = "fieldNames=\"%s\"" % (",".join(self.field_names))
    classes_str = ""
    if self.classes is not None:
      classes_str = " ".join(self.classes)
    extra_attributes =  "%s %s" % (self.extra_attributes, " ".join([field_names_str]))
    if self.title == "FILE_TITLE":
      title_str = 'includeTitle="true"'
    elif self.title is not None:
      title_str = "title=\"%s\"" % self.title
    else:
      title_str = None
    if title_str is not None:
      extra_attributes = "%s %s" % (title_str, extra_attributes)
    return """<div class="js_include %s" url="%s"  newLevelForH1="%d" %s> </div>"""  % (classes_str,self.url, self.h1_level, extra_attributes)
