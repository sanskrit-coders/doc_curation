from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import bhashya_aligner as ba


def test_clean_commentary_boilerplate_and_shell_rejection():
  raw = "तत्र प्रथमा।\n\nम० ‘देवो वः’ (का० ४।२।९)। हे गावः॥ १०॥\n[1]षष्ठी ।\nइति माध्यन्दिनीयायां वाजसनेविसंहितायां प्रथमोऽध्यायः॥ १॥"
  cleaned = ba.clean_commentary_boilerplate(raw)
  assert cleaned.startswith("‘देवो वः’")
  assert "षष्ठी" not in cleaned
  assert "तत्र प्रथमा" not in cleaned
  assert "वाजसनेविसंहितायां" not in cleaned

  with_colophon = "म० हे अग्ने॥ १५॥\nश्रीमन्महीधरकृते वेददीपे मनोहरे।"
  cleaned_v = ba.clean_commentary_boilerplate(with_colophon)
  assert "श्रीमन्महीधरकृते वेददीपे मनोहरे।" in cleaned_v

  assert ba.clean_commentary_boilerplate("॥ ३२॥ ३३॥ ३४॥") == ""


def test_cross_author_leak_and_24_24_swap():
  u_raw = {
    (24, 24): "न्पारुष्णसंज्ञान्गृहपतयोऽग्नये॥ २४॥\nम त्रयाणां लबानां मध्ये द्वौ सोमाय॥ २४॥",
    (19, 48): "शेषं यजमानो भक्षयति॥ ४८॥ मा० ‘शेषं यजमानः’ (का० १९।५।१२)। सुहुतमस्तु॥ ४८॥",
  }
  m_raw = {
    (24, 24): "श्वित्रः श्वेतः पशुरादित्यानाम्॥ ३९॥\n\nचत्वारिंशी।\nइति माध्यन्दिनीयायां वाजसनेयसंहितायां चतुर्विंशोऽध्यायः॥ २४॥",
    (19, 22): "आमिक्षा शिष्टं वाजिनम्॥ २१॥\nद्वाविंशी।\nउ। धानानां रूपम्॥ २२॥",
  }
  u_out, m_out = ba._split_cross_author_leaks(u_raw, m_raw)
  assert "त्रयाणां" not in u_out[(24, 24)]
  assert "त्रयाणां" in m_out[(24, 24)]
  assert "श्वित्रः" in m_out[(24, 39)]
  assert "शेषं यजमानो" in u_out[(19, 48)] and "मा०" not in u_out[(19, 48)]
  assert "का० १९" in m_out[(19, 48)]
  assert "धानानां" in u_out[(19, 22)]
  assert "आमिक्षा" in m_out[(19, 21)]


