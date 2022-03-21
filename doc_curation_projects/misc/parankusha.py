import logging
from doc_curation.scraping import parankusha

if __name__ == '__main__':
    browser = parankusha.get_logged_in_browser(headless=False)
    parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "देशिक-स्तोत्राणि", "expand:देशिक-स्तोत्राणि", "Stotram-श्री अभीतिस्तवः"], outdir="/home/vvasuki/sanskrit/raw_etexts/kAvyam/stotram/vedAnta-deshikaH/")