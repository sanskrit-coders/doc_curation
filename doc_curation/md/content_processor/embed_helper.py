import regex


def set_audio_caption_from_filename(text, prefix):
  """
  
  Example: replace <div class="audioEmbed"  src="https://archive.org/download/tiruppAvai_vibhA/30__Vangakkadal_kadainda__suruTTi.mp3" caption=""></div>
  with 
  <div class="audioEmbed"  src="https://archive.org/download/tiruppAvai_vibhA/30__Vangakkadal_kadainda__suruTTi.mp3" caption="vibhA - 30 - Vangakkadal kadainda - suruTTi"></div>

  :param text: 
  :param prefix: 
  :return: 
  """
  def transformer(match):
    return "%s.mp3\" caption=\"%s - %s\"" % (match.group(1), prefix, match.group(1).replace("__", " - ").replace("_", " "))

  c = regex.sub(r"(?<=audioEmbed.+/)([^/]+?).mp3\" +caption=\".*?\"", transformer, text)
  
  return c
