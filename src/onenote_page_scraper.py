# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime

import scrapy
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

import onenote_types as types


class OneNotePageSpider(scrapy.Spider):

    def __init__(self, accessToken, allAlfredData: [types.OneNoteElement], lastSyncDate):
        self.name = 'OneNotePage'
        self.allowed_domains = ['graph.microsoft.com']
        self.accessToken = accessToken
        self.allAlfredData = allAlfredData
        self.lastSyncDate = lastSyncDate if type(lastSyncDate) is datetime else datetime(2000, 1, 1)
        self.alfredDataDictionary = self.genarateDictionaryFromList(self.allAlfredData)
        self.alfredParentChildDictionary = self.genarateParentChildDictionaryFromList(self.allAlfredData)

    def genarateDictionaryFromList(self, allAlfredData: [types.OneNoteElement]):
        alfredDictionaryData = {}

        for element in allAlfredData:
            alfredDictionaryData[element.uid] = element

        return alfredDictionaryData
    
    def genarateParentChildDictionaryFromList(self, allAlfredData: [types.OneNoteElement]):
        alfredParentChildDictionary = {}

        for element in allAlfredData:
            if element.parentUid not in alfredParentChildDictionary:
                alfredParentChildDictionary[element.parentUid] = []
            
            alfredParentChildDictionary[element.parentUid].append(element.uid)

        return alfredParentChildDictionary
    
    def start_requests(self):
        yield scrapy.Request(url='https://graph.microsoft.com/v1.0/me/onenote/sections',  method="GET", headers={"Authorization": "Bearer " + self.accessToken})

    def parse(self, response):
        sections = json.loads(response.text)
        sectionInfo = {
            "sectionName": sections["value"][0]["displayName"],
            "notebookName": sections["value"][0]["parentNotebook"]["displayName"]
        }
        
        # do only scrape notebooks which do not include "(Archiv)" in their name and
        # therefore are not yet archived
        if sectionInfo["notebookName"].find("(Archiv)") == -1:
            for section in sections["value"]:
                yield scrapy.Request(meta={"sectionInfo": sectionInfo}, url=section["pagesUrl"], method="GET", headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_pages)

    def parse_pages(self, response):
        sectionInfo = response.meta["sectionInfo"]
        pages = json.loads(response.text)

        for page in pages["value"]:
            yield {
                'pageName': page["title"],
                'pageOneNoteClientUrl': page["links"]["oneNoteClientUrl"]["href"],
                'parentSectionName': sectionInfo["sectionName"],
                'notebookName': sectionInfo["notebookName"]
            }
    
class TooManyRequestsRetryMiddleware(RetryMiddleware):

    def __init__(self, crawler):
        super(TooManyRequestsRetryMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response, spider):
        if request.meta.get('dont_retry', False):
            return response
        elif response.status == 429:
            self.crawler.engine.pause()
            time.sleep(60) # If the rate limit is renewed in a minute, put 60 seconds, and so on.
            self.crawler.engine.unpause()
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        elif response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        return response 
