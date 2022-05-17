import os

from doc_curation.scraping import gp



def dump_tulasi():
  base_dir = "/home/vvasuki/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/tulasIdAsa"
  # gp.dump_book(url="https://gitaseva.org/books/vinay-patrika", dest_html_path=os.path.join(base_dir, "vinaya-patrikA.html"), final_url_check=lambda x: "toc_marker-27" in x)
  # gp.dump_book(url="https://gitaseva.org/books/srikrishan-gitavali", dest_html_path=os.path.join(base_dir, "srikrishan-gitavali.html"), final_url_check=lambda x: "toc_marker-14" in x)
  # gp.dump_book(url="https://gitaseva.org/books/ramagya-prashan", dest_html_path=os.path.join(base_dir, "ramagya-prashan.html"), final_url_check=lambda x: "toc_marker-4" in x)
  # gp.dump_book(url="https://gitaseva.org/books/parvati-mangal", dest_html_path=os.path.join(base_dir, "parvati-mangal.html"), final_url_check=lambda x: "toc_marker-4" in x)
  # gp.dump_book(url="https://gitaseva.org/books/janki-mangal", dest_html_path=os.path.join(base_dir, "janki-mangal.html"))
  # gp.dump_book(url="https://gitaseva.org/books/hanuman-bahuk", dest_html_path=os.path.join(base_dir, "hanuman-bahuk.html"))
  # gp.dump_book(url="https://gitaseva.org/books/kavitavali", dest_html_path=os.path.join(base_dir, "kavitavali.html"))
  gp.dump_book(url="https://gitaseva.org/books/shri-ramchritmanas-satik", dest_html_path=base_dir)
  # TODO: The below did not work.
  # gp.dump_book(url="https://gitaseva.org/books/vairagya-sandipini", dest_html_path=os.path.join(base_dir, "vairagya-sandipini.html"))

def dump_suradas():
  # for (let x of document.querySelectorAll(".ebooks> a")) console.log("gp.dump_book(url=\"" + x.href + "\", dest_html_path=base_dir)")
  base_dir = "/home/vvasuki/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/suradAsa"
  # gp.dump_book(url="https://gitaseva.org/books/virah-padawali", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/sur-ramchritawali", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/anurag-padavali", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/sur-vinay-patrika", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/shri-krishan-bal-madhuri", dest_html_path=base_dir)


def dump_sanskrit():
  base_dir = "/home/vvasuki/vishvAsa/purANam/static/"
  # gp.dump_book(url="https://gitaseva.org/books/srimad-valmikiya-ramayan", dest_html_path=os.path.join(base_dir, "rAmAyaNam/goraxapura-pAThaH/source.html"), final_url_check=lambda x: "toc_marker-14" in x)
  # gp.dump_book(url="https://gitaseva.org/books/shrimad-bhagwat-mahapuran-with-hindi-explanation", dest_html_path=os.path.join(base_dir, "bhAgavatam/goraxapura-pAThaH/source.html"), "source.html"), final_url_check=lambda x: "toc_marker-32" in x)
  # gp.dump_book(url="https://gitaseva.org/books/shrimad-bhagwat-mahapuran-with-hindi-explanation", dest_html_path=os.path.join(base_dir, "viShNu-purANam/goraxapura-pAThaH/source.html"), final_url_check=lambda x: "toc_marker-9" in x)
  # gp.dump_book(url="https://gitaseva.org/books/sri-duga-saptshati-with-hindi-translation", dest_html_path=os.path.join(base_dir, "durgA-saptashatI/goraxapura-pAThaH/source.html"), final_url_check=lambda x: "toc_marker-20" in x)
  # gp.dump_book(url="https://gitaseva.org/books/adhyatam-ramayan", dest_html_path=os.path.join(base_dir, "adhyAtma-rAmAyaNam/goraxapura-pAThaH/source.html"), "source.html"), final_url_check=lambda x: "toc_marker-12" in x)

def dump_pUjA():
  base_dir = "/home/vvasuki/vishvAsa/purANam/static/misc-gp"
  # gp.dump_book(url="https://gitaseva.org/books/bhajnamrit", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/devi-stotra-ratnakar", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/sanskar-prakash", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/ganesh-stotra-ratnakar", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/rudrastadhayee", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/nitya-karm-pooja-prakash", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/shri-satya-narayan-vrat-katha", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/vrat-parichay", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/sahasranaam-stotra-sangrah", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/ganga-lahri", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/bhajan-sangrah", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/shatnaam-stotra-sangrah", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/shravan-maas-mahatmya", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/sri-krishan-leela-bhajnawali", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/chetavani-pad-sangrah", dest_html_path=base_dir)
  # gp.dump_book(url="https://gitaseva.org/books/strotratnavali", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/sandhya-sandhya-gayatri-ka-mahtav-aur-bhramchary", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/nityakarm-prayog", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/sri-hanumanchalisa", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/arti-sangrah", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/balivaishvadev-vidhi", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/tarpan-vidhi", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/sandhyopasan-vidhi-tarpan-and-balivaisavdev-vidhi", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/shiv-mahiman-stotra", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/aadityahardyastrotam", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/santan-gopal-stotra-santan-prapti-ke-shstriya-upay", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/nitya-stuti", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/anusmriti", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/bhismstavraj", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/gajal-gita", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/amog-shivkavch", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/sri-narayankavch", dest_html_path=base_dir)
  gp.dump_book(url="https://gitaseva.org/books/sri-durga-chalisa-and-sri-vindheyshwari-chalisa", dest_html_path=base_dir)

if __name__ == '__main__':
  dump_tulasi()
  # dump_suradas()
  # dump_pUjA()
  pass
