from doc_curation.md.content_processor.commentary.lemma_aligner import (
  VerseSpec,
  align_commentary_sections,
  build_sarva_tikah_entry,
  inline_footnotes_for_block,
  parse_footnotes_markdown,
)


def test_split_half_verses_merged_groups_and_citations():
  verses = [
    VerseSpec.from_text(0, "2.114", "s1", "विभागं चेत् पिता कुर्याद् इच्छया विभजेत् सुतान् ।\nज्येष्ठं वा श्रेष्ठ-भागेन सर्वे वा स्युः समांशिनः ॥ २.११४ ॥"),
    VerseSpec.from_text(1, "2.117", "s1", "विभजेरन् सुताः पित्रोर् ऊर्ध्वं रिक्थम् ऋणं समम् ।\nमातुर् दुहितरः शेषम् ऋणात् ताभ्य ऋते ऽन्वयः ॥ २.११७ ॥"),
    VerseSpec.from_text(2, "2.118", "s1", "पितृ-द्रव्याविरोधेन यद् अन्यत् स्वयम् अर्जितम् ।\nमैत्रम् औद्वाहिकं चैव दायादानां न तद् भवेत् ॥ २.११८ ॥"),
    VerseSpec.from_text(3, "2.119", "s1", "क्रमाद् अभ्यागतं द्रव्यं हृतम् अप्य् उद्धरेत् तु यः ।\nदायादेभ्यो न तद् दद्याद् विद्यया लब्धम् एव च ॥ २.११९ ॥"),
  ]
  comm_md = """+++
title = "०८ दाय-विभाग-प्रकरणम्"
+++
**अथ दायविभागप्रकरणम्**

> प्रमाणम् मानुषं दैवम् इति भेदेन वर्णितम् ।
> अधुना वर्ण्यते दायविभागो योगमूर्तिना ॥

तत्र दायशब्देन यद् धनं स्वामिसंबन्धाद् अन्यस्य स्वं भवति तद् उच्यते ।

_इदानीं विभागस्य प्रकारम् आह ।_

> **विभागं चेत् पिता कुर्याद् इच्छया विभजेत् सुतान् । २.११४अब्**
> **ज्येष्ठं वा श्रेष्ठभागेन सर्वे वा स्युः समांशिनः ॥ २.११४च्द् ॥**

यदा पिता चिकीर्षति तदा विभजेत् ।

> **विभजेरन् सुताः पित्रोर् ऊर्ध्वं रिक्थम् ऋणं समम् । २.११७अब्**

समम् एव विभजेरन् ।

> ज्येष्ठ एव तु गृह्णीयात् पित्र्यं धनम् अशेषतः । (म्ध् ९.१०५)

_मातृधने ऽपवादम् आह ।_

> **मातुर् दुहितरः शेषम् ऋणात् २.११७च्**

मातुर् धनं दुहितरो विभजेरन् ।

_दुहित्रभावे कः गृह्णीयाद् इत्य् आह ।_

> **ताभ्य ऋते ऽन्वयः ॥ २.११७द्**

पुत्रादिर् गृह्णीयात् ।[^१]

_अविभाज्यम् आह ।_

> **पितृद्रव्याविरोधेन यद् अन्यत् स्वयम् अर्जितम् । २.११८अब्**
> **मैत्रम् औद्वाहिकं चैव दायादानां न तद् भवेत् ॥ २.११८च्द् ॥**
> **क्रमाद् अभ्यागतं द्रव्यं हृतम् अप्य् उद्धरेत् तु यः । २.११९अब्**
> **दायादेभ्यो न तद् दद्याद् विद्यया लब्धम् एव च ॥ २.११९च्द् ॥**

मातापित्रोर् द्रव्याविनाशेन यद् अर्जितम् ।
"""
  res = align_commentary_sections([("s1", comm_md)], verses)

  # Substantive intro stays in section avatārikā while immediate transition goes with 2.114
  assert "प्रमाणम् मानुषं" in res.per_section_avatarika["s1"]
  assert "इदानीं विभागस्य प्रकारम् आह" not in res.per_section_avatarika["s1"]
  assert "_इदानीं विभागस्य प्रकारम् आह ।_" in res.per_verse["2.114"][0]
  assert "यदा पिता चिकीर्षति" in res.per_verse["2.114"][0]

  # Split 2.117 parts (ab, c, d) concatenate sequentially, keeping Manu cite inside 2.117
  assert len(res.per_verse["2.117"]) == 3
  joined_117 = "\n\n".join(res.per_verse["2.117"])
  assert "म्ध् ९.१०५" in joined_117
  assert "मातुर् धनं दुहितरो" in joined_117
  assert "पुत्रादिर् गृह्णीयात्" in joined_117

  # Merged 2.118-2.119 blockquote owned by 2.118 without duplicating onto 2.119
  assert len(res.per_verse["2.118"]) == 1
  assert "मातापित्रोर् द्रव्याविनाशेन" in res.per_verse["2.118"][0]
  assert "2.119" not in res.per_verse
  assert res.unassigned_bold_groups == []


