import asyncio
import math
import os
import re
import string
import sys
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import reduce

import requests
from lxml import etree
from indic_transliteration import sanscript
from requests import Session

LISTINGS_BASE_URI = 'http://eoh.rkmathbangalore.org/listing/alphabet'
WORD_PAGE_BASE_URI = 'http://eoh.rkmathbangalore.org/describe/word'
concurrency = 10


HWS_XLITERATE_SCHEME_MAPS = [
    sanscript.SchemeMap(sanscript.SCHEMES[sanscript.IAST], sanscript.SCHEMES[script])
    for script in [sanscript.DEVANAGARI, sanscript.ITRANS, sanscript.TAMIL, sanscript.TELUGU]
]


def get_listing_pages():
    # we are getting all once for proper hyperlinking
    for alphabet in string.ascii_uppercase:
        yield requests.get('{}/{}'.format(LISTINGS_BASE_URI, alphabet)).text


def _get_class_matching_xpath(tag: str, clsname: str):
    return "//{tag}[contains(concat(' ', normalize-space(@class), ' '), ' {cls} ')]".format(tag=tag, cls=clsname)


def get_first_matched_elem(elem, xpath):
    matches = elem.xpath(xpath)
    return matches[0] if len(matches) else None


def extract_words(listing_page: str):
    page_elem = etree.HTML(listing_page)
    word_links_block_elem = get_first_matched_elem(page_elem, _get_class_matching_xpath('div', 'word-list'))
    return [
        e.get('href').rsplit(sep='/', maxsplit=1)[1]
        for e in word_links_block_elem
    ] if word_links_block_elem is not None else []


def get_word_page(word: str):
    return requests.get('{}/{}'.format(WORD_PAGE_BASE_URI, word)).text


def get_word_page_components(word_page: str):
    page_elem = etree.HTML(word_page)
    hw_elem = get_first_matched_elem(page_elem, _get_class_matching_xpath('h1', 'head-word'))
    hw_note_elem = get_first_matched_elem(page_elem, _get_class_matching_xpath('h3', 'head-word-note'))
    descr_elem = get_first_matched_elem(page_elem, _get_class_matching_xpath('div', 'description'))

    #  print(hw_elem, hw_note_elem)
    description = reduce(
        lambda s, n: s + etree.tostring(n, method='html', encoding='unicode', with_tail=False) + (n.tail or '').strip(), descr_elem, '')

    return {
        "headword": hw_elem.text.strip() if hw_elem is not None else None,
        "headword_note": hw_note_elem.text.strip() if hw_note_elem is not None else None,
        "description": description
    }


def get_bl_headwords(iast_word: str):
    print(iast_word)
    iast_word = iast_word.lower()
    from indic_transliteration import sanscript
    return [
        sanscript.transliterate(iast_word, scheme_map=sm)
        for sm in HWS_XLITERATE_SCHEME_MAPS
    ] + [iast_word]

def get_bl_body(components: dict):
    header_part = '<b>{}</b>'.format(components['headword']) if 'headword' in components else ''
    note_part = '<b><i>{}</i></b>'.format(components['headword_note']) if components.get('headword_note') else ''
    descr_part = components.get('description', '').replace('\n', ' ')

    return '{}<br>{}------------------------------------------<br>{}'.format(
        header_part,
        note_part + '<br>' if note_part else '',
        descr_part
    )


def get_bl_directives():
    babylon_directives = OrderedDict([
        ("stripmethod", "keep"),
        ("sametypesequence", "h"),
        ("bookname", 'Ramakrishna Math - A Concise Encyclopaedia of Hinduism')
    ])
    return babylon_directives


def get_bl_directives_string():
    return ''.join([
        "#{key}={val}\n".format(key=key, val=val)
        for key, val in get_bl_directives().items()
    ])


def get_bl_entry(components: dict):
    hws = get_bl_headwords(components['headword'])
    hws_part = '|'.join(hws)
    body_part = get_bl_body(components)
    return '{}\n{}\n\n'.format(hws_part, body_part)


def fetch(session: Session, url):
    with session.get(url) as response:
        if response.status_code != 200:
            print("FAILURE::{0}".format(url))
            return None
        data = response.text
        return data


async def get_data_asynchronous(urls):
    responses = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        with requests.Session() as session:
            # Set any session parameters here before calling `fetch`
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    executor,
                    fetch,
                    *(session, url) # Allows us to pass in multiple arguments to `fetch`
                )
                for url in urls
            ]
            for response in await asyncio.gather(*tasks):
                responses.append(response)

    return responses


