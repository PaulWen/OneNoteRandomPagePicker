import json
import os
from datetime import datetime

from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from twisted.internet import defer, reactor

import onenote_page_content_scraper as page_content_scraper
import onenote_sync_scraper as sync_scraper
import onenote_types as types

LAST_SYNC_DATE_FILE = "lastSyncDate.txt"
ONENOTE_ELEMENTS_FILE = "onenoteElements.json"
PAGE_CONTENT_FOLDER = "./page-content/"

CRAWLER_CONFIG = {
    'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)',
    'FEED_FORMAT': 'json',
    'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    'RETRY_HTTP_CODES': [401, 429],
    # 'CLOSESPIDER_PAGECOUNT': 10,
    'DOWNLOADER_MIDDLEWARES': {
        'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,  # deactivate default middleware
        'onenote_retry_middleware.TooManyRequestsRetryMiddleware': 543,
        # activate custom middleware for retries (543 is the priority of this middleware)
    }
}


def genarateListFromDictionary(allAlfredDataDictionary: {types.OneNoteElement}):
    allAlfredListData = []

    for key in allAlfredDataDictionary:
        allAlfredListData.append(allAlfredDataDictionary[key])

    return allAlfredListData


def genarateDictionaryFromList(allAlfredData: [types.OneNoteElement]):
    alfredDictionaryData = {}

    for element in allAlfredData:
        alfredDictionaryData[element.uid] = element

    return alfredDictionaryData


def load_alfred_data_from_file(file_path: str):
    allAlfredData = []

    with open(file_path, "r") as file:
        data = json.load(file)
        for element in data:
            allAlfredData.append(types.as_onenoteelement(element))

    return allAlfredData


def store_alfred_data_in_file(file_path: str, data: [types.OneNoteElement]):
    with open(file_path, mode='w') as file:
        json.dump([element.__dict__ for element in data], file)


def load_last_sync_date_from_file(file_path: str):
    lastSyncDate = ""

    with open(file_path, "r") as file:
        lastSyncDate = file.read()
        if lastSyncDate:
            lastSyncDate = datetime.strptime(str(lastSyncDate), '%Y-%m-%dT%H:%M:%S.%f%z')

    return lastSyncDate


def store_last_sync_date_in_file(file_path: str, date: str):
    with open(file_path, mode='w') as file:
        file.write(date)


def delete_pages(pagesUids):
    for pageUid in pagesUids:
        filePath = PAGE_CONTENT_FOLDER + pageUid + ".html"
        if os.path.isfile(filePath):
            os.remove(filePath)


def main():
    all_alfred_data = load_alfred_data_from_file(ONENOTE_ELEMENTS_FILE)
    alfred_data_dictionary: {str, types.OneNoteElement} = genarateDictionaryFromList(all_alfred_data)

    pages_deleted = set()
    pages_modified = set()

    lastSyncDate = load_last_sync_date_from_file(LAST_SYNC_DATE_FILE)
    thisSyncDate = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S.%f%z')

    configure_logging()
    scrapyRunner = CrawlerRunner(CRAWLER_CONFIG)

    @defer.inlineCallbacks
    def crawl():
        yield scrapyRunner.crawl(sync_scraper.OneNoteSyncSpider, alfred_data_dictionary,
                                 lastSyncDate, pages_modified, pages_deleted)
        yield scrapyRunner.crawl(page_content_scraper.OneNotePageContentSpider, pages_modified, PAGE_CONTENT_FOLDER,
                                 alfred_data_dictionary)
        reactor.stop()

    crawl()
    reactor.run()  # the script will block here until the crawling is finished

    allAlfredDataList = genarateListFromDictionary(alfred_data_dictionary)
    store_alfred_data_in_file(ONENOTE_ELEMENTS_FILE, allAlfredDataList)
    store_last_sync_date_in_file(LAST_SYNC_DATE_FILE, thisSyncDate)

    delete_pages(pages_deleted)

    print("Done")


main()
