
iitk_title_to_folder_path = {
  "विश्वास-प्रस्तुतिः": "saMskRtam/vishvAsa-prastutiH",
  "मूल श्लोकः": "saMskRtam/mUlam",

  "रामानुज-सम्प्रदायः": "____________",
  "Vedantadeshikacharya": "saMskRtam/venkaTanAthaH",
  "Ramanuja": "saMskRtam/rAmAnujaH/mUlam",
  "Ramanuja's Sanskrit Commentary By Swami Adidevananda": "saMskRtam/rAmAnujaH/english/AdidevAnandaH",

  "अभिनवगुप्त-सम्प्रदायः": "____________",
  "Sanskrit Commentary By Sri Abhinavgupta": "saMskRtam/abhinava-guptaH/mUlam",
  "English Translation of Abhinavgupta's": "saMskRtam/abhinava-guptaH/english/shankaranArAyaNaH",

  "माध्व-सम्प्रदायः": "____________",
  "Madhavacharya": "saMskRtam/madhvaH",
  "Jayatritha": "saMskRtam/jayatIrthaH",

  "शाङ्कर-सम्प्रदायः": "____________",
  "Sanskrit Commentary By Sri Shankaracharya": "saMskRtam/shankaraH/mUlam",
  "Harikrishnadas Goenka": "saMskRtam/shankaraH/hindI/harikRShNadAsaH",
  "Shankaracharya's Sanskrit Commentary By Swami Gambirananda": "saMskRtam/shankaraH/gambhIrAnandaH",
  "Anandgiri": "saMskRtam/AnandagiriH",
  "Madhusudan Saraswati": "saMskRtam/madhusUdana-sarasvatI",

  "संस्कृतटीकान्तरम्": "____________",
  "Vallabhacharya": "saMskRtam/vallabhaH",
  "Sridhara": "saMskRtam/shrIdhara-svAmI",
  "Dhanpati": "saMskRtam/dhanapatiH",
  "Neelkanth": "saMskRtam/nIlakaNThaH",
  "Purushottamji": "saMskRtam/puruShottamaH",

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
  for title_substring, folder_path in iitk_title_to_folder_path.items():
    if title_substring in title:
      return folder_path

