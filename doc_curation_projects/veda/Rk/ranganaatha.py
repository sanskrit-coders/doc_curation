import logging
import os

import regex

from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.content_processor.details_helper import Detail
from doc_curation.md.file import MdFile
from doc_curation_projects.veda import Rk
from indic_transliteration import sanscript

IN_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/saMhitA/ranganAthaH"

def prep_details(in_dir=IN_DIR):
  def _content_fixer(content, *args, **kwargs):
    def _detail_maker(match):
      local_title = f"रङ्गनाथः - {match.group(1)}"
      detail = Detail(title=local_title, content=match.group(5).strip())
      return f"{match.group(1)}\n\n{detail.to_md_html()}\n\n"
    content = regex.sub(r"(([०-९]+)\.([०-९]+)\.०*([०-९]+)) *\n+([^<]+?[।॥ ]+\4॥) *\n", _detail_maker, content)
    return content
    
  library.apply_function(fn=MdFile.transform, dir_path=in_dir, content_transformer=_content_fixer)


def export_to_files():
  rk_id_to_name = Rk.get_Rk_id_to_name_map_from_muulam()
  def _content_fixer(content, *args, **kwargs):
    details = details_helper.get_details(content=content, title=".*")
    for detail_tag, detail in details:
      id = detail.title.split(" - ")[-1]
      id_parts = [sanscript.transliterate(x, _from=sanscript.DEVANAGARI, _to=sanscript.IAST)   for x in id.split(".")]
      id_parts = [int(x) for x in id_parts]
      id_fixed = f"{id_parts[0]:02}/{id_parts[1]:03}/{id_parts[2]:02}"
      dest_name = rk_id_to_name[id_fixed]
      dest_path = os.path.join(Rk.commentary_base, f"{id_parts[0]:02}/{id_parts[1]:03}/{dest_name}.md")
      if not os.path.exists(dest_path):
        logging.fatal(f"File {dest_path} does not exist, skipping.")
        exit(1)
      md_file = MdFile(file_path=dest_path)
      md_file.replace_content_metadata(new_content=lambda c, *args, **kwargs: details_helper.insert_duplicate_adjascent(content=c, old_title_pattern="सायण(.*)", new_title="रङ्गनाथः", content_transformer=lambda c: detail.content.replace("\n", " "), *args, **kwargs), dry_run=False)
    return details_helper.detail_remover(content=content, title="रङ्गनाथः.*")

  library.apply_function(fn=MdFile.transform, dir_path=IN_DIR, content_transformer=_content_fixer)

def check_completeness():
  library.list_files_with_missing_details(src_dir=Rk.commentary_base, detail_title="रङ्गनाथः.*")


if __name__ == '__main__':
  pass
  prep_details()
  # export_to_files()
  # check_completeness()


