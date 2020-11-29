import json
import sys

import requests
from scrapy.crawler import CrawlerProcess

import microsoft_graph_device_flow as auth
import onenote_page_scraper as onenote

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
    'FEED_URI': 'result.json'
})

process.crawl(onenote.OneNotePageSpider, accessToken)
process.start() # the script will block here until the crawling is finished

print("Done")