def test_role_classification_and_two_pass_split_alignment():
  u_text = "अपः प्रणयति। कस्त्वा युनक्ति। यज्ञस्यारम्भकर्मणि॥ ६॥"
  m_text = "‘अपः प्रणयति कस्त्वा युनक्तीति’ (का० १।३।१)। देवो युनक्ति॥ ६॥"
  plan = ba.plan_kandika_alignment(u_text, m_text, ["कस्त्वा युनक्ति"])
  assert len(plan) == 1
  assert plan[0]["uvata"]["viniyoga"] == "अपः प्रणयति।"
  assert "कस्त्वा युनक्ति" in plan[0]["uvata"]["tika"]
  assert "का॰ १।३।१" in plan[0]["mahidhara"]["viniyoga"]
  assert "देवो युनक्ति" in plan[0]["mahidhara"]["tika"]

  # Negative guard: `विनियोगो नास्ति` stays out of viniyoga, `इदानीं ... निरूप्यते` stays in avatarika
  plan_neg = ba.plan_kandika_alignment(
    "",
    "एकोनचत्वारिंशताध्यायैः कर्मकाण्डं निरूपितम्। इदानीं कर्माचरणशुद्धान्तःकरणं प्रति ज्ञानकाण्डमेकेनाध्यायेन निरूप्यते। ईशावास्यमित्यादिमन्त्राणां कर्मसु विनियोगो नास्ति। ईशा परमात्मना वास्यम्॥ १॥",
    ["ईशा वास्यम्"],
  )
  assert "viniyoga" not in plan_neg[0]["mahidhara"]
  assert "कर्मकाण्डं" in plan_neg[0]["mahidhara"]["avatarika"]
  assert "निरूप्यते" in plan_neg[0]["mahidhara"]["avatarika"]
  assert "विनियोगो नास्ति" in plan_neg[0]["mahidhara"]["tika"]

  # Guard against `ऽवतिष्ठते` false-positive viniyoga and Taittiriya arthavada citations
  plan_tika = ba.plan_kandika_alignment(
    "साच क्रियमाणा तस्मिन्नेवाभिधेयेऽवतिष्ठते मगधाधिपतिवत्।",
    "तदुक्तं तित्तिरिणा ऽऋक्सामे वै देवेभ्यः’ (६। १। ३) इति।",
    ["इषे त्वा"],
  )
  assert "viniyoga" not in plan_tika[0]["uvata"]
  assert "viniyoga" not in plan_tika[0]["mahidhara"]

  # Two-pass split alignment (e.g. M 1.1 with अथ व्याकरणप्रक्रिया returning to sub-mantra 0)
  m_two_pass = (
    "प्रणम्य लक्ष्मीं नृहरिं गणेशम्।\n\n"
    "अथ मन्त्रार्थः क्रियापदाध्याहारेण। हे शाखे, इषे त्वा छिनद्मि।\n"
    "‘मातृभिर्वत्सान्संसृज्य वायवः स्थ’ (४।२।७) इति। हे वत्साः, वायवः स्थ।\n"
    "अथ व्याकरणप्रक्रिया। इषे। इषेरिच्छार्थस्य कर्मणि क्विप्।"
  )
  plan2 = ba.plan_kandika_alignment(
    "शाखामुपगूहति। यजमानस्य पशून्पाहि।",
    m_two_pass,
    ["इषे त्वा", "वायवः स्थ", "यजमानस्य पशून्पाहि"],
    kandika_key="1.1",
  )
  assert "प्रणम्य" in plan2[0]["mahidhara"]["avatarika"]
  assert "व्याकरणप्रक्रिया" in plan2[0]["mahidhara"]["tika"]
  assert "वायवः" in plan2[1]["mahidhara"]["viniyoga"]
  assert "वायवः" in plan2[1]["mahidhara"]["tika"]
  assert "शाखामुपगूहति" in plan2[2]["uvata"]["viniyoga"]


