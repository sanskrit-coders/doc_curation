import pytest

from doc_curation.sanskrit.accent.reconciler import (
  apply_marks_to_token,
  fill_vp_accents_from_padapatha,
  format_filled_vp_summary,
  format_padapatha_summary,
  format_suggested_vp_summary,
  parse_padapatha_items,
  reconcile_and_sync_markdown_blocks,
  reconcile_markdown_blocks,
  reconcile_vprastuti_and_tiikaa_texts,
  reconcile_vp_suggestions,
)


def test_apply_marks_to_token_preserves_clusters():
  assert apply_marks_to_token("ये᳓नावृत᳓ङ्", ["U", "U", "", ""]) == "ये᳓ना᳓वृतङ्"
  assert apply_marks_to_token("म᳓हतो", ["", "", "U"]) == "महतो᳓"
  assert apply_marks_to_token("विश्वं᳓", ["U", ""]) == "वि᳓श्वं"
  assert apply_marks_to_token("शा᳓न्तिश्शा᳓न्तिश्शा᳓न्तिः", ["U", "", "", "", "", ""]) == "शा᳓न्तिश्शान्तिश्शान्तिः"
  assert apply_marks_to_token("अ᳓जोऽन्यः", ["", "S", "U"]) == "अजो᳙ऽन्यः᳓"
  assert apply_marks_to_token("दानय्ँ", ["U", ""]) == "दा᳓नय्ँ"
  assert apply_marks_to_token("अग्निर्", ["", "U"]) == "अग्नि᳓र्"
  assert apply_marks_to_token("आ᳓ङ्क्ते᳓", ["U", ""]) == "आ᳓ङ्क्ते"


def test_reconcile_bold_sandhi_and_repeated_words():
  items = parse_padapatha_items(
    "- हृद᳓यम् → **हृ᳓दयम्** (*TS*, *RV*, *TB*)\n"
    "- च (अनुदात्तम्, पा॰ ८.१.१८)\n"
    "- अपि → **अ᳓पि** (*TS*, *RV*, *TB*, *AV*)\n"
    "- अधो᳓-मुखम् (*TS*)"
  )
  out, _ = reconcile_vp_suggestions("**हृद᳓यञ्** चाप्य् अधो᳓-मुखम्", items)
  assert out == "**[[हृद᳓यञ्|हृ᳓दयञ्]]** [[चाप्य्|चा᳓प्य्]] अधो᳓-मुखम्"

  items_rep = parse_padapatha_items(
    "- शा᳓न्तिः (*TS*, *RV*)\n"
    "- शा᳓न्तिः → **शान्तिः** (द्विर्वचने परस्यानुदात्तत्वम्, पा॰ ८.१.३)\n"
    "- शा᳓न्तिः → **शान्तिः** (द्विर्वचने परस्यानुदात्तत्वम्, पा॰ ८.१.३)"
  )
  out_rep, _ = reconcile_vp_suggestions("शा᳓न्तिश्शा᳓न्तिश्शा᳓न्तिः ।", items_rep)
  assert out_rep == "[[शा᳓न्तिश्शा᳓न्तिश्शा᳓न्तिः|शा᳓न्तिश्शान्तिश्शान्तिः]] ।"


def test_reconcile_onsetless_yan_and_space_rightward_sandhi():
  it_09 = parse_padapatha_items(
    "- दुरिताः᳓ (आरण्यक-पाठः)\n"
    "- अति → **अ᳓ति** (*TS*, *RV*, *TB*, *TK*)\n"
    "- अग्निः᳓ (*TS*, *RV*, *TB*, *TK*)"
  )
  assert reconcile_vp_suggestions("दुरिता᳓त्य् अग्निः᳓॥", it_09)[0] == "दुरिता᳓त्य् अग्निः᳓॥"

  it_m = parse_padapatha_items(
    "- नः (अनुदात्तम्, पा॰ ८.१.१८)\n"
    "- आ → **आ᳓** (*TS*, *RV*, *AV*)\n"
    "- अ᳓गात् → **अगात्** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*, *RV*)"
  )
  assert reconcile_vp_suggestions("न **आ᳓गाद्**", it_m)[0] == "न **आ᳓गाद्**"

  it_ag = parse_padapatha_items(
    "- प्रथम᳓म् (*TS*)\n"
    "- नु → **नु᳓** (*TS*)\n"
    "- आ → **आ᳓** (*TS*, *RV*, *AV*)\n"
    "- अगन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)"
  )
  assert reconcile_vp_suggestions("प्रथमं᳓ न्व् **आ᳓गन्**", it_ag)[0] == "प्रथमं᳓ न्व् **आ᳓गन्**"

  it_t = parse_padapatha_items(
    "- सवित्रे᳓ (*TS*)\n"
    "- तु → **तु᳓** (*TS*, *RV*, *TB*)\n"
    "- अर्भु-म᳓ते (*MW*)"
  )
  assert reconcile_vp_suggestions("सवित्रे᳓ त्वर्भुम᳓ते", it_t)[0] == "सवित्रे᳓ [[त्वर्भुम᳓ते|त्व᳙र्भुम᳓ते]]"

  it_a = parse_padapatha_items(
    "- न → **न᳓** (*TS*, *RV*)\n"
    "- अ᳓स्य (*TS*, *RV*)\n"
    "- अक्षः → **अ᳓क्षः** (*TS*, *RV*)"
  )
  assert reconcile_vp_suggestions("नास्या᳓क्षो", it_a)[0] == "[[नास्या᳓क्षो|ना᳓स्या᳓क्षो]]"


