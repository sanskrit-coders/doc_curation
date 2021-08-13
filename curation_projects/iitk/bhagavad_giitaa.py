from urllib.request import urlopen

from bs4 import BeautifulSoup

from doc_curation.md import library
import regex


title_to_folder_path = { 
  "मूल श्लोकः": "mUlam", 
  "Hindi Commentary By Swami Ramsukhdas": "hindI/rAmasukhadAsaH/TIkA", 
  "Harikrishnadas Goenka": "saMskRtam/shankaraH/hindI/harikRShNadAsaH", 
  "Anandgiri": "saMskRtam/AnandagiriH", 
  "Dhanpati": "saMskRtam/dhanapatiH", 
  "Madhavacharya": "saMskRtam/madhvaH", 
  "Neelkanth": "saMskRtam/nIlakaNThaH", 
  "Ramanuja": "saMskRtam/rAmAnujaH/mUlam", 
  "Sridhara": "saMskRtam/shrIdhara-svAmI", 
  "Vedantadeshikacharya": "saMskRtam/venkaTanAthaH", 
  "Adidevananda": "english/AdidevanandaH", 
  "English Translation By Swami Gambirananda": "english/gambhIrAnandaH",  
  "Shankaracharya's Sanskrit Commentary By Swami Gambirananda": "saMskRtam/shankaraH/gambhIrAnandaH", 
  "Chinmayananda": "hindI/chinmayAnandaH", 
  "Hindi Translation By Swami Ramsukhdas": "hindI/rAmasukhadAsaH/anuvAdaH", 
  "Swami Tejomayananda": "hindI/tejomayAnandaH/anuvAdaH", 
  "Sanskrit Commentary By Sri Abhinavgupta": "saMskRtam/abhinava-guptaH/mUlam", 
  "Jayatritha": "saMskRtam/jayatIrthaH", 
  "Madhusudan Saraswati": "saMskRtam/madhusUdana-sarasvatI",  
  "Purushottamji": "saMskRtam/puruShottamaH", 
  "Sanskrit Commentary By Sri Shankaracharya": "saMskRtam/shankaraH/mUlam", 
  "Vallabhacharya": "saMskRtam/vallabhaH", 
  "English Translation By Swami Sivananda": "english/shivAnandaH/anuvAdaH",
  "English Commentary By Swami Sivananda": "english/shivAnandaH/TIkA",
  "Abhinavgupta's Sanskrit Commentary By Dr. S. Sankaranarayan": "saMskRtam/abhinava-guptaH/english/shankaranArAyaNaH",
  "Ramanuja's Sanskrit Commentary By Swami Adidevananda": "saMskRtam/rAmAnujaH/english/AdidevAnandaH", 
  "Translation By By Dr. S. Sankaranarayan": "english/shankaranArAyaNaH", 
  "Purohit Swami": "english/purohitasvAmI"}


def dump_shloka_details(url, base_dir):
  chapter_id = regex.match("field_chapter_value=(\d+)", url).group(1)
  shloka_id = regex.match("field_nsutra_value=(\d+)", url).group(1)
  
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  part_divs = soup.select(".views-field")

  content_tag = part_div[0].select("font[size='3px']")
  shloka = souper.get_md_paragraph(content_tag.contents)
  metadata={title: title_from_text(text=shloka)}
  out_path = "%02d/%02d_%s.md" % (chapter_id, shloka_id, get_storage_name(text=title))
  dest_path = os.path.join(base_dir, "mUlam", out_path)
  
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata=metadata, content=shloka, dry_run=False)
  
  for part_div in part_divs[1:]:
    pass


if __name__ == '__main__':
    url = "https://www.gitasupersite.iitk.ac.in/srimad?language=dv&field_chapter_value=1&field_nsutra_value=1&htrskd=1&httyn=1&htshg=1&scsh=1&hcchi=1&hcrskd=1&scang=1&scram=1&scanand=1&scjaya=1&scmad=1&scval=1&scms=1&scsri=1&scvv=1&scpur=1&scneel=1&scdhan=1&ecsiva=1&etsiva=1&etpurohit=1&etgb=1&setgb=1&etssa=1&etassa=1&etradi=1&etadi=1&choose=1"
    dump_shloka_details(url=url, base_dir="/home/vvasuki/vishvAsa/purANam/static/mahAbhAratam/06-bhIShma-parva/02-bhagavad-gItA-parva")