def test_local_transposition_reclaimed_and_bold_terms_inside_quote_ignored():
  verses = [
    VerseSpec.from_text(0, "3.13", "s1", "प्रविशेयुः समालभ्य कृत्वा ऽश्मनि पदं शनैः ॥ ३.१३ ॥"),
    VerseSpec.from_text(1, "3.14", "s1", "प्रवेशनादिकं कर्म प्रेत-संस्पर्शिनाम् अपि । इच्छतां तत्-क्षणाच् छुद्धिः परेषां स्नान-संयमान् ॥ ३.१४ ॥"),
    VerseSpec.from_text(2, "3.15", "s1", "आचार्य-पितृ-उपाध्यायान् निर्हृत्यापि व्रती व्रती । सङ्कटान्नं च नाश्नीयान् न च तैः सह संवसेत् ॥ ३.१५ ॥"),
    VerseSpec.from_text(3, "3.16", "s1", "क्रीत-लब्धाशना भूमौ स्वपेयुस् ते पृथक् क्षितौ । पिण्ड-यज्ञावृता देयं प्रेतायान्नं दिन-त्रयम् ॥ ३.१६ ॥"),
  ]
  # Commentary discusses 3.16 before 3.14-3.15 and quotes a partially-bolded Smṛti stanza
  comm_md = """**अथाशौचप्रकरणम्**

_तत्र प्रथमम् आह ।_

> **प्रविशेयुः समालभ्य कृत्वाश्मनि पदं शनैः ॥ ३.१३ ॥**

इति शनैः प्रविशेयुः ।

> ब्राह्मणस्य **रुजः कृत्या**
> **घ्रातिर्** अघ्रेय-मद्ययोः ।

> **

> **पितृयज्ञावृता देयं प्रेतायान्नं दिनत्रयम् ॥ ३.१४ ॥**

प्रेतायान्नं देयम् ।

> **प्रवेशनाधिकं कर्म प्रेतसंस्पर्शनाम् अपि ।**
> **इच्छतां**
> **तत्क्षणच् छुद्धिः परेषां स्नानसंयमात् ॥ ३.१६ ॥**

इच्छतां शुद्धिः स्यात् ।

> **आचार्योपाध्यायपितॄन् निर्हृत्यापि व्रती व्रती ।**
> **स कटान्नं च नाश्नीयान् न च तैः सह संवसेत् ॥ ३.१७ ॥**

संकटान्नं नाश्नीयात् ।
> **
"""
  res = align_commentary_sections([("s1", comm_md)], verses)
  assert "3.13" in res.per_verse
  assert "3.14" in res.per_verse
  assert "3.15" in res.per_verse
  assert "3.16" in res.per_verse
  assert "घ्रातिर्" in res.per_verse["3.13"][0]
  assert not res.per_verse["3.13"][0].rstrip().endswith("> **")
  assert "प्रेतायान्नं देयम्" in res.per_verse["3.16"][0]
  assert "इच्छतां शुद्धिः स्यात्" in res.per_verse["3.14"][0]
  assert "संकटान्नं नाश्नीयात्" in res.per_verse["3.15"][0]
  # Trailing stray `> **` artifact is removed cleanly
  assert not res.per_verse["3.15"][0].rstrip().endswith("> **")
  # Single short italic lead-in stays in verse 0 rather than creating an extra avatārikā block
  assert "s1" not in res.per_section_avatarika
  assert "_तत्र प्रथमम् आह ।_" in res.per_verse["3.13"][0]


