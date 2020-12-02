import json
import sys
from datetime import datetime

import requests
from scrapy.crawler import CrawlerProcess

import microsoft_graph_device_flow as auth
import onenote_page_scraper as scraper
import onenote_types as types

config = json.load(open(sys.argv[1]))

accessToken = auth.retrieveAccessToken()

# Calling graph using the access token
# graph_data = requests.get(  # Use token to call downstream service
#     config["endpoint"],
#     headers={'Authorization': 'Bearer ' + accessToken},).json()
# print("Graph API call result: %s" % json.dumps(graph_data, indent=2))

process = CrawlerProcess({
    'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)',
    'FEED_FORMAT': 'json',
    'FEED_URI': 'result.json',
    'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    'RETRY_HTTP_CODES': [429],
    'DOWNLOADER_MIDDLEWARES': {
        'scrapy.downloadermiddlewares.retry.RetryMiddleware': None, # deactivate default middleware
        'onenote_page_scraper.TooManyRequestsRetryMiddleware': 543 # activate custom middleware for retries (543 is the priority of this middleware)
    }
})

allAlfredData = []
with open('onenoteElements.json', "r") as file:
    data = json.load(file)
    for element in data:
        allAlfredData.append(types.as_onenoteelement(element))

lastSyncDate=""
with open('lastSyncDate.txt', "r") as file:
     lastSyncDate = file.read()
     if lastSyncDate:
        lastSyncDate = datetime.strptime(str(lastSyncDate), '%Y-%m-%d %H:%M:%S')

with open("lastSyncDate.txt", mode='w') as file:
    file.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

process.crawl(scraper.OneNotePageSpider, accessToken, allAlfredData, lastSyncDate)
process.start() # the script will block here until the crawling is finished

print("Done")
