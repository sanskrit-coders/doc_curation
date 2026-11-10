from doc_curation.sanskrit.seeker import is_sanskrit_nagari


def test_is_sanskrit_nagari_requires_devanagari():
  assert not is_sanskrit_nagari("Tamil text only")


def test_is_sanskrit_nagari_counts_unique_hindi_markers():
  text = "धर्म है है और है"
  assert is_sanskrit_nagari(text, non_skt_threshold=2)
  assert not is_sanskrit_nagari(text, non_skt_threshold=1)


def test_is_sanskrit_nagari_counts_unique_tamil_tokens():
  text = "धर्म தமிழ் தமிழ் வணக்கம் வணக்கம்"
  assert is_sanskrit_nagari(text, non_skt_threshold=2)
  assert not is_sanskrit_nagari(text, non_skt_threshold=1)


def test_is_sanskrit_nagari_counts_unique_tamil_transliterations():
  text = "धर्म अऱु अऩ अऴ अऩ्ऱ अऱु"
  assert is_sanskrit_nagari(text, non_skt_threshold=4)
  assert not is_sanskrit_nagari(text, non_skt_threshold=3)
