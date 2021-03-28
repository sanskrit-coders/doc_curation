# From https://github.com/lalitaalaalitah/Scrape_IndianCulture.Gov.In_Release/blob/master/v1_DownloadAllBooksFromIndianCultureGovIn_Release_270320221.py

#! /usr/local/bin/python ## Replace with your virtualenv
import requests# Install as --- pip install requests
from bs4 import BeautifulSoup as bs# Install as --- pip install bs4
from datetime import datetime
import os
import pickle
from urllib.parse import unquote
import time
import shutil
# 
# created by    :   lalitaalaalitah
# 
default_timeout = 10
return_code_expected = 200

# dict of TypeOfPDF : [root_dir, base_url, first_page_url]
main_dict = {
  "Manuscripts" : [
    './Scrape_IndianCulture.Gov.In/Manuscripts',
    "https://www.indianculture.gov.in/manuscripts?search_api_fulltext=&page=",
    "https://www.indianculture.gov.in/manuscripts?search_api_fulltext=&page=0",
  ],
  "RareBooks": [
    "./Scrape_IndianCulture.Gov.In/RareBooks",
    "https://www.indianculture.gov.in/rarebooks?search_api_fulltext=&page=",
    "https://www.indianculture.gov.in/rarebooks?search_api_fulltext=&page=0",
  ],
  "eBooks" : [
    './Scrape_IndianCulture.Gov.In/eBooks',
    'https://www.indianculture.gov.in/ebooks?search_api_fulltext=&page=',
    'https://www.indianculture.gov.in/ebooks?search_api_fulltext=&page=0',
  ]
}

def get_page_extract_data_save(
    page_url, i, path_of_csv, list_of_lists_for_resutls, path_of_pickle
):  # page_url is url of page containing search results, i is the part of url where seach page number is define as page=0 etc., path_of_csv is where we save all data as comma separated file
  global n
  # url of the page
  url_of_page = page_url
  # get first page
  return_code_ = 0
  while return_code_ == 0:
    try:
      page = requests.get(url_of_page, timeout=default_timeout)
    except:
      continue
    if page.status_code == return_code_expected:
      break
    time.sleep(10)
  # parse first_page with BeautifulSoup
  parsed_page = bs(page.content, "html.parser")
  # Extract all links for all books in the page
  h2_in_first_page_links = parsed_page.find_all("h2", class_="text-truncate")
  # print each link, get all book title and their links.
  for each_link in h2_in_first_page_links:
    list_for_each_link = []
    # print(each_link)
    each_link_title = each_link.text
    #print(each_link_title)
    each_link_title_href = "https://www.indianculture.gov.in" + each_link.a["href"]
    print(n)
    print(each_link_title_href)
    n += 1
    # Write to list
    if n not in list_for_each_link:
      list_for_each_link.append(str(n))
    if each_link_title not in list_for_each_link:
      list_for_each_link.append(each_link_title)
    if each_link_title_href not in list_for_each_link:
      list_for_each_link.append(each_link_title_href)
    # add this list to list_of_list
    if list_for_each_link not in list_of_lists_for_resutls:
      list_of_lists_for_resutls.append(list_for_each_link)
  # Get last page number
  if i == 0:
    last_page_ = parsed_page.find("li", class_="pager__item pager__item--last")
    last_page = last_page_.text
    last_page_href = last_page_.a["href"]
    last_page_number = last_page_href.split("=")[-1]
    #print(last_page_number)
    return last_page_number
# 
def write_metadata(parsed_html, path_to_save_metadata):
  big_string_of_metadata_list = []
  # Extarct metadata
  metadata_book_title = parsed_html.find('h1', class_='display-5').text.strip()
  big_string_of_metadata_list.append(f"Title : {metadata_book_title}\n")
  # 
  metadata_text_details = parsed_html.find_all('p', class_='textdetails')
  for each_text_detail in metadata_text_details:
    # print(each_text_detail.text.strip())
    big_string_of_metadata_list.append(f"TextDetail : {each_text_detail.text.strip()}\n")
  metadata_dcf_val = parsed_html.find_all('table', class_='table table-bordered table-striped')
  for each_dcf_val in metadata_dcf_val:
    dcf_val_txt_list = each_dcf_val.text.split('\n\n')
    #print(dcf_val_txt_list)
    for each_dcf_val_txt in dcf_val_txt_list:
      each_dcf_val_txt_tab = each_dcf_val_txt.replace('\n', '\t') + '\n'
      big_string_of_metadata_list.append(each_dcf_val_txt_tab)
  # 
  # clean old file
  with open(path_to_save_metadata, 'w') as ptsm:
    pass
  # 
  with open(path_to_save_metadata, 'a') as ptsm:
    for each_item in big_string_of_metadata_list:
      ptsm.write(each_item)
