
iitk_title_to_folder_path = {
  "विश्वास-प्रस्तुतिः": "saMskRtam/vishvAsa-prastutiH",
  "मूल श्लोकः": "saMskRtam/mUlam",

  "रामानुज-सम्प्रदायः": "____________",
  "Ramanuja": "saMskRtam/rAmAnujaH/mUlam",
  "Vedantadeshikacharya": "saMskRtam/rAmAnujaH/venkaTanAthaH",
  "Sanskrit Commentary By Swami Adidevananda": "saMskRtam/rAmAnujaH/english/AdidevAnandaH",

  "अभिनवगुप्त-सम्प्रदायः": "____________",
  "Sanskrit Commentary By Sri Abhinavgupta": "saMskRtam/abhinava-guptaH/mUlam",
  "English Translation of Abhinavgupta's": "saMskRtam/abhinava-guptaH/english/shankaranArAyaNaH",

  "माध्व-सम्प्रदायः": "____________",
  "Madhavacharya": "saMskRtam/madhvaH/mUlam",
  "Jayatritha": "saMskRtam/madhvaH/jayatIrthaH",

  "शाङ्कर-सम्प्रदायः": "____________",
  "Sanskrit Commentary By Sri Shankaracharya": "saMskRtam/shankaraH/mUlam",
  "Harikrishnadas Goenka": "saMskRtam/shankaraH/hindI/harikRShNadAsaH",
  "Sanskrit Commentary By Swami Gambirananda": "saMskRtam/shankaraH/english/gambhIrAnandaH",
  "Anandgiri": "saMskRtam/shankaraH/AnandagiriH",
  "Madhusudan Saraswati": "saMskRtam/shankaraH/madhusUdana-sarasvatI",
  "Neelkanth": "saMskRtam/shankaraH/nIlakaNThaH",
  "Dhanpati": "saMskRtam/shankaraH/dhanapatiH",


  "वल्लभ-सम्प्रदायः": "____________",
  "Vallabhacharya": "saMskRtam/vallabhaH/mUlam",
  "Purushottamji": "saMskRtam/vallabhaH/puruShottamaH",

  "संस्कृतटीकान्तरम्": "____________",
  "Sridhara": "saMskRtam/shrIdhara-svAmI",

  "हिन्दी-टीकाः": "____________",
  "Chinmayananda": "hindI/chinmayAnandaH",
  "Swami Tejomayananda": "hindI/tejomayAnandaH/anuvAdaH",
  "Hindi Translation By Swami Ramsukhdas": "hindI/rAmasukhadAsaH/anuvAdaH",
  "Hindi Commentary By Swami Ramsukhdas": "hindI/rAmasukhadAsaH/TIkA",

  "आङ्ग्ल-टीकाः": "____________",
  "Translation By By Dr. S. Sankaranarayan": "english/shankaranArAyaNaH",
  "English Translation By Swami Gambirananda": "english/gambhIrAnandaH",
  "Purohit Swami": "english/purohitasvAmI",
  "Adidevananda": "english/AdidevanandaH",
  "English Translation By Swami Sivananda": "english/shivAnandaH/anuvAdaH",
  "English Commentary By Swami Sivananda": "english/shivAnandaH/TIkA",
}



def folder_path_from_title(title):
  title_substrings = sorted(iitk_title_to_folder_path.keys(), key=lambda x: len(x), reverse=True)
  for title_substring in title_substrings:
    folder_path = iitk_title_to_folder_path[title_substring]
    if title_substring in title:
      return folder_path
  return None

