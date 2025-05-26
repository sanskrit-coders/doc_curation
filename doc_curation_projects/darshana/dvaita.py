from regex import regex

from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.scraping.misc_sites import dvaita

from doc_curation.utils import patterns


def misc():

  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18485/18481/sharav/pathar/pathar", dest_path="/home/vvasuki/gitland/vishvAsa/mAdhvam/content/tattvam/padma-nAbhaH/padArtha-sangrahaH")

  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/19565/18484/sharav/mathha/managa", dest_path="/home/vvasuki/gitland/vishvAsa/mAdhvam/content/tattvam/padma-nAbhaH/madhva-siddhAnta-sAroddhAraH")

  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/19085/18678/sharav/sarava/upatha", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vijayIndra-tIrthAH/sarva-siddhAnta-sAra-vivechanam")

  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18411/18411/sharav/sharam", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vijayIndra-tIrthAH/madhva-siddhAnta-sAroddhAraH/")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18688/18680/sharav/braham/parath", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vijayIndra-tIrthAH/")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18733/18710/sharas/bhatha/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/satya-dhyAna-tIrthAH/bhedaparANi_hi_sUtrANi")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18766/18711/sharas/cathar/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/satya-dhyAna-tIrthAH/chandrikA-maNDanam")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/19180/19173/sharas/karama/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/satyAtma-tIrthAH/karma-vijayaH")
  # 
  # 
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/6161/6145/thavat/sharat/athhay/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/dvaita-dyumaNiH/sarva-prastutiH")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/17443/17436/sharam/yakata/ganaes/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vAdirAjaH/yukti-mallikA/sarva-prastutiH")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/19151/19150/sharav/mathha/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vanamAlI/madhva-mukhAlankAraH/sarva-prastutiH")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18668/18412/sharas/sharam/sharam/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/satya-pramodaH/nyAya-sudhA-maNDanam/sarva-prastutiH")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18582/18416/sharas/bhagav/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/satya-pramodaH/bhagavan-nirdoShatva-laxaNam/sarva-prastutiH")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18641/18620/sharas/sharav/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/satya-pramodaH/vijayIndra-vaibhavam/sarva-prastutiH")
  # 
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/18641/18620/sharas/sharav/managa", dest_path="/home/vvasuki/gitland/vishvAsa/mAdhvam/content/tattvam/vijayIndra-tIrthAH/sarva-siddhAnta-sAra-vivechanam/satya-pramoda-vijayIndra-vijaya-vaibhavam")
  # 
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/4438/4433/sharaj/parama/parata/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/jaya-tIrthaH/pramANa-paddhatiH/sarva-prastutiH")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/9011/4434/sharaj/vathav/vathav/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/jaya-tIrthaH/vAdAvalI/sarva-prastutiH")
  # 
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/13901/4778/sharav/nayaya/parath/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vyAsa-tIrthaH/nyAyAmRtam/sarva-prastutiH/")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/11066/4779/sharav/tatapa/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vyAsa-tIrthaH/tAtparya-chandrikA/sarva-prastutiH/")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/12775/4780/sharav/taraka/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vyAsa-tIrthaH/tarka-tANDavam/sarva-prastutiH/")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/12781/12778/sharav/bhatha/bhatha/bhatha", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vyAsa-tIrthaH/bhedojjIvanam/sarva-prastutiH/")



def dashaprakaraNAni():
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/13528/937/thasha/1-para/managa/garana", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/01-pramANa-laxaNam/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14026/938/thasha/2-kath/malma", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/02-kathA-laxaNam/mUlam")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14055/939/thasha/3-tata/malma", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/03-tattva-sankhyAnam/mUlam")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/4818/940/thasha/4-tata/mal", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/04-tattvoddyotaH/mUlam")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/4781/941/thasha/5-upat/mal", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/05-upAdhi-khaNDanam/mUlam")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/4733/942/thasha/6-maya/mal", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/06-mAyAvAda-khaNDanam/mUlam")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/4774/943/thasha/7-math/mal", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/07-mithyAtvAnumAna-khaNDanam/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/4826/944/thasha/8-vash/mal/parath", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/08-viShNu-tattva-nirNayaH/")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14061/945/thasha/9-kara/malma", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/09-karma-nirNayaH/mUlam")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14058/13524/thasha/10-tat/malma", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/10-prakaraNAni/10-tattva-vivekaH/mUlam")


def brahmasUtrAdi():
  pass
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/587/562/satara/1-brah/garana", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/bhAShyam/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/977/975/sharam/sathha/managa", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/anu-vyAkhyAnam/sarva-prastutiH/")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/15031/564/satara/3-naya/taka-t/parath/parath", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/nyAya-vivaraNam/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14989/565/satara/4-brah/malma/parath", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/madhvaH/aNu-bhAShyam/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/19135/19135/satara/6onaka", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/tattvam/vidyAdhIshaH/")


def purANAdi():
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/10778/10775/parana/sharam/parath/parath", dest_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/madhva-tAtparya-nirNayaH/sarva-prastutiH")
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14142/923/itahas/1-yama/malma", dest_path="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/kAvyam/padyam/madhvaH/yamaka-bhAratam")

def kAvyAdi():
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/10498/10497/samath/samath/parath", dest_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/kAvyam/nArAyaNa-paNDita-su-madhva-vijayaH/sarva-prastutiH")


def upaniShat():
  # dvaita.dump_series(url="https://dvaitavedanta.in/category-details/15940/928/upanas/3-mana/malma/parath", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/muNDakopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14152/925/upanas/1-iish/malma", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14165/926/upanas/2-kath/malma/parath/parath", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/15964/929/upanas/4-shha/malma/parath", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/prashnopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/15954/930/upanas/5-mana/malma/parath", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14224/931/upanas/6-aita/malma/thavat/parath", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/aitareya-brAhmaNam/upaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14233/932/upanas/7-tata/malma/shakas", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH/05_taittirIyopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14242/933/upanas/8-bhat/malma/tataya/ashava", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/shatapatha-brAhmaNam/17_bRhadAraNyakopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14295/934/upanas/9-chha/malma/parath", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/madhvaH/sarva-prastutiH")
  dvaita.dump_series(url="https://dvaitavedanta.in/category-details/14303/935/upanas/10-tal/malma/parath", dest_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/brAhmaNam/talavakAra-brAhmaNam/kenopaniShat/madhvaH/sarva-prastutiH")


def fix_details(dir_path):
  SHLOKA_PATTERN = r"(?<=\n|^)\# +(\S.+)\n+\# +(\S.+\s*?॥ *([०-९\d\.]+) *॥ *?(?=\n|$))"

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=SHLOKA_PATTERN, shloka_processor=lambda x: regex.sub(r"\# +", "", x).replace("\n\n", "  \n")))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.sections_to_details(content=c))


if __name__ == '__main__':
  pass
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/", overwrite=False, dry_run=False)
  # fix_details(dir_path="/home/vvasuki/gitland/vishvAsa/mAdhvam/content/kAvyam/nArAyaNa-paNDita-su-madhva-vijayaH/sarva-prastutiH")
  # upaniShat()
  misc()
  # dashaprakaraNAni()
  # kAvyAdi()
  # brahmasUtrAdi()
  # purANAdi()
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/", overwrite=False, dry_run=False)