# 
# 
# 
for each_project in main_dict.keys():
  # set root working dir
  root_dir = main_dict[each_project][0]
  print(root_dir)
  # create if not present
  if not os.path.isdir(root_dir):
    os.makedirs(root_dir)
  # change dir
  os.chdir(root_dir)
  # get now_time...
  get_date_time_now = datetime.now()
  # define base url
  base_url = main_dict[each_project][1]
  print(base_url)
  # define first page url
  first_page_url = main_dict[each_project][2]
  print(first_page_url)
  # Get Page Number
  first_page_number = "0"
  # Save all details in a csv, path of csv
  path_of_csv = root_dir + "/" + "all_extracted_data.csv"
  print(path_of_csv)
  # delete old csv
  if os.path.isfile(path_of_csv):
    with open(path_of_csv, "w") as poc:
      pass
  # pickle for all extracted data
  path_of_pickle = path_of_csv + ".pickle"
  # print(path_of_pickle)
  # load csv if exist
  if os.path.isfile(path_of_pickle):
    with open(path_of_pickle, "rb") as poc:
      list_of_lists_for_resutls = pickle.load(poc)
  else:
    list_of_lists_for_resutls = []
  #
  # print(list_of_lists_for_resutls)
  print(len(list_of_lists_for_resutls))
  #
  n = 0
  download_count = 1
  #
  # Prompt for each type doownload
  download_this_category = input('do you want to download this category of PDF? yes(y), No(n)\n')
  # 
  if not download_this_category == 'n':
    last_page_number = get_page_extract_data_save(
      first_page_url, 0, path_of_csv, list_of_lists_for_resutls, path_of_pickle
    )
    download_all_pages_and_get_data_confirm = input('do you want to go through each page dedicated to each book/manuscript and then save that data before downloading. Yes(y) if never run the script to get all data. Else No(n)\n')
    if download_all_pages_and_get_data_confirm == 'y':
      for i in range(1, int(last_page_number) + 1):
        page_number_for_i = str(i)
        url_of_the_page = base_url + page_number_for_i
        get_page_extract_data_save(
          url_of_the_page, i, path_of_csv, list_of_lists_for_resutls, path_of_pickle
        )
      # Now pickle the data
      with open(path_of_pickle, "wb") as pop:
        pickle.dump(list_of_lists_for_resutls, pop)
      # Now write to csv
      with open(path_of_csv, "a") as pof:
        for each_item in list_of_lists_for_resutls:
          string_to_write = (
              each_item[0] + ',"' + each_item[1] + '",' + each_item[2] + "\n"
          )
          pof.write(string_to_write)
    # Now download each page, extract metadata, download pdf/jpg
    nn = 0
    for each_item in list_of_lists_for_resutls:
      print(nn)
      # get book title
      book_title = each_item[1]
      print(book_title)
      # download consent
      download_this_book = input('Do you want to download this book. Yes(y), No(n)?\n')
      # 
      if not download_this_book == 'n':
        # get book page url
        book_page_url = each_item[2]
        print(book_page_url)
        # # dir name
        dir_name =  book_page_url.split('/')[-1]
        print(dir_name)
        # print(f'Old pdf path was {path_for_pdf_dir}')
        new_path_for_pdf_dir = os.path.join(root_dir, 'Downloads', dir_name.replace('.pdf', ''))
        print(f'dir for this pdf/group of images witll be\n{new_path_for_pdf_dir}')
        # 
        if not os.path.isdir(new_path_for_pdf_dir):
          # get the dedicated page
          print('downloading page...')
          # 
          return_code_ = 0
          while return_code_ == 0 :
            try:
              book_page_get = requests.get(book_page_url, timeout=default_timeout)
            except:
              continue
            if book_page_get.status_code == 200:
              break
            time.sleep(10)
          print('got the page.')
          print(book_page_get.status_code)
          # parse it with bs
          parsed_book_page = bs(book_page_get.content, 'html.parser')
          # get class pdf from the page
          class_pdf_in_page = parsed_book_page.find_all('iframe', class_='pdf')
          # 
          nn +=1
          # 
          pdf_related_to_this_page = 0
          # print class
          # confirm that the class exist
          if len(class_pdf_in_page) > 0:
            for each_item in class_pdf_in_page:
              # print(each_item)
              # get src
              src_each_item = each_item['src']
              #print(src_each_item)
              # split and get file address
              pdf_address = src_each_item.split('file=')[-1]
              cleaned_pdf_address = unquote(pdf_address)
              #print(cleaned_pdf_address)
              # get pdf name
              pdf_name = cleaned_pdf_address.split('/')[-1]
              # generate pdf path
              path_for_pdf_dir = os.path.join(root_dir, 'Downloads', pdf_name.replace('.pdf', ''))
              # # print(f'Old pdf path was {path_for_pdf_dir}')
              # create dir
              if not os.path.isdir(path_for_pdf_dir):
                # os.makedirs(path_for_pdf_dir)
                pass
              else:
                shutil.move(path_for_pdf_dir, new_path_for_pdf_dir)
              # 
              if not os.path.isdir(new_path_for_pdf_dir):
                os.makedirs(new_path_for_pdf_dir)
              # create full pdf path in the dir
              pdf_path = new_path_for_pdf_dir + '/' + pdf_name
              print(f'pdf path will be {pdf_path}')
              # create curl
              cmd_for_curl = 'curl ' + cleaned_pdf_address + " -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:87.0) Gecko/20100101 Firefox/87.0' -H 'Accept: */*' -H 'Accept-Language: en-US,en;q=0.8,sa;q=0.5,hi;q=0.3' --compressed -H 'Referer: https://www.indianculture.gov.in/libraries/pdf.js/web/viewer.html?file=https%3A%2F%2Fwww.indianculture.gov.in%2Fsystem%2Ffiles%2FdigitalFilesICWeb%2Figncarepository%2F963%2Fignca-19280-rb.pdf' -H 'DNT: 1' -H 'Connection: keep-alive' -H 'TE: Trailers'" + " --output " + pdf_path
              #print(cmd_for_curl)
              # write all cmd to a file
              with open('all_cmd_curl', 'a') as acc:
                acc.write(cmd_for_curl)
                acc.write('\n')
              # download pdf
              if not os.path.isfile(pdf_path):
                os.system(cmd_for_curl)
                download_count += 1
                if download_count % 100 == 0:
                  time.sleep(60)
              else:
                print('already downloaded')
              # 
              pdf_related_to_this_page += 1
            # # Now save this page as html in a new folder
            # save html file for page
            path_for_html = new_path_for_pdf_dir + '/' + pdf_name + '.html'
            with open(path_for_html, 'wb') as fp:
              fp.write(book_page_get.content)
            # 
            path_for_metadata = path_for_html.replace('.html', '.md')
            # input('press enter to continue')
          else:#Download jpg fro, pages
            # get class pdf from the page
            class_jpg_in_page = parsed_book_page.find_all('div', class_='col-md-6 pt-3')
            if len(class_jpg_in_page) > 0:
              # print(f'total {len(class_jpg_in_page)} images containing elements are present.')
              for each_jpg in class_jpg_in_page:
                # print(each_jpg)
                # find in each_jpg element for img
                each_jpg_img_list = each_jpg.find_all('img')
                for each_img in each_jpg_img_list:
                  #print(each_img)
                  img_each_item = each_img['src']
                  src_each_item = img_each_item
                  #print(src_each_item)
                  # split and get file address
                  cleaned_jpg_address = 'https://www.indianculture.gov.in' + unquote(src_each_item)
                  #print(cleaned_jpg_address)
                  # get pdf name
                  pdf_name = book_page_url.split('/')[-1]
                  print(f'folder name for all jpg will be {pdf_name}')
                  # get jpg name
                  jpg_name = cleaned_jpg_address.split('/')[-1]
                  print(f'this is jpg file name {jpg_name}')
                  # generate pdf path
                  path_for_jpg_dir = os.path.join(root_dir, 'Downloads', pdf_name.replace('.pdf', ''))
                  # create dir
                  if not os.path.isdir(path_for_jpg_dir):
                    os.makedirs(path_for_jpg_dir)
                  # create full pdf path in the dir
                  jpg_path = path_for_jpg_dir + '/' + jpg_name
                  #print(f'pdf path will be {jpg_path}')
                  # create curl
                  cmd_for_curl = 'curl ' + cleaned_jpg_address + " -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:87.0) Gecko/20100101 Firefox/87.0' -H 'Accept: */*' -H 'Accept-Language: en-US,en;q=0.8,sa;q=0.5,hi;q=0.3' --compressed -H 'Referer: https://www.indianculture.gov.in/libraries/pdf.js/web/viewer.html?file=https%3A%2F%2Fwww.indianculture.gov.in%2Fsystem%2Ffiles%2FdigitalFilesICWeb%2Figncarepository%2F963%2Fignca-19280-rb.pdf' -H 'DNT: 1' -H 'Connection: keep-alive' -H 'TE: Trailers'" + " --output " + jpg_path
                  #print(cmd_for_curl)
                  # write all cmd to a file
                  with open('all_cmd_curl', 'a') as acc:
                    acc.write(cmd_for_curl)
                    acc.write('\n')
                  # download images
                  if not os.path.isfile(jpg_path):
                    os.system(cmd_for_curl)
                    download_count += 1
                    if download_count % 100 == 0:
                      time.sleep(60)
                  else:
                    print('already downloaded')
                  # 
                  pdf_related_to_this_page += 1
                  # 
            # # Now save this page as html in a new folder
            # save html file for page
            path_for_html = path_for_jpg_dir + '/' + pdf_name + '.html'
            # 
            with open(path_for_html, 'wb') as fp:
              fp.write(book_page_get.content)
            # 
            path_for_metadata = path_for_html.replace('.html', '.md')
          # write metadata
          if not os.path.isfile(path_for_metadata):
            write_metadata(parsed_book_page, path_for_metadata)