def test_reconcile_spaced_avagraha_ekadesha_and_revalidation():
  # पा॰ ८.२.५: anudātta + udātta अ᳓ -> udātta on Word1 (even across spaced ऽ)
  it_vid = parse_padapatha_items(
    "- विद्यते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*)\n"
    "- अ᳓यनाय (प्रातिपदिकम् अ᳓यन (*MW*))"
  )
  out_vid, logs_vid = reconcile_vp_suggestions("ना᳓न्यः᳓ प᳓न्था [[विद्यते᳓|विद्यते]] ऽयनाय । २", it_vid)
  assert out_vid == "ना᳓न्यः᳓ प᳓न्था विद्यते᳓ ऽयनाय । २"
  assert any("UNWRAP_SUG" in lg for lg in logs_vid)

  it_vac = parse_padapatha_items(
    "- वा᳓चस्पते (आमन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८, *TB*)\n"
    "- अ᳓च्छिद्रया (आरण्यक-पाठः (अनाम्नातम्))"
  )
  assert reconcile_vp_suggestions("[[वा᳓चस्पते᳓|वा᳓चस्पते]] ऽच्छिद्रया वाचा᳓ ।", it_vac)[0] == "वा᳓चस्पते᳓ ऽच्छिद्रया वाचा᳓ ।"

  # Update both Word1 ekādeśa and unelided tail of ऽWord2
  it_viv = parse_padapatha_items(
    "- वि᳓विच्यन्ते → **विविच्यन्ते** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)\n"
    "- अथ᳓ → **अ᳓थ** (*TS*, *RV*, *TB*, *TK*)"
  )
  out_viv, _ = reconcile_vp_suggestions("इह᳓ [[वि᳓विच्यन्ते|विविच्यन्ते]]\nऽथा᳓ यन्ति", it_viv)
  assert out_viv == "इह᳓ [[वि᳓विच्यन्ते|विविच्यन्ते᳓]]\n[[ऽथा᳓|ऽथा]] यन्ति"

  # Update invalid merged boundary while fixing double udātta
  it_raj = parse_padapatha_items(
    "- राजा → **रा᳓जा** (*TS*, *RV*, *TB*)\n"
    "- अभि → **अभि᳓** (*TS*, *RV*, *TB*, *TK*)"
  )
  assert reconcile_vp_suggestions("[[रा᳓जा᳓भि|रा᳓जा᳓भि᳓]]", it_raj)[0] == "[[रा᳓जा᳓भि|रा᳓जाभि᳓]]"

  # Punctuation prevents false cross-comma coalescence
  it_comma = parse_padapatha_items(
    "- ब्रह्म-कोश᳓म् (*TS*)\n- प्र᳓ (*TS*)\n- पद्ये (पा॰ ८.१.२८)\n- अमृ᳓तम् (*TS*, *RV*, *TB*)"
  )
  assert reconcile_vp_suggestions("ब्रह्मकोशं᳓ प्र᳓पद्ये,\nऽमृ᳓तं", it_comma)[0] == "ब्रह्मकोशं᳓ प्र᳓पद्ये,\nऽमृ᳓तं"

  # Savarṇa-dīrgha आ᳓ + अ stays आ᳓ (पा॰ ८.२.५), while ए᳓ + अ allows both S and U (पा॰ ८.२.६)
  it_sav = parse_padapatha_items("- आ᳓ (*TS*, *RV*, *AV*)\n- अस्मा᳓सु (*TS*, *RV*)")
  assert reconcile_vp_suggestions("आ᳓ ऽस्मा᳓सु", it_sav)[0] == "आ᳓ ऽस्मा᳓सु"

  it_ehi = parse_padapatha_items(
    "- शेषे (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)\n- आ᳓ (*TS*, *RV*, *AV*)\n- इहि (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)"
  )
  assert reconcile_vp_suggestions("उ᳓पशेष **[[ए᳓हि|एहि]]** ।", it_ehi)[0] == "उ᳓पशेष **ए᳓हि** ।"

  # Stale 1-to-1 suggestion matching PP is unwrapped cleanly
  it_pat = parse_padapatha_items("- पत᳓यन्ति (तिङः परं तिङ् न निहन्यते, पा॰ ८.१.२८)")
  assert reconcile_vp_suggestions("[[पत᳓यन्ति|पतयन्ति]] विद्यु᳓त", it_pat)[0] == "पत᳓यन्ति विद्यु᳓त"