def test_render_js_include_and_inline_split_idempotent(tmp_path):
  static_dir = tmp_path / "sarvASh_TIkAH" / "04"
  static_dir.mkdir(parents=True)
  static_file = static_dir / "08_vishvo.md"
  static_file.write_text(
    '+++\ntitle = "०८"\n+++\n'
    "<details><summary>Griffith</summary>\n\nG\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nM\n</details>\n\n"
    "<details><summary>पदपाठः - दयानन्दादि</summary>\n\nP\n</details>\n"
    "<details><summary>महीधरः</summary>\n\nOLD\n</details>\n"
    "<details><summary>अधिमन्त्रम् (VC)</summary>\n\nVC\n</details>\n"
  )
  host_sec = (
    "## ०८ विश्वो देवस्य\n"
    '<div class="js_include" newlevelforh1="3" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH/vishvAsa-prastutiH/04/08_vishvo.md">\n'
    '<details open><summary><h3>विश्वास-प्रस्तुतिः ...{Loading}...</h3></summary>\nVP\n</details>\n</div>\n'
    '<div class="js_include collapsed" newlevelforh1="3" title="सर्वाष् टीकाः" unfilled url="/vedAH/sarvASh_TIkAH/04/08_vishvo.md">\n'
    '<details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>\n'
    + static_file.read_text().split("+++\n", 2)[2]
    + "</details>\n</div>\n"
  )
  plan = [
    {
      "uvata": {"viniyoga": "उवटविनियोगः।", "tika": "उवटटीका।"},
      "mahidhara": {"avatarika": "अथ षष्ठः।", "tika": "महीधरटीका।"},
    }
  ]
  new_host, st_upd = ba.render_host_section(host_sec, plan, static_tikah_dir=static_dir.parent)
  assert st_upd is not None
  new_static_path, new_static_text = st_upd
  assert new_static_path == static_file
  # Static must contain tikas right after padapatha, NEVER viniyoga/avatarika or raw महीधरः
  assert "<summary>उवट-टीका</summary>" in new_static_text
  assert "<summary>महीधर-टीका</summary>" in new_static_text
  assert "विनियोगः" not in new_static_text
  assert "अवतारिका" not in new_static_text
  assert "<summary>महीधरः</summary>" not in new_static_text
  # Host puts avatarika & viniyoga inside <summary>सर्वा अवतारिकाः</summary> ABOVE vishvAsa-prastutiH js_include
  vp_pos = new_host.index("vishvAsa-prastutiH/04/08_vishvo.md")
  assert "<summary>सर्वा अवतारिकाः</summary>" in new_host
  assert new_host.index("<summary>सर्वा अवतारिकाः</summary>") < new_host.index("महीधरः - अवतारिका")
  assert new_host.index("महीधरः - अवतारिका") < new_host.index("उवटः - विनियोगः") < vp_pos
  # Re-rendering is idempotent (depth-safe stripping of nested सर्वा अवतारिकाः)
  new_host2, _ = ba.render_host_section(new_host, plan, static_tikah_dir=static_dir.parent)
  assert new_host2 == new_host
  assert new_host.count("<summary>सर्वा अवतारिकाः</summary>") == 1

  # Inline split-mantra section removes trailing raw महीधरः, wraps per-submantra upper blocks, omits empty wrappers
  inline_sec = (
    "## ०१\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nV1\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n"
    "<details><summary>Griffith</summary>\n\nG1.\n</details>\n"
    "<details><summary>मूलम्</summary>\n\nM1\n</details>\n"
    "<details><summary>पदपाठः - दयानन्दादि</summary>\n\nP1\n</details>\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nV2\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n"
    "<details><summary>Griffith</summary>\n\nG2.\n</details>\n"
    "<details><summary>मूलम्</summary>\n\nM2\n</details>\n"
    "<details><summary>पदपाठः - दयानन्दादि</summary>\n\nP2\n</details>\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nV3\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n"
    "<details><summary>Griffith</summary>\n\nG3.\n</details>\n"
    "<details><summary>मूलम्</summary>\n\nM3\n</details>\n"
    "<details><summary>पदपाठः - दयानन्दादि</summary>\n\nP3\n</details>\n"
    "<details><summary>महीधरः</summary>\n\nRAW\n</details>\n"
    "<details><summary>अधिमन्त्रम् (VC)</summary>\n\nVC\n</details>\n</details>\n"
  )
  plan_inline = [
    {"uvata": {"viniyoga": "उवि१", "tika": "उटी१"}, "mahidhara": {"tika": "मटी१"}},
    {"uvata": {"tika": "उटी२"}, "mahidhara": {"viniyoga": "मवि२", "tika": "मटी२"}},
    {"uvata": {"tika": "उटी३"}, "mahidhara": {}},
  ]
  rendered_in, _ = ba.render_host_section(inline_sec, plan_inline)
  assert "<summary>महीधरः</summary>" not in rendered_in
  assert rendered_in.count("<summary>सर्वा अवतारिकाः</summary>") == 2
  assert rendered_in.index("उवटः - विनियोगः") < rendered_in.index("V1")
  assert rendered_in.index("उवट-टीका") > rendered_in.index("P1")
  assert rendered_in.index("महीधरः - विनियोगः") < rendered_in.index("V2")
  assert rendered_in.index("मटी२") > rendered_in.index("P2")
  assert rendered_in.count("<details") == rendered_in.count("</details>")
  assert ba.render_host_section(rendered_in, plan_inline)[0] == rendered_in

  from doc_curation.sanskrit.accent import samhita_splitter
  assert samhita_splitter.validate_samhita_section(rendered_in) == []


