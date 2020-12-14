from indic_transliteration.font_converter.tech_hindi import DVTTVedicConverter


def dump():
  DVTTVedicConverter().convert_mixed(input_file="/home/vvasuki/Documents/books/granthasangrahaH/vedaH/khila_sansknet.txt", out_file="/home/vvasuki/vvasuki-git/vedAH/content/shAkalam/saMhitA/khilam.md")

if __name__ == '__main__':
    dump()