def test_reconcile_markdown_blocks_skips_js_include_and_summary():
  assert format_padapatha_summary(0, 5) == "पद-पाठः (यान्त्रिकः)"
  assert format_padapatha_summary(2, 5) == "पद-पाठः (यान्त्रिकः - 2/5 व्यत्यस्त-स्वराः)"

  md = (
    '<div class="js_include" url="/foo">\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n[[विद्यते᳓|विद्यते]] ऽयनाय\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- विद्यते (पा॰ ८.१.२८)\n- अ᳓यनाय (*TS*)\n</details>\n"
    "</div>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n[[विद्यते᳓|विद्यते]] ऽयनाय\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- विद्यते (पा॰ ८.१.२८)\n- अ᳓यनाय (*TS*)\n</details>\n"
  )
  updated, logs = reconcile_markdown_blocks(md)
  assert len(logs) == 1
  # Inside js_include untouched; standalone inline block unwrapped
  assert updated.count("[[विद्यते᳓|विद्यते]]") == 1
  assert updated.count("विद्यते᳓ ऽयनाय") == 1


def test_reconcile_vprastuti_and_tiikaa_texts_preserves_frontmatter():
  vp = "+++\ntitle = \"test\"\n+++\n\nना᳓न्यः᳓ प᳓न्था [[विद्यते᳓|विद्यते]] ऽयनाय । २\n"
  tk = (
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- न᳓ (*TS*)\n- अन्यः᳓ (*TS*)\n- प᳓न्थाः (*TS*)\n"
    "- विद्यते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*)\n"
    "- अ᳓यनाय (*TS*)\n</details>\n"
  )
  out, _ = reconcile_vprastuti_and_tiikaa_texts(vp, tk)
  assert out.startswith("+++\ntitle = \"test\"\n+++\n\n")
  assert "विद्यते᳓ ऽयनाय" in out

  # Masks <div class="js_include">, stage-direction parens/brackets, and slices abbreviated '…' pratīkas
  vp_complex = (
    "+++\ntitle = \"complex\"\n+++\n\n"
    "(उत्तरस्याम्) धर्माय᳓ स्वा᳓हा [स्थू᳓णे अभि᳓रक्षतु] …।\n"
    "<div class=\"js_include\" url=\"/x.md\">\nधर्माय᳓\n</div>\n"
  )
  tk_complex = (
    "<details><summary>मूलम्</summary>\n\nधर्मा॑य॒ स्वाहा॑ । अ॒द्भ्यः स्वाहा॑ ।\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/4 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- धर्माय᳓ → **ध᳓र्माय** (*TS*)\n"
    "- स्वा᳓हा (*TS*)\n"
    "- अद्भ्यः᳓ (*TS*)\n"
    "- स्वा᳓हा (*TS*)\n</details>\n"
  )
  out_c, _ = reconcile_vprastuti_and_tiikaa_texts(vp_complex, tk_complex)
  assert "(उत्तरस्याम्) [[धर्माय᳓|ध᳓र्माय]] स्वा᳓हा [स्थू᳓णे अभि᳓रक्षतु] …।" in out_c
  assert "<div class=\"js_include\" url=\"/x.md\">\nधर्माय᳓\n</div>" in out_c