def test_wikisource_parser_and_combined_reposition(tmp_path):
  ws_dir = tmp_path / "ws"
  ws_dir.mkdir()
  (ws_dir / "25.wt").write_text(
    "अग्ने त्वं नः ॥\n"
    "{{भाष्यम्(उवट-महीधर)|\n"
    "सप्तचत्वारिंशी।\n"
    "अग्ने॒ त्वं न॑: ॥ ४७ ॥\n"
    "उ० अग्ने त्वं न इति व्याख्यातम् ॥ ४७ ॥\n"
    "इति उवटकृतौ मन्त्रभाष्ये पञ्चविंशोऽध्यायः ॥ २५ ॥\n"
    "म० तिस्रो द्विपदा व्याख्याताः ॥ ४७ ॥\n"
    "}}\n"
  )
  u_map, m_map = ba.parse_wikisource_bhashya_dir(ws_dir, {25: 47})
  assert "व्याख्यातम्" in u_map[(25, 47)]
  assert "तिस्रो द्विपदा" in m_map[(25, 47)]

  repositioned, notes = ba._reposition_combined_entries(
    {
      (16, 66): "द्वे कण्डिके उक्तार्थे ॥ ६५ ॥ ६६ ॥ ।",
      (14, 31): "सृष्टीः ॥ २८ ॥ ॥ २९ ॥ ३० ॥ ३१ ॥",
      (9, 34): "॥ ३२ ॥ ३३ ॥ ३४ ॥ वाजपेयः समाप्तः ॥",
    },
    {9: 40, 14: 31, 16: 66},
  )
  assert (16, 65) in repositioned
  assert "६५-कण्डिकया" in notes[(16, 66)]
  assert (14, 28) in repositioned
  assert all("२८-कण्डिकया" in notes[(14, x)] for x in (29, 30, 31))
  assert (9, 34) in repositioned
  assert "३४-कण्डिकया" in notes[(9, 32)] and "३४-कण्डिकया" in notes[(9, 33)]

  prose_repo, prose_notes = ba._reposition_combined_entries(
    {
      (10, 11): "एवं दक्षिणामारोहेति चतस्रः कण्डिका व्याख्येयाः॥ ११॥",
      (12, 40): "पुनरूर्जा। द्वे व्याख्याते॥ ४०॥",
      (14, 9): "चतुर्भिर्मन्त्रैः ... पृष्ठवाड् वय इत्यादिदश निगदव्याख्याताः॥ ९॥",
      (14, 24): "स्पृतं दश इष्टका उपदधाति दशभिर्मन्त्रैः ...॥ २४॥",
    },
    {10: 34, 12: 117, 14: 31},
    apply_prose_group_notes=True,
  )
  assert (10, 12) in prose_notes and "११-कण्डिकया" in prose_notes[(10, 12)]
  assert (12, 41) in prose_notes and "४०-कण्डिकया" in prose_notes[(12, 41)]
  assert (14, 10) in prose_notes and "९-कण्डिकया" in prose_notes[(14, 10)]
  assert (14, 25) in prose_notes and "२४-कण्डिकया" in prose_notes[(14, 25)]


def test_aligner_uses_soft_breaks_and_cleans_uvata_and_um():
  from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa import prose_clean
  from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup import tika_merger

  plan = ba.plan_kandika_alignment(
    "इषे त्वा। अन्नार्थं वचनम्। तृतीयं वाक्यम्॥ १॥",
    "",
    ["इषे त्वा"],
  )
  u_tika = plan[0]["uvata"]["tika"]
  assert "\n\n" not in u_tika
  assert "  \n" in u_tika

  uv_dirty = "आज्यम्ाज्यशब्देन यज्ञो लक्ष्यते (पा० ६.१। १०) ।\n\nधयतेर्णिजन्त(३)स्यासुनि रूपम् ।\n\nकर्मा (१)कर्त्री:"
  uv_clean = prose_clean.clean_prose_block(uv_dirty, mode="uvata")
  assert "आज्यम् । आज्यशब्देन" in uv_clean
  assert "(पा॰ ६.१। १०)" in uv_clean
  assert "(३)" not in uv_clean and "(१)" not in uv_clean
  assert "\n\n" not in uv_clean and "  \n" in uv_clean
  assert "कर्त्रीः" in uv_clean

  merged = tika_merger.merge_author_bodies(["प्रथमः भागः।", "द्वितीयः भागः।"])
  assert merged == "प्रथमः भागः।  \nद्वितीयः भागः।"

  um_dirty = (
    '+++\ntitle = "०१"\n+++\n\n'
    "उ० दृष्टमित्यर्थः (का० १।२।३)। तथा 'दध्यङ्\n\n"
    "१ ऋषीन्वच्मीह. २ ब्रह्मपङ्क्तिः\n\n"
    "ह वा आथर्वण' इति।\n\n"
    ".\n\n"
    "म० अन्\n\n"
    "* * *\n\n"
    "१ पादटिप्पणी।\n\n"
    "* * *\n\n"
    "तरात्मा भवति।\n\n"
    "मन्त्राणामकारादिवर्णक्रमकोशः । १ ९ ४०"
  )
  um_cleaned = ba.clean_uvatamahidharau_text(um_dirty)
  assert "उ॰ दृष्टमित्यर्थः (का॰ १।२।३)।" in um_cleaned
  assert "तथा 'दध्यङ् ह वा आथर्वण' इति।" in um_cleaned
  assert "> [टिप्पणी] १ ऋषीन्वच्मीह. २ ब्रह्मपङ्क्तिः" in um_cleaned
  assert "\n\n.\n\n" not in um_cleaned
  assert "मन्त्राणामकारादिवर्णक्रमकोशः" not in um_cleaned
  assert "म॰ अन् तरात्मा भवति।" in um_cleaned
  assert "> [टिप्पणी] १ पादटिप्पणी।" in um_cleaned