def get_urls(urls):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return get_data_asynchronous(urls)
    #  future = asyncio.ensure_future(get_data_asynchronous(urls))
    #  loop.run_until_complete(future)
    #  return future.result()


def batch_get_urls(urls, batch_size):
    return [
        get_urls(urls[batch_size * i: batch_size * (i + 1)])
        for i in range(math.ceil(len(urls) / batch_size))
    ]


def batch_get_word_pages(words, batch_size):
    return batch_get_urls([
        '{}/{}'.format(WORD_PAGE_BASE_URI, word)
        for word in words
    ], batch_size)


async def _add_entries_from_cache(bl_file, cache_folder_path):
    cached_file_names = [
        fn for fn in os.listdir(cache_folder_path)
        if fn.endswith('.html')
    ]
    all_words = []
    for fn in cached_file_names:
        fp = os.path.join(cache_folder_path, fn)
        with open(fp, 'rb') as wpf:
            word_page = wpf.read().decode('utf-8')
        components = get_word_page_components(word_page)
        all_words.append(components['headword'])
        bl_entry = get_bl_entry(components)
        bl_file.write(bl_entry.encode('utf-8'))

    return all_words


def hyperlink(bl_file_path, all_words: list):
    if sys.platform != 'linux':
        print('hyperlinking currently requires sed, which may exist only on unix compilant platforms')
        sys.exit(1)

    print('\nhyperlinking.... may take a minute')
    considered_words = filter(lambda w: len(w) > 3 and '"' not in w, all_words)
    sorted_words = sorted(considered_words, key=lambda w: len(w), reverse=True)

    batch_size = 100
    no_batches = math.ceil(len(sorted_words) / batch_size)

    for bno in range(no_batches):
        words = sorted_words[batch_size * bno : batch_size * (bno + 1)]
        sed_command = 'sed -i \'' + '; '.join([
            r'7~3s#\([,;\. -]\)\({w}\)\([,;-\. -]\)#\1<a href="{s}">{s}</a>\3#ig'.format(
                w=w, s=sanscript.transliterate(w.lower(), scheme_map=HWS_XLITERATE_SCHEME_MAPS[0]))
            for w in words
        ]) + '\' "{}"'.format(bl_file_path)
        #  print(sed_command)
        os.system(sed_command)


async def  _add_entries_from_live(bl_file, cache_folder_path):
    listing_pages = get_listing_pages()
    all_words = []
    for page in listing_pages:
        words = extract_words(page)
        all_words.extend(words)

        batch_size = 50
        word_page_future_batches = batch_get_word_pages(words, batch_size)
        # word_index = 0

        for futures in word_page_future_batches:
            batch_pages = await futures
            for word_page in batch_pages:
                # word = words[word_index]
                components = get_word_page_components(word_page)
                if cache_folder_path:
                    word_page_path = os.path.join(cache_folder_path, '{}.html'.format(components['headword']))
                    with open(word_page_path, 'wb') as wpf:
                        wpf.write(word_page.encode('utf-8'))

                #  print(word, components)
                bl_entry = get_bl_entry(components)
                bl_file.write(bl_entry.encode('utf-8'))
    return all_words


async def _create_babyloan(target_file_path='rkmath_encyclopedia_of_hinduism.babyloan', cache_folder_path=None, use_cached=False):

    bl_file = open(target_file_path, 'wb')
    bl_file.write(''.encode('utf-8'))
    bl_file.close()

    bl_file = open(target_file_path, 'ab')
    bl_file.write('\n'.encode('utf-8'))
    bl_file.write(get_bl_directives_string().encode('utf-8'))
    bl_file.write('\n'.encode('utf-8'))

    all_words = None
    if cache_folder_path and use_cached and os.path.isdir(cache_folder_path):
        print('using cached pages')
        all_words = await _add_entries_from_cache(bl_file, cache_folder_path)

    else:
        print('using live pages')
        if cache_folder_path:
            os.makedirs(cache_folder_path, exist_ok=True)
        all_words = await _add_entries_from_live(bl_file, cache_folder_path)

    bl_file.close()
    hyperlink(target_file_path, all_words)


def create_babyloan(*args, **kwargs):
    asyncio.get_event_loop().run_until_complete(_create_babyloan(*args, **kwargs))


if __name__ == '__main__':
    create_babyloan(*sys.argv[1:])