def test_reconcile_intra_compound_and_samasa_sutra_provenance():
  items = parse_padapatha_items(
    "- हिरण्य-कक्ष्या᳓न् → **हि᳓रण्य-कक्ष्यान्** (बहुव्रीहौ पा॰ ६.२.१; *KS* हि᳓रण्यकेशान्)\n"
    "- सु-धु᳓रान् (*KS*, *RV* सुधु᳓रम्; पा॰ ६.२.११९)\n"
    "- हिरण्य-अक्षा᳓न् (*KS*, *RV* हिरण्याक्षः᳓; पा॰ ५.४.११३, ६.१.१६३)\n"
    "- अयस्-शफा᳓न् → **अ᳓यस्-शफान्** (पा॰ ६.२.१; *KS* अ᳓यश्शफान्)\n"
    "- अ᳓श्वान् (*TS*, *RV*, *TB*)\n"
    "- अन᳓श्यतः → **अ᳓नश्यतः** (पा॰ ६.२.२; *KS* अ᳓नश्यतो)\n"
    "- दानम् → **दा᳓नम्** (*TS*, *RV*)\n"
    "- यमः᳓ (*TS*, *RV*, *AV*)\n"
    "- राजा → **रा᳓जा** (*TS*, *RV*, *TB*)\n"
    "- अभि → **अभि᳓** (*TS*, *RV*, *TB*, *TK*)\n"
    "- ति᳓ष्ठति → **तिष्ठति** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*, *RV*)"
  )
  vp = (
    "हिरण्य-कक्ष्यान्+++(=कुक्षीन्)+++ सु-धुरान्  \n"
    "हिरण्याक्षान् अयश्-शफान् ।  \n"
    "अ᳓श्वान् अनश्यतो दानय्ँ  \n"
    "यमो᳓ रा᳓जा᳓भि **तिष्ठति** ।  "
  )
  out, _ = reconcile_vp_suggestions(vp, items)
  assert out == (
    "[[हिरण्य-कक्ष्यान्|हि᳓रण्य-कक्ष्यान्]]+++(=कुक्षीन्)+++ [[सु-धुरान्|सु-धु᳓रान्]]  \n"
    "[[हिरण्याक्षान्|हिरण्याक्षा᳓न्]] [[अयश्-शफान्|अ᳓यश्-शफान्]] ।  \n"
    "अ᳓श्वान् [[अनश्यतो|अ᳓नश्यतो]] [[दानय्ँ|दा᳓नय्ँ]]  \n"
    "यमो᳓ [[रा᳓जा᳓भि|रा᳓जाभि᳓]] **तिष्ठति** ।  "
  )

  it_sapta = parse_padapatha_items(
    "- सप्त᳓-अर्चिषः (सप्त᳓ (*TS*, *RV*) + अर्चिः᳓ (*TB*), पा॰ ६.२.१; मूले स॒प्तार्चिष॑स्)"
  )
  assert reconcile_vp_suggestions("सप्ता᳓र्चि᳓षस्", it_sapta)[0] == "[[सप्ता᳓र्चि᳓षस्|सप्ता᳓र्चिषस्]]"

  # Compound item split across clause punctuation in VP must not emit a half-compound suggestion
  it_bp = parse_padapatha_items(
    "- ब्र᳓ह्म-पूता᳓ → **ब्र᳓ह्म-पूता** (पा॰ ६.२.२; *AV* ब्रह्म॑पूता)\n- पुनातु (पा॰ ८.१.२८)"
  )
  vp_bp = "ब्र᳓ह्म +++(च)+++, +++(सा)+++ पूता᳓ पुनातु"
  assert reconcile_vp_suggestions(vp_bp, it_bp)[0] == vp_bp


