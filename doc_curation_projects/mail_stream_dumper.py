import regex, os
from doc_curation import md
from doc_curation.md import library
from doc_curation.md.file import MdFile
from curation_utils import scraping, file_helper


def dump_sadaasvaada(messages, subject, dest_dir, url, dry_run=False):
  subject = regex.sub("Sadāsvāda[ -]*", "", subject)
  title = messages[0].date.strftime('%Y-%m-%d') + "__" + subject
  file_name = os.path.join(dest_dir, file_helper.get_storage_name(title))
  md_file = MdFile(file_path=os.path.join(dest_dir, file_name + ".md"))
  content = ""
  for index, message in enumerate(messages):
    content = f"{content}\n\n{message.content}"
  md_file.dump_to_file(content=message.content, metadata={"title": title}, dry_run=dry_run)


def scrape_groups():
  from doc_curation.mail_stream import mailman
  # mailman.scrape_months(url="https://list.indology.info/pipermail/indology/", list_id="[INDOLOGY] ", dest_dir_base="/home/vvasuki/hindu-comm/mail_stream_indology/", dry_run=False)
  mailman.scrape_months(url="https://lists.advaita-vedanta.org/archives/advaita-l/", list_id="[Advaita-l] ", dest_dir_base="/home/vvasuki/hindu-comm/mail_stream_advaita-l/", dry_run=False)
  pass

def dump_google_groups():
  from doc_curation.mail_stream import mailman, google_groups
  pass
  # google_groups.scrape_threads(url="https://groups.google.com/g/hindu-vidya", dest_dir="/home/vvasuki/hindu-comm/hindu-vidya", dry_run=False)
  google_groups.scrape_threads(url="https://groups.google.com/g/advaitin", dest_dir="/home/vvasuki/hindu-comm/advaitin", dry_run=False, start_url="YlKKle4tC2s")
  # google_groups.scrape_threads(url="https://groups.google.com/g/sadaswada", dest_dir="/home/vvasuki/vishvAsa/kAvyam/content/AsvAdaH/sadAsvAdaH", dumper=dump_sadaasvaada, dry_run=False)
  # google_groups.scrape_threads(url="https://groups.google.com/g/bvparishat", dest_dir="/home/vvasuki/hindu-comm/bvparishat", dry_run=False, start_url="ry4713TxiuQ")
  # google_groups.scrape_threads(url="https://groups.google.com/g/samskrita", dest_dir="/home/vvasuki/hindu-comm/samskrita", dry_run=False, start_url="qVDwKqFADvg")
  # google_groups.get_thread_messages_selenium(url="https://groups.google.com/g/bvparishat/c/vkOvpkrL97o")

def word_clouds():
  stop_words = ["https", "groups", "group", "google", "com", "email", "subscribed", "msgid", "wrote", "gmail", "regards", "samskrita", "bvparishat", "http", "googlegroups", "तव", "send", "post", "discussion", "unsubscribe", "namaste", "PM", "AM", "footer", "Professor", "Source"]
  library.dump_word_cloud(src_path="/home/vvasuki/hindu-comm/samskrita", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/vishvAsa/kAvyam/content/AsvAdaH/sadAsvAdaH", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/vishvAsa/kAvyam/content/AsvAdaH/sadAsvAdaH", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/hindu-comm/mail_stream_indology", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/hindu-comm/mail_stream_advaita-l", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/hindu-comm/hindu-vidya", dest_path="word-clouds/general.png", stop_words=stop_words)


if __name__ == '__main__':
  # word_clouds()
  # scrape_groups()
  dump_google_groups()
  pass
