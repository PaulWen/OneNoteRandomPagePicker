# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime

import scrapy
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

import onenote_types as types


class OneNotePageSpider(scrapy.Spider):

    def __init__(self, accessToken, alfredDataDictionary: {str, types.OneNoteElement}, alfredParentChildDictionary: {str, (str)}, lastSyncDate):
        self.name = 'OneNotePage'
        self.allowed_domains = ['graph.microsoft.com']
        self.accessToken = accessToken
        self.lastSyncDate = lastSyncDate if type(lastSyncDate) is datetime else datetime.strptime(
            '2000-01-01T00:00:00.000Z', "%Y-%m-%dT%H:%M:%S.%f%z")
        self.alfredDataDictionary = alfredDataDictionary
        self.alfredParentChildDictionary = alfredParentChildDictionary

    def start_requests(self):
        yield scrapy.Request(meta={types.PARENT_UID_KEY: types.NOTEBOOKS_KEY, types.ONENOTE_TYPE_KEY: types.OneNoteType.NOTEBOOK}, url='https://graph.microsoft.com/v1.0/me/onenote/notebooks', method="GET",
                             headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)

    '''
    Can be used to parse one type of onenote elements (e.g. notebook, section, section
    group, page). The function syncs the data with the current set of data. 
    '''
    def parse_onenote_elements(self, response):
        parentUid = response.meta[types.PARENT_UID_KEY]
        childOnenoteType = response.meta[types.ONENOTE_TYPE_KEY]
        children = json.loads(response.text)["value"]

        deletedChildren = self.identify_deleted_children(parentUid, children)
        self.delete_recursively(deletedChildren)

        modifiedChildren = self.identify_modified_children(children)

        for child in modifiedChildren:
            self.update_modified_element(childOnenoteType, child, parentUid)
            scrape_child_request = self.scrape_children(child)
            for request in scrape_child_request:
                yield request


    '''
    This function detects all the deleted children of a parent.
    For this to work, it is expacted that the list of children includes all the children
    the parent currently has. 
    '''                                 
    def identify_deleted_children(self, parentUid, children):
        childrenUids = set()
        for child in children:
            childrenUids.add(child["id"])

        pastChildrenUids = self.alfredParentChildDictionary[parentUid] if None else set()

        deletedElements = pastChildrenUids - childrenUids

        return deletedElements

    '''
    Identifies all the elements in the list of elements that need to be updated.
    It is decided based on the name of an element and its lastModifiedTimestamp if an
    element needs to be updated or not.
    '''
    def identify_modified_children(self, children):
         for child in children:
            # do only scrape elements which do not include "(Archiv)" in their name and
            # therefore are not yet archived
            if self.extract_title(child).find("(Archiv)") > -1:
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
            yield scrapy.Request(meta={types.PARENT_UID_KEY: parent["id"], types.ONENOTE_TYPE_KEY: types.OneNoteType.SECTION_GROUP}, url=parent["sectionGroupsUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken},
                                callback=self.parse_onenote_elements)
        
        if "sectionsUrl" in parent:
            yield scrapy.Request(meta={types.PARENT_UID_KEY: parent["id"], types.ONENOTE_TYPE_KEY: types.OneNoteType.SECTION}, url=parent["sectionsUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)
        
        if "pagesUrl" in parent:
            yield scrapy.Request(meta={types.PARENT_UID_KEY: parent["id"], types.ONENOTE_TYPE_KEY: types.OneNoteType.PAGE}, url=parent["pagesUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)


    def map_element(self, elementType: types.OneNoteType, element, parentUid):
        if elementType == types.OneNoteType.NOTEBOOK:
            return self.map_element_to_notebook(element)

        if elementType == types.OneNoteType.SECTION_GROUP:
            return self.map_element_to_section_group(element, parentUid)

        if elementType == types.OneNoteType.SECTION:
            return self.map_element_to_section(element, parentUid)

        if elementType == types.OneNoteType.PAGE:
            return self.map_element_to_page(element, parentUid)

    def map_element_to_notebook(self, element):
        return types.OneNoteElement(
                    self.extract_title(element),
                    self.extract_title(element),
                    element['id'],
                    self.extract_title(element),
                    self.extract_link(element),
                    "icons/notebook.png",
                    "file",
                    types.OneNoteType.NOTEBOOK,
                    None
                )
    
    def map_element_to_section_group(self, element, parentUid):
        return types.OneNoteElement(
                    self.extract_title(element),
                    self.extract_title(element),
                    element['id'],
                    self.extract_title(element['parentNotebook']),
                    None,
                    "icons/section-group.png",
                    "file",
                    types.OneNoteType.SECTION_GROUP,
                    parentUid
                )
    
    def map_element_to_section(self, element, parentUid):
        return types.OneNoteElement(
                    self.extract_title(element),
                    self.extract_title(element),
                    element['id'],
                    self.extract_title(element['parentNotebook']),
                    None,
                    "icons/section.png",
                    "file",
                    types.OneNoteType.SECTION,
                    parentUid
                )
    
    def map_element_to_page(self, element, parentUid):
        return types.OneNoteElement(
                    self.extract_title(element),
                    self.extract_title(element),
                    element['id'],
                    self.extract_title(element['parentSection']),
                    self.extract_link(element),
                    "icons/page.png",
                    "file",
                    types.OneNoteType.PAGE,
                    parentUid
                )

    def update_modified_element(self, elementOnenoteType, element, parentUid):
        elementMapped = self.map_element(elementOnenoteType, element, parentUid)
        self.alfredDataDictionary[elementMapped.uid] = elementMapped

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

    def extract_title(self, element):
        if 'displayName' in element:
            return element['displayName']
        
        if 'title' in element:
            return element['title']

        raise RuntimeError("Cannot retrieve title of element: " + element ["self"]) 
   
    def extract_link(self, element):
        if 'href' in element['links']['oneNoteClientUrl']:
            return element['links']['oneNoteClientUrl']['href']
        
        return element['links']['oneNoteClientUrl'] 

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