def test_cross_section_and_page_markers_and_footnotes():
  verses = [
    VerseSpec.from_text(0, "1.160", "s6", "पर-शय्यासनोद्यान-गृह-यानानि वर्जयेत् ।\nअ-दत्तान्य् अग्नि-हीनस्य न+अन्नम् अद्याद् अन-आपदि ॥ १.१६० ॥"),
    VerseSpec.from_text(1, "1.161", "s6", "कदर्य-बद्ध-चौराणां क्लीब-रङ्गावतारिणाम् ॥ १.१६१ ॥"),
    VerseSpec.from_text(2, "1.167", "s7", "अनर्चितं वृथा-मांसं केश-कीट-समन्वितम् ॥ १.१६७ ॥"),
  ]
  s6_md = """_उक्तम् अन्यद् वर्जनीयम् ।_

> **परशय्यासनोद्यानगृहयानानि वर्जयेत् ।**

अदत्तानि वर्जयेत् ।
"""
  s7_md = """**अथ भक्ष्याभक्ष्यप्रकरणम्**

_तत्राभोज्यान्य् आह ।_

> **अग्निहीनस्य नान्नम् अद्याद् अनापदि ॥ १.१६० ॥**

अग्निहीनस्यानं[^१] न भुञ्जीत ।

**[२३८]**\t**कदर्यबद्धचौराणां क्लीबरङ्गावतारिणाम् ।**

कदर्यस्य न भुञ्जीत ।

> **अनर्चितं वृथामांसं केशकीटसमन्वितम् ॥ १.१६७ ॥**

अनर्चितं वर्जयेत् ।
"""
  res = align_commentary_sections([("s6", s6_md), ("s7", s7_md)], verses)
  assert len(res.per_verse["1.160"]) == 2
  assert "परशय्यासनोद्यान" in res.per_verse["1.160"][0]
  assert "अग्निहीनस्य नान्नम्" in res.per_verse["1.160"][1]
  assert "कदर्यस्य न भुञ्जीत" in res.per_verse["1.161"][0]
  assert "अनर्चितं वर्जयेत्" in res.per_verse["1.167"][0]

  fn_md = """+++
title = "Footnotes"
+++

[^1]:
     NSP reads agni.

[^2]-
     Note using hyphen format.
     Continuation line.
"""
  parsed = parse_footnotes_markdown(fn_md)
  assert parsed["1"] == "NSP reads agni."
  assert parsed["१"] == "NSP reads agni."
  assert "Continuation line." in parsed["२"]

  inlined = inline_footnotes_for_block(res.per_verse["1.160"][1], parsed)
  assert "अग्निहीनस्यानं[१] न भुञ्जीत" in inlined
  assert "[१]: NSP reads agni." in inlined
  assert "[^" not in inlined

  tikah = build_sarva_tikah_entry(
    "मन्त्रः ॥ १.१६० ॥",
    [("विज्ञानेश्वरः", ""), ("अपरार्कः", inlined)],
  )
  assert "<summary>मूलम्</summary>" in tikah
  assert "<summary>अपरार्कः</summary>" in tikah
  assert "विज्ञानेश्वरः" not in tikah


