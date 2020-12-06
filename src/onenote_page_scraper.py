# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime

import scrapy
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

import onenote_types as types

PARENT_UID_KEY = "parentUid"
NOTEBOOKS_KEY = "notebooks"

class OneNotePageSpider(scrapy.Spider):

    def __init__(self, accessToken, allAlfredData: [types.OneNoteElement], lastSyncDate):
        self.name = 'OneNotePage'
        self.allowed_domains = ['graph.microsoft.com']
        self.accessToken = accessToken
        self.lastSyncDate = lastSyncDate if type(lastSyncDate) is datetime else datetime.strptime(
            '2000-01-01T00:00:00.000Z', "%Y-%m-%dT%H:%M:%S.%f%z")
        self.alfredDataDictionary = self.genarateDictionaryFromList(allAlfredData)
        self.alfredParentChildDictionary = self.genarateParentChildDictionaryFromList(allAlfredData)

    def genarateDictionaryFromList(self, allAlfredData: [types.OneNoteElement]):
        alfredDictionaryData = {}

        for element in allAlfredData:
            alfredDictionaryData[element.uid] = element

        return alfredDictionaryData

    def genarateParentChildDictionaryFromList(self, allAlfredData: [types.OneNoteElement]):
        alfredParentChildDictionary = {
            "notebooks": set()
        }

        for element in allAlfredData:
            if element.onenoteType == types.OneNoteType.NOTEBOOK:
                alfredParentChildDictionary[NOTEBOOKS_KEY].add(element.uid)

            if element.parentUid not in alfredParentChildDictionary:
                alfredParentChildDictionary[element.parentUid] = set()

            alfredParentChildDictionary[element.parentUid].add(element.uid)

        return alfredParentChildDictionary

    def start_requests(self):
        yield scrapy.Request(meta={PARENT_UID_KEY: NOTEBOOKS_KEY}, url='https://graph.microsoft.com/v1.0/me/onenote/notebooks', method="GET",
                             headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_notebooks)

    def parse_notebooks(self, response):
        notebooks = json.loads(response.text)["value"]

        # check if any notebooks have been deleted
        notbookUids = set()
        for notebook in notebooks:
            notbookUids.add(notebook["id"])

        deletedNotebooks = self.alfredParentChildDictionary[NOTEBOOKS_KEY] - notbookUids

        # remove deleted notebooks and all the child elements from the
        # alfredDataDictionary
        self.delete_recursively(deletedNotebooks)

        for notebook in notebooks:
            # do only scrape notebooks which do not include "(Archiv)" in their name and
            # therefore are not yet archived
            if notebook["displayName"].find("(Archiv)") > -1:
                continue

            # do only scrape notebooks which have been updated since the last sync
            lastModified = self.parse_datetime(notebook["lastModifiedDateTime"])
            if lastModified < self.lastSyncDate:
                continue

            # add/replace notebook element in data
            self.alfredDataDictionary[notebook["id"]] = types.OneNoteElement(
                    notebook['displayName'],
                    notebook['displayName'],
                    notebook['id'],
                    notebook['displayName'],
                    notebook['links']['oneNoteClientUrl'],
                    "icons/notebook.png",
                    "file",
                    types.OneNoteType.NOTEBOOK,
                    None
                ) 

            # scrape children
            yield scrapy.Request(url=notebook["sectionGroupsUrl"], method="GET",
                                 headers={"Authorization": "Bearer " + self.accessToken},
                                 callback=self.parse_section_groups)
            yield scrapy.Request(url=notebook["sectionsUrl"], method="GET",
                                 headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_sections)
    
    '''
    Can be used to parse one type of onenote elements (e.g. notebook, section, section
    group, page). The function syncs the data with the current set of data. 
    '''
    def parse_onenote_elements(self, response):
        parentUid = response.meta[PARENT_UID_KEY]
        children = json.loads(response.text)["value"]

        deletedChildren = self.identify_deleted_elements(parentUid, children)
        self.delete_recursively(deletedChildren)

        modifiedChildren = self.identify_modified_children(children)

        for child in modifiedChildren:
            # add/replace element in data
            self.alfredDataDictionary[child["id"]] = types.OneNoteElement(
                    notebook['displayName'],
                    notebook['displayName'],
                    notebook['id'],
                    notebook['displayName'],
                    notebook['links']['oneNoteClientUrl'],
                    "icons/notebook.png",
                    "file",
                    types.OneNoteType.NOTEBOOK,
                    None
                ) 

            # scrape children
            self.scrape_children(child)

    '''
    This function detects all the deleted children of a parent.
    For this to work, it is expacted that the list of children includes all the children
    the parent currently has. 
    '''                                 
    def identify_deleted_children(self, parentUid, children):
        childrenUids = set()
        for child in children:
            childrenUids.add(child["id"])

        deletedElements = self.alfredParentChildDictionary[parentUid] - childrenUids

        return deletedElements

    '''
    Identifies all the elements in the list of elements hat need to be updated.
    It is decided based on the name of an element and its lastModifiedTimestamp if an
    element needs to be updated or not.
    '''
    def identify_modified_children(self, children):
         for child in children:
            # do only scrape elements which do not include "(Archiv)" in their name and
            # therefore are not yet archived
            if child["displayName"].find("(Archiv)") > -1:
                continue

            # do only scrape elements which have been updated since the last sync
            lastModified = self.parse_datetime(child["lastModifiedDateTime"])
            if lastModified < self.lastSyncDate:
                continue
        
            yield child

    '''
    Scrapes the children of the passed in element.
    '''
    def scrape_children(self, parent):
        if "sectionGroupsUrl" in parent:
            yield scrapy.Request(meta={PARENT_UID_KEY: parent["id"]}, url=parent["sectionGroupsUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken},
                                callback=self.parse_onenote_elements)
        
        if "sectionsUrl" in parent:
            yield scrapy.Request(meta={PARENT_UID_KEY: parent["id"]}, url=parent["sectionsUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)
        
        if "sectionsUrl" in parent:
            yield scrapy.Request(meta={PARENT_UID_KEY: parent["id"]}, url=parent["sectionsUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)
        
        if "sectionsUrl" in parent:
            yield scrapy.Request(meta={PARENT_UID_KEY: parent["id"]}, url=parent["sectionsUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)


    def parse_section_groups(self, response):
        sectionGroups = json.loads(response.text)["value"]

         # check if any notebooks have been deleted
        sectionGroupsUids = set()
        for notebook in notebooks:
            sectionGroupsUids.add(notebook["id"])

        deletedNotebooks = self.alfredParentChildDictionary["notebooks"] - sectionGroupsUids

        # remove deleted notebooks and all the child elements from the
        # alfredDataDictionary
        self.delete_recursively(deletedNotebooks)

        for notebook in notebooks:
            # do only scrape notebooks which do not include "(Archiv)" in their name and
            # therefore are not yet archived
            if notebook["displayName"].find("(Archiv)") > -1:
                continue

            # do only scrape notebooks which have been updated since the last sync
            lastModified = self.parse_datetime(notebook["lastModifiedDateTime"])
            if lastModified < self.lastSyncDate:
                continue

            # add/replace notebook element in data
            self.alfredDataDictionary[notebook["id"]] = types.OneNoteElement(
                    notebook['displayName'],
                    notebook['displayName'],
                    notebook['id'],
                    notebook['displayName'],
                    notebook['links']['oneNoteClientUrl'],
                    "icons/notebook.png",
                    "file",
                    types.OneNoteType.NOTEBOOK,
                    None
                ) 

            # scrape children
            yield scrapy.Request(url=notebook["sectionGroupsUrl"], method="GET",
                                 headers={"Authorization": "Bearer " + self.accessToken},
                                 callback=self.parse_section_groups)
            yield scrapy.Request(url=notebook["sectionsUrl"], method="GET",
                                 headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_sections)




        for sectionGroup in sectionGroups:
            yield scrapy.Request(url=sectionoGroup["sectionsUrl"], method="GET",
                                 headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_sections)

    def parse_sections(self, response):
        sections = json.loads(response.text)["value"]
        sectionInfo = {
            "sectionName": sections["value"][0]["displayName"],
            "notebookName": sections["value"][0]["parentNotebook"]["displayName"]
        }

        # do only scrape notebooks which do not include "(Archiv)" in their name and
        # therefore are not yet archived
        if sectionInfo["notebookName"].find("(Archiv)") == -1:
            for section in sections:
                yield scrapy.Request(meta={"sectionInfo": sectionInfo}, url=section["pagesUrl"], method="GET",
                                     headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_pages)

    def parse_pages(self, response):
        sectionInfo = response.meta["sectionInfo"]
        pages = json.loads(response.text)["value"]

        for page in pages:
            yield {
                'pageName': page["title"],
                'pageOneNoteClientUrl': page["links"]["oneNoteClientUrl"]["href"],
                'parentSectionName': sectionInfo["sectionName"],
                'notebookName': sectionInfo["notebookName"]
            }

    def delete_recursively(self, uids: [str]):
        for uid in uids:
            if uid in self.alfredParentChildDictionary:
                children = self.alfredParentChildDictionary[uid]
                self.delete_recursively(children)
            if uid in self.alfredDataDictionary:
                del self.alfredDataDictionary[uid]

    def parse_datetime(self, datetimeString: str):
        try:
            return datetime.strptime(datetimeString, "%Y-%m-%dT%H:%M:%S.%f%z")
        except:
            return datetime.strptime(datetimeString, "%Y-%m-%dT%H:%M:%S%z")


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
            time.sleep(60)  # If the rate limit is renewed in a minute, put 60 seconds, and so on.
            self.crawler.engine.unpause()
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        elif response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        return response