"""
Completeness status

01/050/11_udyannadya_mitramaha.md - 0
01/062/01_pra_manmahe.md - 0
01/062/02_pra_vo.md - 0
01/062/03_indrasyAngirasAM_cheShTau.md - 0
01/062/04_sa_suShTubhA.md - 0
01/062/05_gRNAno_angirobhirdasma.md - 0
01/062/06_tadu_prayaxatamamasya.md - 0
01/062/07_dvitA_vi.md - 0
01/062/08_sanAddivaM_pari.md - 0
01/062/09_sanemi_sakhyaM.md - 0
01/062/10_sanAtsanILA_avanIravAtA.md - 0
01/062/11_sanAyuvo_namasA.md - 0
01/065/01_pashvA_na.md - 0
01/065/03_Rtasya_devA.md - 0
01/065/05_puShTirna_raNvA.md - 0
01/065/07_jAmiH_sindhUnAM.md - 0
01/065/09_shvasityapsu_haMso.md - 0
01/066/01_rayirna_chitrA.md - 0
01/066/03_dAdhAra_xemamoko.md - 0
01/066/05_durokashochiH_kraturna.md - 0
01/066/07_seneva_sRShTAmaM.md - 0
01/066/09_taM_vashcharAthA.md - 0
01/067/01_vaneShu_jAyurmarteShu.md - 0
01/067/03_haste_dadhAno.md - 0
01/067/05_ajo_na.md - 0
01/067/07_ya_IM.md - 0
01/067/09_vi_yo.md - 0
01/068/01_shrINannupa_sthAddivaM.md - 0
01/068/03_Aditte_vishve.md - 0
01/068/05_Rtasya_preShA.md - 0
01/068/07_hotA_niShatto.md - 0
01/068/09_piturna_putrAH.md - 0
01/069/01_shukraH_shushukvA_N.md - 0
01/069/03_vedhA_adRpto.md - 0
01/069/05_putro_na.md - 0
01/069/07_nakiShTa_etA.md - 0
01/069/09_uSho_na.md - 0
01/070/02_A_daivyAni.md - 0
01/070/03_garbho_yo.md - 0
01/070/04_adrau_chidasmA.md - 0
01/070/05_sa_hi.md - 0
01/070/06_etA_chikitvo.md - 0
01/070/07_vardhAnyaM_pUrvIH.md - 0
01/070/08_arAdhi_hotA.md - 0
01/070/09_goShu_prashastiM.md - 0
01/070/10_vi_tvA.md - 0
01/070/11_sAdhurna_gRdhnurasteva.md - 0
01/091/16_A_pyAyasva.md - 0
01/091/17_A_pyAyasva.md - 0
01/139/07_o_ShU.md - 0
01/163/05_imA_te.md - 0
01/169/01_mahashchittvamindra_yata.md - 0
01/169/02_ayujranta_indra.md - 0
01/169/03_amyaksA_ta.md - 0
01/169/04_tvaM_tU.md - 0
01/169/05_tve_rAya.md - 0
01/169/06_prati_pra.md - 0
01/169/07_prati_ghorANAmetAnAmayAsAM.md - 0
01/169/08_tvaM_mAnebhya.md - 0
01/180/07_vayaM_chiddhi.md - 0
01/187/11_taM_tvA.md - 0
02/017/09_nUnaM_sA.md - 0

03/059/01_mitro_janAnyAtayati.md - 0
03/059/02_pra_sa.md - 0
03/059/03_anamIvAsa_iLayA.md - 0
03/059/04_ayaM_mitro.md - 0
03/059/05_mahA_N_Adityo.md - 0
03/059/06_mitrasya_charShaNIdhRto_avo.md - 0
03/059/07_abhi_yo.md - 0
03/059/08_mitrAya_pancha.md - 0
03/059/09_mitro_deveShvAyuShu.md - 0

04/042/06_ahaM_tA.md - 0

05/043/16_urau_devA.md - 0
05/043/17_samashvinoravasA_nUtanena.md - 0
05/044/15_agnirjAgAra_tamRchaH.md - 0
05/062/01_Rtena_RtamapihitaM.md - 0
05/062/02_tatsu_vAM.md - 0
05/062/03_adhArayataM_pRthivImuta.md - 0
05/062/04_A_vAmashvAsaH.md - 0
05/062/05_anu_shrutAmamatiM.md - 0
05/062/06_akravihastA_sukRte.md - 0
05/062/07_hiraNyanirNigayo_asya.md - 0
05/062/08_hiraNyarUpamuShaso_vyuShTAvayaHsthUNamuditA.md - 0
05/062/09_yadbaMhiShThaM_nAtividhe.md - 0
06/015/01_imamU_Shu.md - 0
06/015/02_mitraM_na.md - 0
06/015/03_sa_tvaM.md - 0
06/015/04_dyutAnaM_vo.md - 0
06/015/05_pAvakayA_yashchitayantyA.md - 0
06/015/06_agnimagniM_vaH.md - 0
06/015/07_samiddhamagniM_samidhA.md - 0
06/015/08_tvAM_dUtamagne.md - 0
06/015/09_vibhUShannagna_ubhayA_N.md - 0
06/015/10_taM_supratIkaM.md - 0
06/015/11_tamagne_pAsyuta.md - 0
06/015/12_tvamagne_vanuShyato.md - 0
06/015/13_agnirhotA_gRhapatiH.md - 0
06/015/14_agne_yadadya.md - 0
06/015/15_abhi_prayAMsi.md - 0
06/015/16_agne_vishvebhiH.md - 0
06/015/17_imamu_tyamatharvavadagniM.md - 0
06/015/18_janiShvA_devavItaye.md - 0
06/015/19_vayamu_tvA.md - 0
06/017/03-05ab.md - 0
06/032/01_apUrvyA_purutamAnyasmai.md - 0
06/059/07_indrAgnI_A.md - 0
06/059/08_indrAgnI_tapanti.md - 0
06/059/09_indrAgnI_yuvorapi.md - 0
06/059/10_indrAgnI_ukthavAhasA.md - 0
06/060/03_A_vRtrahaNA.md - 0
06/060/06_hato_vRtrANyAryA.md - 0
06/064/01_udu_shriya.md - 0
06/064/02_bhadrA_dadRxa.md - 0
06/064/03_vahanti_sImaruNAso.md - 0
06/064/04_sugota_te.md - 0
06/064/05_sA_vaha.md - 0
06/064/06_utte_vayashchidvasaterapaptannarashcha.md - 0
07/041/01_prAtaragniM_prAtarindraM.md - 2
07/041/02_prAtarjitaM_bhagamugraM.md - 2
07/041/03_bhaga_praNetarbhaga.md - 2
07/041/04_utedAnIM_bhagavantaH.md - 2
07/041/05_bhaga_eva.md - 2
07/041/06_samadhvarAyoShaso_namanta.md - 2
07/041/07_ashvAvatIrgomatIrna_uShAso.md - 2
07/070/07_iyaM_manIShA.md - 0
07/073/05_A_pashchAtAnnAsatyA.md - 0

08/006/19_imAsta_indra.md - 0
08/012/29_yadA_te.md - 0
08/033/09_ya_ugraH.md - 0
08/033/10_satyamitthA_vRShedasi.md - 0
08/033/11_vRShaNaste_abhIshavo.md - 0
08/033/12_vRShA_sotA.md - 0
08/033/13_endra_yAhi.md - 0
08/033/14_vahantu_tvA.md - 0
08/033/15_asmAkamadyAntamaM_stomaM.md - 0
08/033/16_nahi_Shastava.md - 0
08/033/17_indrashchidghA_tadabravItstriyA.md - 0
08/033/18_saptI_chidghA.md - 0
08/070/02_indraM_taM.md - 0
08/070/06_A_paprAtha.md - 0
08/070/08_taM_vo.md - 0
08/070/10_tvaM_na.md - 0
08/070/14_bhUribhiH_samaha.md - 0
08/093/24_iha_tyA.md - 0
08/093/25_tubhyaM_somAH.md - 0
08/093/26_A_te.md - 0
09/009/05_tA_abhi.md - 0
09/026/04_tamahyanbhurijordhiyA_saMvasAnaM.md - 0
09/043/04_pavamAna_vidA.md - 0
09/092/01_pari_suvAno.md - 0
09/092/02_achChA_nRchaxA.md - 0
09/092/03_pra_sumedhA.md - 0
09/092/04_tava_tye.md - 0
09/092/05_tannu_satyaM.md - 0
09/092/06_pari_sadmeva.md - 0
09/097/31ff.md - 0
10/004/03_shishuM_na.md - 0
10/009/09_Apo_adyAnvachAriShaM.md - 0
10/043/10_gobhiShTaremAmatiM_durevAM.md - 0
10/043/11_bRhaspatirnaH_pari.md - 0
10/044/10_gobhiShTaremAmatiM_durevAM.md - 0
10/044/11_bRhaspatirnaH_pari.md - 0
10/086/16_na_seshe.md - 0
10/106/11_RdhyAma_stomaM.md - 0
10/130/03_kAsItpramA_pratimA.md - 0
10/131/06_indraH_sutrAmA.md - 0
10/131/07_tasya_vayaM.md - 0
10/180/03_indra_xatramabhi.md - 2

"""