def test_synonym_gap_fill_title_punctuation_and_colophon_preserved():
  verses = [
    VerseSpec.from_text(0, "1.305", "s12", "दद्याद् ग्रह-क्रमाद् एवं द्विजेभ्यो भोजनं बुधः ॥ १.३०५ ॥"),
    VerseSpec.from_text(1, "1.306", "s12", "धेनुः शङ्खस् तथा ऽनड्वान् हेम वासो हयः क्रमात् ।\nकृष्णा गौर् आयसं छाग एता वै दक्षिणाः स्मृताः ॥ १.३०६ ॥"),
    VerseSpec.from_text(2, "1.307", "s12", "यश् च यस्य यदा दुःस्थः स तं यत्नेन पूजयेत् ॥ १.३०७ ॥"),
  ]
  comm_md = """**अथ ग्रहशान्तिप्रकरणम्** ।

_ग्रहशान्तिम् आह ।_

> **दद्याद् ग्रहक्रमाद् एवं द्विजेभ्यो भोजनं बुधः ॥ १.३०० ॥**

भोजनं दद्यात् ।

> **धेनुं शङ्खम् अनड्वाहं काञ्चनं वसनं हयम् ।**
> **कृष्णां गाम् आयसाम् छागं प्रदद्याद् दैक्षिणाः क्रमात् ॥ १.३०१ ॥**

दक्षिणा दद्यात् ।

> **यश् च यस्य यदा दुःस्थः स तं यत्नेन पूजयेत् ॥ १.३०२ ॥**

स पूजयेत् ।

**इति ग्रहशान्तिप्रकरणम्**
> **
"""
  res = align_commentary_sections([("s12", comm_md)], verses)
  assert "s12" not in res.per_section_avatarika
  assert "_ग्रहशान्तिम् आह ।_" in res.per_verse["1.305"][0]
  assert "दक्षिणा दद्यात्" in res.per_verse["1.306"][0]
  assert "**इति ग्रहशान्तिप्रकरणम्**" in res.per_verse["1.307"][0]
  assert not res.per_verse["1.307"][0].rstrip().endswith("> **")


def test_parse_paired_details_sections_recovers_malformed_blocks():
  from doc_curation.md.content_processor.commentary.lemma_aligner import (
    align_entry_stream_to_verses,
    parse_paired_details_sections,
  )

  md = """+++
title = "०४"
+++

<details><summary>मूलम्</summary>

**राजतो धनम् अन्विच्छेत् संसीदन् स्नतकः क्षुधा ।  
याज्यान्तेवासिनोर् वापि न त्व् अन्यत इति स्थितिः ॥ ४.३३ ॥**
</details>
**राजत** इति । स्नातकः क्षुधावसादं गच्छन् ॥ ४.३३ ॥

<details><summary>मूलम्</summary>

**कुर्याद् घृतपशुं सङ्गे कुर्यात् पिष्टपशुं तथा ।  
न त्व् एव तु वृथा हन्तुं पशुम् इच्छेत् कदाचन ॥ ५.३७ ॥**  
कुर्याद् इति । वृथा पशुं न हन्यात्
</details>॥ ५.३७ ॥

<details><summary>मूलम्</summary>

**प्रतिरोद्धा गुरोश् चैव त्यक्ताग्निर् वार्धुषिस् तथा ॥ ३.१५३ ॥**
</details>
नो चोम्मेन्तर्य्
"""
  entries = parse_paired_details_sections(md, commentary_prefix="गोविन्दराजः")
  assert len(entries) == 3
  assert entries[0]["verse_hint"] == 33
  assert "**राजत** इति" in entries[0]["body"]
  assert entries[1]["verse_hint"] == 37
  assert "कुर्याद् इति" in entries[1]["body"]
  assert entries[1]["body"].endswith("॥ ५.३७ ॥")
  assert entries[2]["body"] == ""

  verses = [
    VerseSpec.from_text(0, "4.33", "04", "राजतो धनम् अन्विच्छेत् संसीदन् स्नातकः क्षुधा । याज्यान्तेवासिनोर् वापि न त्व् अन्यत इति स्थितिः ॥ ४.३३ ॥"),
    VerseSpec.from_text(1, "4.34", "04", "न सीदेत् स्नातको विप्रः क्षुधा शक्तः कथञ्चन ॥ ४.३४ ॥"),
    VerseSpec.from_text(2, "5.37", "05", "कुर्याद् घृतपशुं सङ्गे कुर्यात् पिष्टपशुं तथा । न त्व् एव तु वृथा हन्तुं पशुम् इच्छेत् कदाचन ॥ ५.३७ ॥"),
  ]
  aligned = align_entry_stream_to_verses(entries[:2], verses)
  assert list(aligned.keys()) == ["4.33", "5.37"]


