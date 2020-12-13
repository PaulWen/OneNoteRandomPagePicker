# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime

import scrapy
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

import onenote_types as types

'''
This spider loads all types of onenote elements (e.g. notebook, section, section group,
page) and syncs them with the current set of onenote elements. If onenote elements already
exist, this spider will only load those elements again that changed since the last sync.
'''
class OneNoteSyncSpider(scrapy.Spider):

    def __init__(self, accessToken, alfredDataDictionary: {str, types.OneNoteElement}, alfredParentChildDictionary: {str, (str)}, lastSyncDate):
        self.name = 'OneNoteSyncSpider'
        self.allowed_domains = ['graph.microsoft.com']
        self.accessToken = accessToken
        self.lastSyncDate = lastSyncDate if type(lastSyncDate) is datetime else datetime.strptime(
            '2000-01-01T00:00:00.000Z', "%Y-%m-%dT%H:%M:%S.%f%z")
        self.alfredDataDictionary = alfredDataDictionary
        self.alfredParentChildDictionary = alfredParentChildDictionary

    def start_requests(self):
        yield scrapy.Request(meta={types.ONENOTE_TYPE_KEY: types.OneNoteType.NOTEBOOK}, url='https://graph.microsoft.com/v1.0/me/onenote/notebooks', method="GET",
                             headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)
        
        yield scrapy.Request(meta={types.ONENOTE_TYPE_KEY: types.OneNoteType.SECTION_GROUP}, url='https://graph.microsoft.com/v1.0/me/onenote/sectiongroups', method="GET",
                             headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)
        
        yield scrapy.Request(meta={types.ONENOTE_TYPE_KEY: types.OneNoteType.SECTION}, url='https://graph.microsoft.com/v1.0/me/onenote/sections', method="GET",
                             headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_elements)

    '''
    Is used to parse one type of onenote elements: notebook, section, section
    group. The function syncs the data with the current set of data. 
    '''
    def parse_onenote_elements(self, response):
        onenoteType = response.meta[types.ONENOTE_TYPE_KEY]
        elements = json.loads(response.text)["value"]

        deletedElementsUids = self.identify_deleted_elements_uids(onenoteType, elements)
        self.delete_recursively(deletedElementsUids)

        modifiedElements = self.identify_modified_elements(elements)

        for element in modifiedElements:
            self.update_modified_element(onenoteType, element)
            
            if onenoteType == types.OneNoteType.SECTION:
                yield self.scrape_pages(element)
   
    '''
    Is used to parse a list of onenote pages. The function syncs the data with the current set of data. 
    '''
    def parse_onenote_pages(self, response):
        sectionUid = response.meta[types.PARENT_UID_KEY]
        pages = json.loads(response.text)["value"]

        deletedPagesUids = self.identify_deleted_pages_uids(sectionUid, pages)
        self.delete_recursively(deletedPagesUids)

        modifiedPages = self.identify_modified_elements(pages)

        for page in modifiedPages:
            self.update_modified_element(types.OneNoteType.PAGE, page)

    '''
    This function detects all the deleted pages of a section.
    For this to work, it is expacted that the list of pages includes all the pages
    the section currently has. 
    '''                                 
    def identify_deleted_pages_uids(self, sectionUid, pages):
        pagesUids = set()
        for page in pages:
            pagesUids.add(page["id"])

        pastChildrenUids = self.alfredParentChildDictionary[sectionUid] if None else set()

        deletedElements = pastChildrenUids - pagesUids

        return deletedElements
    
    '''
    This function detects all the deleted elements of the same type.
    For this to work, it is expacted that the list of peers includes all the peers
    the onenote type currently reviewed. 

    This function is used to detected deleted notebooks section groups and sections.
    '''                                 
    def identify_deleted_elements_uids(self, onenoteType, elements):
        elementUids = set()
        for element in elements:
            elementUids.add(element["id"])
        
        pastElementUids = set()
        for pastElement in self.alfredDataDictionary.values():
            if pastElement.onenoteType == onenoteType:
                pastElementUids.add(pastElement.uid)

        deletedElements = pastElementUids - elementUids

        return deletedElements

    '''
    Identifies all the elements in the list of elements that need to be updated.
    It is decided based on the name of an element and its lastModifiedTimestamp if an
    element needs to be updated or not.
    '''
    def identify_modified_elements(self, elements):
         for element in elements:
            if self.is_element_archived(element):
                continue

            # do only scrape elements which have been updated since the last sync
            lastModified = self.parse_datetime(element["lastModifiedDateTime"])
            if lastModified < self.lastSyncDate:
                continue
        
            yield element

    '''
    Do only scrape elements which do not include "(Archiv)" in their name and
    therefore are not yet archived.
    '''
    def is_element_archived(self, element):
        if self.extract_title(element).find("(Archiv)") > -1:
            return True
        
        if "parentNotebook" in element and element['parentNotebook']['displayName'].find("(Archiv)") > -1:
            return True
        
        link = self.extract_link(element)
        if link != None and link.find("/One%20Note/Archiv/") > -1:
            return True

        return False

    '''
    Scrapes the pages of the passed in element.
    '''
    def scrape_pages(self, parent):
        if "pagesUrl" in parent:
            return scrapy.Request(meta={types.PARENT_UID_KEY: parent["id"]}, url=parent["pagesUrl"], method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_onenote_pages)


    def map_element(self, elementType: types.OneNoteType, element):
        if elementType == types.OneNoteType.NOTEBOOK:
            return self.map_element_to_notebook(element)

        if elementType == types.OneNoteType.SECTION_GROUP:
            return self.map_element_to_section_group(element)

        if elementType == types.OneNoteType.SECTION:
            return self.map_element_to_section(element)

        if elementType == types.OneNoteType.PAGE:
            return self.map_element_to_page(element)

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
                    None,
                    element['lastModifiedDateTime']
                )
    
    def map_element_to_section_group(self, element):
        return types.OneNoteElement(
                    self.extract_title(element),
                    self.extract_title(element),
                    element['id'],
                    self.extract_title(element['parentNotebook']),
                    None,
                    "icons/section-group.png",
                    "file",
                    types.OneNoteType.SECTION_GROUP,
                    self.extract_parentUid(element),
                    element['lastModifiedDateTime']
                )
    
    def map_element_to_section(self, element):
        return types.OneNoteElement(
                    self.extract_title(element),
                    self.extract_title(element),
                    element['id'],
                    self.extract_title(element['parentNotebook']),
                    None,
                    "icons/section.png",
                    "file",
                    types.OneNoteType.SECTION,
                    self.extract_parentUid(element),
                    element['lastModifiedDateTime']
                )
    
    def map_element_to_page(self, element):
        return types.OneNoteElement(
                    self.extract_title(element),
                    self.extract_title(element),
                    element['id'],
                    self.extract_title(element['parentSection']),
                    self.extract_link(element),
                    "icons/page.png",
                    "file",
                    types.OneNoteType.PAGE,
                    self.extract_parentUid(element),
                    element['lastModifiedDateTime']
                )

    def update_modified_element(self, elementOnenoteType, element):
        elementMapped = self.map_element(elementOnenoteType, element)
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

    def extract_parentUid(self, element):
        if 'parentSection' in element and element['parentSection'] != None:
            return element['parentSection']['id']

        if 'parentSectionGroup' in element and element['parentSectionGroup'] != None:
            return element['parentSectionGroup']['id']
        
        if 'parentNotebook' in element and element['parentNotebook'] != None:
            return element['parentNotebook']['id']
        

        raise RuntimeError("Cannot retrieve title of element: " + element ["self"]) 
   
    def extract_link(self, element):
        if not 'links' in element:
            return None

        if 'href' in element['links']['oneNoteClientUrl']:
            return element['links']['oneNoteClientUrl']['href']
        
        return element['links']['oneNoteClientUrl']

class TooManyRequestsRetryMiddleware(RetryMiddleware):

    def __init__(self, crawler):
        super(TooManyRequestsRetryMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.last429Error = self.current_time()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def current_time(self):
        return datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S.%f%z')

    def process_response(self, request, response, spider):
        if request.meta.get('dont_retry', False):
            return response
        elif response.status == 429:
            secondsSinceLast429Error = (self.current_time() - self.last429Error).total_seconds()

            self.crawler.engine.pause()
            if secondsSinceLast429Error > 70:
                time.sleep(60)  # Sleep 60 seconds.
            else:
                time.sleep(60 * 60)  # Sleep 1 hour.
            self.crawler.engine.unpause()

            reason = response_status_message(response.status)
            self.last429Error = self.current_time()
            return self._retry(request, reason, spider) or response
        elif response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        return response
