import json
import sys
from datetime import datetime

import requests
from scrapy.crawler import CrawlerProcess

import microsoft_graph_device_flow as auth
import onenote_page_scraper as scraper
import onenote_types as types

LAST_SYNC_DATE_FILE = "lastSyncDate.txt"
ONENOTE_ELEMENTS_FILE = "onenoteElements.json"

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
    alfredParentChildDictionary = {
        "notebooks": set()
    }

    for element in alfredDataDictionary:
        element = alfredDataDictionary[element]
        if element.onenoteType == types.OneNoteType.NOTEBOOK:
            alfredParentChildDictionary[types.NOTEBOOKS_KEY].add(element.uid)

        if element.parentUid not in alfredParentChildDictionary:
            alfredParentChildDictionary[element.parentUid] = set()

        alfredParentChildDictionary[element.parentUid].add(element.uid)

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



def main():
    config = json.load(open(sys.argv[1]))

    allAlfredData = load_alfred_data_from_file(ONENOTE_ELEMENTS_FILE)
    alfredDataDictionary = genarateDictionaryFromList(allAlfredData)
    alfredParentChildDictionary = genarateParentChildDictionaryFromDictionary(alfredDataDictionary)
    
    lastSyncDate = load_last_sync_date_from_file(LAST_SYNC_DATE_FILE)
    thisSyncDate = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S.%f%z')

    accessToken = auth.retrieveAccessToken()
    
    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)',
        'FEED_FORMAT': 'json',
        'FEED_URI': 'result.json',
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'RETRY_HTTP_CODES': [429],
        'CLOSESPIDER_PAGECOUNT': 10,
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': None, # deactivate default middleware
            'onenote_page_scraper.TooManyRequestsRetryMiddleware': 543, # activate custom middleware for retries (543 is the priority of this middleware)
        }
    })
    process.crawl(scraper.OneNotePageSpider, accessToken, alfredDataDictionary, alfredParentChildDictionary, lastSyncDate)
    process.start() # the script will block here until the crawling is finished

    alfredParentChildDictionary = genarateParentChildDictionaryFromDictionary(alfredDataDictionary)
    allAlfredDataList = genarateListFromDictionary(alfredDataDictionary)

    store_alfred_data_in_file(ONENOTE_ELEMENTS_FILE, allAlfredDataList)
    store_last_sync_date_in_file(LAST_SYNC_DATE_FILE, thisSyncDate)

    print("Done")

main()
