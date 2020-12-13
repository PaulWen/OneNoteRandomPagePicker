import json
import os
import re
import sys
from datetime import datetime

import requests
from scrapy.crawler import CrawlerProcess

import microsoft_graph_device_flow as auth
import onenote_page_content_scraper as page_content_scraper
import onenote_sync_scraper as sync_scraper
import onenote_types as types

LAST_SYNC_DATE_FILE = "lastSyncDate.txt"
ONENOTE_ELEMENTS_FILE = "onenoteElements.json"
PAGE_CONTENT_FOLDER = "./page-content/"

CRAWLER_CONFIG = {
        'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)',
        'FEED_FORMAT': 'json',
        'FEED_URI': 'result.json',
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'RETRY_HTTP_CODES': [429],
        'CLOSESPIDER_PAGECOUNT': 10,
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': None, # deactivate default middleware
            'onenote_retry_middleware.TooManyRequestsRetryMiddleware': 543, # activate custom middleware for retries (543 is the priority of this middleware)
        }
    }

def genarateDictionaryFromList(allAlfredData: [types.OneNoteElement]):
    alfredDictionaryData = {}

    for element in allAlfredData:
        alfredDictionaryData[element.uid] = element

    return alfredDictionaryData

def genarateListFromDictionary(allAlfredDataDictionary: {types.OneNoteElement}):
    allAlfredListData = []

    for key in allAlfredDataDictionary:
        allAlfredListData.append(allAlfredDataDictionary[key])

    return allAlfredListData

def genarateParentChildDictionaryFromDictionary(alfredDataDictionary: {str, types.OneNoteElement}):
    alfredParentChildDictionary = {}

    for element in alfredDataDictionary:
        element = alfredDataDictionary[element]

        if element.parentUid == None:
            continue

        if element.parentUid not in alfredParentChildDictionary:
            alfredParentChildDictionary[element.parentUid] = []

        alfredParentChildDictionary[element.parentUid].append(element.uid)

    return alfredParentChildDictionary

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
    lastSyncDate=""
    
    with open(file_path, "r") as file:
        lastSyncDate = file.read()
        if lastSyncDate:
            lastSyncDate = datetime.strptime(str(lastSyncDate), '%Y-%m-%dT%H:%M:%S.%f%z')
    
    return lastSyncDate

def store_last_sync_date_in_file(file_path: str, date: str):
    with open(file_path, mode='w') as file:
        file.write(date)

def recursively_find_url_of_first_child_page(element: types.OneNoteElement, alfredDataDictionary, alfredParentChildDictionary):
    if (element.onenoteType == types.OneNoteType.PAGE):
        return element.arg
    
    if (element.uid in alfredParentChildDictionary):
        childElement = alfredDataDictionary[alfredParentChildDictionary[element.uid][0]]
        return recursively_find_url_of_first_child_page(childElement, alfredDataDictionary, alfredParentChildDictionary)
        
    return None

def add_page_urls_to_elements_without_url(allAlfredDataList: [types.OneNoteElement], alfredDataDictionary, alfredParentChildDictionary):
    for element in allAlfredDataList:
        if (element.arg == None):
            pageUrl = recursively_find_url_of_first_child_page(element, alfredDataDictionary, alfredParentChildDictionary)
            
            if (pageUrl != None):
                sectionUrl = re.sub(r'page-id=.*&', '', pageUrl)
                element.arg = sectionUrl

def delete_pages(pagesUids):
    for pageUid in pagesUids:
        filePath = PAGE_CONTENT_FOLDER + pageUid + ".html"
        if os.path.isfile(filePath):
            os.remove(filePath)

def main():
    config = json.load(open(sys.argv[1]))

    allAlfredData = load_alfred_data_from_file(ONENOTE_ELEMENTS_FILE)
    alfredDataDictionary = genarateDictionaryFromList(allAlfredData)
    alfredParentChildDictionary = genarateParentChildDictionaryFromDictionary(alfredDataDictionary)
    
    pagesDeleted = set()
    pagesModified = set()
    
    lastSyncDate = load_last_sync_date_from_file(LAST_SYNC_DATE_FILE)
    thisSyncDate = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S.%f%z')

    accessToken = auth.retrieveAccessToken()
    
    crawlOneNoteElements = CrawlerProcess(CRAWLER_CONFIG)
    crawlOneNoteElements.crawl(sync_scraper.OneNoteSyncSpider, accessToken, alfredDataDictionary, alfredParentChildDictionary, lastSyncDate, pagesModified, pagesDeleted)
    crawlOneNoteElements.start() # the script will block here until the crawling is finished

    alfredParentChildDictionary = genarateParentChildDictionaryFromDictionary(alfredDataDictionary)
    allAlfredDataList = genarateListFromDictionary(alfredDataDictionary)

    add_page_urls_to_elements_without_url(allAlfredDataList, alfredDataDictionary, alfredParentChildDictionary)

    store_alfred_data_in_file(ONENOTE_ELEMENTS_FILE, allAlfredDataList)
    store_last_sync_date_in_file(LAST_SYNC_DATE_FILE, thisSyncDate)

    delete_pages(pagesDeleted)

    crawlPageContent = CrawlerProcess(CRAWLER_CONFIG)
    crawlPageContent.crawl(page_content_scraper.OneNotePageContentSpider, accessToken, pagesModified, PAGE_CONTENT_FOLDER)
    crawlPageContent.start() # the script will block here until the crawling is finished

    print("Done")

main()
