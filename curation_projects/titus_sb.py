# Potential approaches: 
# 
# 1. Get pages in the range:
# http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm001.htm
# http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm100.htm
# Downside: Matching with kaanda and adhyaaya is harder. 
#
# 2. Use web driver and select text levels.
# 

# noinspection PyUnresolvedReferences
import logging
import os

from doc_curation import titus

browser = titus.browser

if __name__ == '__main__':
    titus.navigate_to_part(base_page_url="http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm.htm", level_3_id=2, level_4_id=3)
    titus.get_text()
    browser.close()
    pass