def test_reconcile_spaced_yan_and_panini_provenance():
  items = parse_padapatha_items(
    "- पाणि᳓ना (प्रातिपदिकम् पाणि᳓ (*MW*))\n"
    "- हि → **हि᳓** (*TS*, *RV*, *TB*, *TK*)\n"
    "- अव-म᳓र्शतु (हि च पा॰ ८.१.३४, तिङि चोदात्तवति पा॰ ८.१.७१)"
  )
  vp = "पाणि᳓ना ह्य् **अवम᳓र्शतु** ।"
  out1, _ = reconcile_vp_suggestions(vp, items)
  assert out1 == "पाणि᳓ना ह्य् **[[अवम᳓र्शतु|अ᳙वम᳓र्शतु]]** ।"
  # Idempotence on second pass
  out2, logs2 = reconcile_vp_suggestions(out1, items)
  assert out2 == out1
  assert logs2 == []

  # Pāṇinian kṛt/taddhita rules (पा॰ ३.१.३, ५.२.११५, ८.१.६६) count as solid provenance
  it_pan = parse_padapatha_items(
    "- दन्तिः → **दन्तिः᳓** (*MS*, पा॰ ५.२.११५, ३.१.३ — भास्करः)\n"
    "- स्तब्धः → **स्तब्धः᳓** (प्रत्ययः पा॰ ३.१.३)\n"
    "- श्रूयते → **श्रूय᳓ते** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, पा॰ ३.१.६७)"
  )
  assert reconcile_vp_suggestions("दन्तिः स्तब्धो श्रूयते", it_pan)[0] == (
    "[[दन्तिः|दन्तिः᳓]] [[स्तब्धो|स्तब्धो᳓]] [[श्रूयते|श्रूय᳓ते]]"
  )

  # Resyllabified consonant-final pada + compound merge + polysyllabic spaced yaṇ
  it_up = parse_padapatha_items(
    "- त᳓त् (*TS*)\n"
    "- उ᳓प-आसितव्य᳓म् → **उप-आसितव्य᳙म्** (पा॰ ३.१.९६, ६.१.१८५, ६.२.१३९)"
  )
  assert reconcile_vp_suggestions("त᳓दु᳓पासितव्य᳓म्", it_up)[0] == "[[त᳓दु᳓पासितव्य᳓म्|त᳓दुपासितव्य᳙म्]]"

  it_atm = parse_padapatha_items(
    "- वि᳓श्वस्य (*TS*)\n"
    "- आत्म-ई᳓श्वरम् → **आत्म-ईश्वर᳓म्** (पा॰ ६.१.२२३)"
  )
  assert reconcile_vp_suggestions("वि᳓श्वस्यात्मे᳓श्वरँ", it_atm)[0] == "[[वि᳓श्वस्यात्मे᳓श्वरँ|वि᳓श्वस्यात्मेश्वरँ᳓]]"

  it_jag = parse_padapatha_items(
    "- जगति → **ज᳓गति** (*RV*)\n- अस्मिन् (अनुदात्तम्, पा॰ २.४.३२)"
  )
  assert reconcile_vp_suggestions("जगत्य् अस्मिन्", it_jag)[0] == "[[जगत्य्|ज᳓गत्य्]] अस्मिन्"