def test_extract_bold_shloka_sections_and_split_italic_avatarika():
  from doc_curation.md.content_processor.commentary.lemma_aligner import (
    extract_bold_shloka_sections,
    split_leading_and_trailing_italic_avatarika,
  )

  kull_md = """+++
title = "०१"
+++
**प्रथमोऽध्यायः ।**

  प्रायिकं धर्मसामान्यलक्षणं वदति—

**मनुमेकाग्रमासीनमभिगम्य महर्षयः ।**
**प्रतिपूज्य यथान्यायमिदं वचनमब्रुवन् ॥ १ ॥**

  'अभिगम्य' इति कर्म(१)[^1] ॥१॥

[^1]: " 'कर्मत्वात्' क० ।"

  किमब्रुवन्नित्यपेक्षायामाह—

**भगवन् सर्ववर्णानां यथावदनुपूर्वशः ।**
**अन्तरप्रभवाणां च धर्मान्नो वक्तुमर्हसि ॥२॥**

  अप्रभवाणां (१[^2] मिश्रितवर्णानाम् ")) धर्मान्वक्तुमर्हसि ॥२॥
"""
  opening, entries = extract_bold_shloka_sections(kull_md)
  assert "धर्मसामान्यलक्षणं वदति—" in opening
  assert len(entries) == 2
  assert entries[0]["verse_hint"] == 1
  assert "कर्म(१)[1]" in entries[0]["body"]
  assert "[1]: \" 'कर्मत्वात्' क० ।\"" in entries[0]["body"]
  assert "[^" not in entries[0]["body"]
  assert entries[1]["verse_hint"] == 2
  assert entries[1]["avatarika"] == "किमब्रुवन्नित्यपेक्षायामाह—"
  assert "[2]: मिश्रितवर्णानाम्" in entries[1]["body"]

  medh_block = """_इयं लीडिङ्ग् अवतारिका ।_

**मनुम्** अभिगम्य ॥ १.१ ॥

[^१]:
     Old variant.

_अभिगम्य प्रतिपूज्य किम् अब्रुवन्न् इत्य् अपेक्षायां द्वितीयः श्लोकः ।_[^४]
"""
  lead, core, trail = split_leading_and_trailing_italic_avatarika(
    medh_block, extra_footnotes={"४": "J: extra intro note."}
  )
  assert lead == "_इयं लीडिङ्ग् अवतारिका ।_"
  assert "**मनुम्** अभिगम्य ॥ १.१ ॥" in core
  assert "[^१]:" in core
  assert "[^४]" not in core
  assert "_अभिगम्य प्रतिपूज्य" in trail
  assert "[४]: J: extra intro note." in trail
  assert "[^" not in trail

  # Verify multi-verse bracketed kṣepaka does not split commentary and unbolded variant in मूलम् does not swallow commentary
  from doc_curation.md.content_processor.commentary.lemma_aligner import parse_paired_details_sections
  ksep_md = """**मुख्यश्लोकः प्रथमः ॥ ९८ ॥**

**\\[ अनर्हते यद्ददाति ॥३॥**

**काले न्यायागतं पात्रे ॥४॥ \\]**

** ** स्वधाशब्दोच्चारणानन्तरं शेषमन्नं निवेदयेत् ॥२३॥

  मुख्यश्लोकव्याख्या ॥९८॥
"""
  _, k_entries = extract_bold_shloka_sections(ksep_md)
  assert len(k_entries) == 1
  assert "मुख्यश्लोकव्याख्या" in k_entries[0]["body"]
  assert "काले न्यायागतं" in k_entries[0]["body"]
  assert "स्वधाशब्दोच्चारणानन्तरं" in k_entries[0]["body"]

  gov_var = """<details><summary>मूलम्</summary>

**यद् यद् ददाति विधिवत् ॥ ३.२७५ ॥**
यद् यद् ददाति पाठान्तरम् ।
</details>
<details><summary>गोविन्दराजः - ३.२७५</summary>

**यद् यद्** इति व्याख्या ॥
</details>
"""
  g_entries = parse_paired_details_sections(gov_var, commentary_prefix="गोविन्दराजः")
  assert len(g_entries) == 1
  assert "**यद् यद्** इति व्याख्या" in g_entries[0]["body"]