def test_fill_vp_accents_and_filled_summary():
  assert format_filled_vp_summary("विश्वास-प्रस्तुतिः (स्वराः पूर्याः)", 5, 25) == "विश्वास-प्रस्तुतिः (5/25 व्यत्यस्त-स्वराः)"
  assert format_filled_vp_summary("विश्वास-प्रस्तुतिः - ऋक् (स्वराः पूर्याः)", 4, 11) == "विश्वास-प्रस्तुतिः - ऋक् (4/11 व्यत्यस्त-स्वराः)"
  assert format_filled_vp_summary("विश्वास-प्रस्तुतिः (स्वराः व्यत्यस्ताः 3/10)", 5, 10) == "विश्वास-प्रस्तुतिः (5/10 व्यत्यस्त-स्वराः)"
  assert format_filled_vp_summary("विश्वास-प्रस्तुतिः (स्वराः पूर्याः)", 0, 8) == "विश्वास-प्रस्तुतिः"
  assert format_filled_vp_summary("विश्वास-प्रस्तुतिः (स्वराः पूर्याः)", 0, 8, mula_has_accents=False) == "विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)"
  assert format_suggested_vp_summary("विश्वास-प्रस्तुतिः (स्वराः व्यत्यस्ताः 2/5)", 2, 5) == "विश्वास-प्रस्तुतिः (2/5 व्यत्यस्त-स्वराः)"

  items_30 = parse_padapatha_items(
    "- ब्राह्मणे᳙भ्यः → **ब्राह्मणे᳓भ्यः** (*AV*, *TS*)\n"
    "- हि → **हि᳓** (*TS*, *RV*)\n"
    "- अनु-ज्ञानम् → **अनु-ज्ञा᳓नम्** (पा॰ ३.३.११५, ६.१.१९३)\n"
    "- गच्छ᳓ → **ग᳓च्छ** (*TS*, *RV*; पा॰ ८.१.३४)"
  )
  filled, unmapped = fill_vp_accents_from_padapatha("ब्राह्मणेभ्यो ह्य् अनुज्ञानङ्\nगच्छ", items_30)
  assert unmapped == []
  assert filled == "ब्राह्मणे᳓भ्यो ह्य् अ᳙नुज्ञा᳓नङ्\nग᳓च्छ"

  items_pr = parse_padapatha_items(
    "- स्व᳓रः (*TS*)\n- प्र-उक्तः → **प्र᳓-उक्तः** (पा॰ ६.२.४९)\n- अङ्गु᳓ष्ठ᳓म् → **अङ्गुष्ठ᳓म्** (*TS*)\n- च (पा॰ ८.१.१८)"
  )
  filled_pr, unm_pr = fill_vp_accents_from_padapatha("स्वरः प्रोक्तो\nऽङ्गुष्ठञ्च", items_pr)
  assert unm_pr == []
  assert filled_pr == "स्व᳓रः प्रो᳓क्तो\nऽङ्गुष्ठ᳓ञ्च"

  # Direct-filled VP blocks migrate `(स्वराः व्यत्यस्ताः N/P)` -> `(N/P व्यत्यस्त-स्वराः)` and remain directly refillable
  md_direct = (
    "<details open><summary>विश्वास-प्रस्तुतिः (स्वराः व्यत्यस्ताः 2/2)</summary>\n\n"
    "वेद᳓मनू᳓च्य ।\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- वे᳓द᳓म् → **वे᳓दम्** (श्रुत्यर्थे वे᳓दम् आद्युदात्तम् श्रेयः, पा॰ ६.१.२०३, *AV*; दर्भमुष्टौ वेद᳓म् *TS*)\n"
    "- अ᳓नू᳓च्य᳓ → **अनू᳓च्य** (*TS*, *TB*, ल्यप् पा॰ ६.१.१९३, ६.२.१३९)\n</details>\n"
  )
  updated_direct, dlogs = reconcile_markdown_blocks(md_direct)
  assert "विश्वास-प्रस्तुतिः (2/2 व्यत्यस्त-स्वराः)" in updated_direct
  assert "वे᳓दमनू᳓च्य ।" in updated_direct
  assert "पद-पाठः (यान्त्रिकः - 2/2 व्यत्यस्त-स्वराः)" in updated_direct
  assert any("REFILLED_VP" in lg for lg in dlogs)
  assert reconcile_markdown_blocks(updated_direct, fixed_point=True) == (updated_direct, [])

  # Editing padapāṭha on a canonical `(2/2 व्यत्यस्त-स्वराः)` non-ŚB direct VP refills without inserting `[[|]]`
  edited_pp = updated_direct.replace("- वे᳓द᳓म् → **वे᳓दम्**", "- वे᳓दम् → **वेद᳓म्**")
  refilled_canon, cl_logs = reconcile_markdown_blocks(edited_pp, fixed_point=True)
  assert "वेद᳓मनू᳓च्य ।" in refilled_canon
  assert "[[" not in refilled_canon
  assert any("REFILLED_VP" in lg for lg in cl_logs)
  assert reconcile_and_sync_markdown_blocks(refilled_canon) == (refilled_canon, [])


def test_reconcile_and_sync_markdown_blocks_and_fixed_point(monkeypatch):
  # 1. Default reconcile_markdown_blocks leaves drifted ŚB VP summary untouched; sync_vp_summaries=True repairs it.
  sb_md = (
    "## ०१\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "[[तत्|त᳓त्]] स᳓विता ॥\n</details>\n\n"
    "<details><summary>मूलम् - Weber</summary>\n\nतत् स᳘विता॥\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 2/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- तत् → **त᳓त्** (*TS*-10)\n"
    "- स᳓विता (*TS*-10)\n</details>\n\n"
    "## ०२\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः (0/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "त᳓त् स᳓विता ॥\n</details>\n\n"
    "<details><summary>मूलम् - Weber</summary>\n\nत᳘त् स᳘विता॥\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- त᳓त् (*TS*-10)\n"
    "- स᳓विता (*TS*-10)\n</details>\n"
  )
  default_out, _ = reconcile_markdown_blocks(sb_md)
  assert "<summary>विश्वास-प्रस्तुतिः</summary>" in default_out
  assert "<summary>विश्वास-प्रस्तुतिः (0/2 व्यत्यस्त-स्वराः)</summary>" in default_out

  synced_out, sync_logs = reconcile_and_sync_markdown_blocks(sb_md)
  assert "<summary>विश्वास-प्रस्तुतिः (1/2 व्यत्यस्त-स्वराः)</summary>" in synced_out
  assert "<summary>पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)</summary>" in synced_out
  assert synced_out.count("<summary>विश्वास-प्रस्तुतिः</summary>") == 1
  assert "<summary>पद-पाठः (यान्त्रिकः)</summary>" in synced_out
  assert any("VP_HDR:" in lg for lg in sync_logs)
  assert reconcile_and_sync_markdown_blocks(synced_out) == (synced_out, [])

  # 2. Preserved no-bracket ŚB cluster with पा॰ ८.२.६ svarita and `(1/2 व्यत्यस्त-स्वराः)` must NOT be overwritten
  sb_826 = (
    "<details open><summary>विश्वास-प्रस्तुतिः (1/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "एवै᳙त᳓त् ॥\n</details>\n\n"
    "<details><summary>मूलम् - Weber</summary>\n\nएॗवैत᳘त्॥\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- एव → **एव᳓** (*RV*-10)\n"
    "- एत᳓त् (*TS*-10)\n</details>\n"
  )
  assert reconcile_and_sync_markdown_blocks(sb_826) == (sb_826, [])

  # 3. Non-ŚB plain cluster with non-solid arrow (no `[[` emitted) stays plain, avoiding false direct-fill on pass 2
  ts_unsolid = (
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "अ᳓ग्निम् ॥\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nअ॒ग्निम् ॥\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/1 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- अ᳓ग्निम् → **अग्निम्᳓** (*MW*)\n</details>\n"
  )
  assert reconcile_and_sync_markdown_blocks(ts_unsolid) == (ts_unsolid, [])

  # 4. fixed_point=True iterates until convergence across multiple passes and validates max_passes
  from doc_curation.sanskrit.accent import reconciler as rec_mod

  orig_once = rec_mod._reconcile_markdown_blocks_once
  calls = []

  def two_step_once(text, **kwargs):
    calls.append(text)
    if text == "step0":
      return "step1", ["PASS1"]
    if text == "step1":
      return "step2", ["PASS2"]
    return text, []

  monkeypatch.setattr(rec_mod, "_reconcile_markdown_blocks_once", two_step_once)
  assert reconcile_markdown_blocks("step0", fixed_point=False) == ("step1", ["PASS1"])
  assert len(calls) == 1
  calls.clear()
  assert reconcile_and_sync_markdown_blocks("step0") == ("step2", ["PASS1", "PASS2"])
  assert calls == ["step0", "step1", "step2"]

  monkeypatch.setattr(rec_mod, "_reconcile_markdown_blocks_once", orig_once)
  with pytest.raises(ValueError, match="max_passes"):
    reconcile_markdown_blocks("x", fixed_point=True, max_passes=0)


def test_is_solid_provenance_excludes_ta_ek_allows_sb():
  from doc_curation.sanskrit.accent.reconciler import is_solid_provenance

  assert is_solid_provenance("*ŚB*-12")
  assert is_solid_provenance("*TS*-5, *ŚB*-2")
  assert not is_solid_provenance("*TA*")
  assert not is_solid_provenance("*TA*-12")
  assert not is_solid_provenance("*EK*")
  assert not is_solid_provenance("*EK* मूल-पाठः")


def test_reconcile_mirror_coalesce_and_ayanta_merges():
  it_mir = parse_padapatha_items("- य᳓त् (*TS*)\n- अदः → **अदः᳓** (*TS*)\n- बहिर्धा᳓ (*TS*)\n- एव → **एव᳓** (*TS*)")
  assert fill_vp_accents_from_padapatha("यददो बहिर्धैव", it_mir) == ("य᳓ददो᳓ बहिर्धै᳓व᳓", [])

  it_ay = parse_padapatha_items("- अ᳓ग्रे (*TS*)\n- आ᳓ (*RV*)\n- अनक्ति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)")
  assert reconcile_vp_suggestions("अग्र आनक्ति", it_ay)[0] == "[[अग्र|अ᳓ग्र]] आनक्ति"

  it_au = parse_padapatha_items("- लोकौ → **लोकौ᳓** (*TS*)\n- अव → **अ᳓व** (*TS*)\n- अरुन्ध (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)")
  assert fill_vp_accents_from_padapatha("लोकाववारुन्ध", it_au) == ("लोका᳓व᳓वारुन्ध", [])

  it_ai_non_glide = parse_padapatha_items(
    "- अ᳓जीजनत (*TS*)\n- त᳓स्यै (*TS*)\n- वै᳓ (*TS*)\n- अह᳓म् (*TS*)\n- अस्मि (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)\n- इ᳓ति (*TS*)"
  )
  assert fill_vp_accents_from_padapatha("अजीजनत तस्यैवाहमस्मीति", it_ai_non_glide) == ("अ᳓जीजनत त᳓स्यैवा᳓ह᳓मस्मी᳓ति", [])


def test_qualified_padapatha_headers_and_shared_cluster_reconcile():
  from doc_curation.sanskrit.accent.reconciler import (
    PP_HEADER_RE,
    format_padapatha_summary,
    parse_padapatha_header,
  )
  from doc_curation.sanskrit.accent.validator import check_padapatha_header, validate_accented_markdown

  assert parse_padapatha_header("पद-पाठः (यान्त्रिकः)") == (None, 0, None)
  assert parse_padapatha_header("पद-पाठः (यान्त्रिकः - 1/21 व्यत्यस्त-स्वराः)") == (None, 1, 21)
  assert parse_padapatha_header("पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम्)") == ("काण्व-ब्राह्मणम्", 0, None)
  assert parse_padapatha_header("पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम् - 2/15 व्यत्यस्त-स्वराः)") == ("काण्व-ब्राह्मणम्", 2, 15)
  assert format_padapatha_summary(2, 15, shAkha_label="काण्व-ब्राह्मणम्") == "पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम् - 2/15 व्यत्यस्त-स्वराः)"
  assert PP_HEADER_RE.match("पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम् - 1/2 व्यत्यस्त-स्वराः)").groups() == ("1", "2")
  assert check_padapatha_header("पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम् - 1/2 व्यत्यस्त-स्वराः)", "- अ → **अ᳓** (*TS*)\n- ब᳓ (*RV*)") is None

  shared_static = (
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nत᳓त् स᳓विता ॥\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n"
    "<details><summary>मूलम् - श्रीधरादि</summary>\n\nत᳘त्स᳘विता॥\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- त᳓त् (*TS*-1)\n- स᳓विता (*TS*-1)\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम् - 1/2 व्यत्यस्त-स्वराः)</summary>\n\n- तत् → **त᳓त्** (*TB*-1)\n- स᳓विता (*TS*-1)\n</details>\n"
    "</details>\n"
  )
  out, logs = reconcile_markdown_blocks(shared_static, sync_vp_summaries=True)
  assert logs == []
  assert out == shared_static
  assert validate_accented_markdown(shared_static) == []


def test_bolding_combining_mark_splits_normalized_and_healed():
  from doc_curation.sanskrit.accent.reconciler import normalize_vp_bolding_splits
  from doc_curation.sanskrit.fixer import fix_intra_word_bolds

  assert fix_intra_word_bolds("**मा**᳓ ते गृहे᳓") == "**मा᳓** ते गृहे᳓"

  fixed_plain, logs_plain = normalize_vp_bolding_splits("**मा**᳓ ते")
  assert fixed_plain == "**मा᳓** ते"
  assert any(lg.startswith("FIX_BOLD_COMB_SPLIT:") for lg in logs_plain)

  fixed_sug, logs_sug = normalize_vp_bolding_splits("**[[मा|मा᳓]]**᳓ ते")
  assert fixed_sug == "**मा᳓** ते"
  assert any(lg.startswith("FIX_BOLD_SUG_SPLIT:") for lg in logs_sug)

  fixed_diff, _ = normalize_vp_bolding_splits("**[[मा|मा᳙]]**᳓ ते")
  assert fixed_diff == "**[[मा᳓|मा᳙]]** ते"

  items = parse_padapatha_items("- मा᳓ (*TS*-205)\n- ते (पा॰ ८.१.१८)\n")
  out1, _ = reconcile_vp_suggestions("**मा**᳓ ते", items)
  assert out1 == "**मा᳓** ते"
  out2, _ = reconcile_vp_suggestions("**[[मा|मा᳓]]**᳓ ते", items)
  assert out2 == "**मा᳓** ते"



