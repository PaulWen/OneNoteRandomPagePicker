# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime

import scrapy

import auth_token_request as req
import onenote_types as types


class OneNoteSyncSpider(scrapy.Spider):
    """
    This spider loads all types of onenote elements (e.g. notebook, section, section group,
    page) and syncs them with the current set of onenote elements. If onenote elements already
    exist, this spider will only load those elements again that changed since the last sync.
    """

    def __init__(self, alfred_data_dictionary: {str, types.OneNoteElement}, lastSyncDate, pagesModified: set(),
                 pagesDeleted: set()):
        self.name = 'OneNoteSyncSpider'
        self.allowed_domains = ['graph.microsoft.com']
        self.lastSyncDate = lastSyncDate if type(lastSyncDate) is datetime else datetime.strptime(
            '2000-01-01T00:00:00.000Z', "%Y-%m-%dT%H:%M:%S.%f%z")
        self.alfred_data_dictionary = alfred_data_dictionary
        self.alfred_parent_child_dictionary: {str, (str)} = self.genarateParentChildDictionaryFromDictionary(
            self.alfred_data_dictionary)
        self.pagesModified = pagesModified
        self.pagesDeleted = pagesDeleted
        self.baseUrl = "https://graph.microsoft.com"

    def start_requests(self):
        yield req.AuthTokenRequest(meta={types.ONENOTE_TYPE_KEY: types.OneNoteType.NOTEBOOK},
                                   url=self.baseUrl + '/v1.0/me/onenote/notebooks', method="GET",
                                   callback=self.parse_onenote_elements)

        yield req.AuthTokenRequest(meta={types.ONENOTE_TYPE_KEY: types.OneNoteType.SECTION_GROUP},
                                   url=self.baseUrl + '/v1.0/me/onenote/sectiongroups', method="GET",
                                   callback=self.parse_onenote_elements)

        yield req.AuthTokenRequest(meta={types.ONENOTE_TYPE_KEY: types.OneNoteType.SECTION},
                                   url=self.baseUrl + '/v1.0/me/onenote/sections', method="GET",
                                   callback=self.parse_onenote_elements)

    def closed(self, reason):
        alfred_parent_child_dictionary = self.genarateParentChildDictionaryFromDictionary(self.alfred_data_dictionary)

        self.add_page_urls_to_elements_without_url(self.alfred_data_dictionary,
                                                   alfred_parent_child_dictionary)

        self.add_subtitle_and_match_string_to_elements(self.alfred_data_dictionary)

    def parse_onenote_elements(self, response):
        """
        Is used to parse one type of onenote elements: notebook, section, section
        group. The function syncs the data with the current set of data.
        """

        onenoteType = response.meta[types.ONENOTE_TYPE_KEY]
        elements = json.loads(response.text)["value"]

        deletedElementsUids = self.identify_deleted_elements_uids(onenoteType, elements)
        self.delete_recursively(deletedElementsUids)

        modifiedElements = self.identify_modified_elements(elements)

        for element in modifiedElements:
            self.update_modified_element(onenoteType, element)

            if onenoteType == types.OneNoteType.SECTION:
                yield self.scrape_pages(element)

    def parse_onenote_pages(self, response):
        """
        Is used to parse a list of onenote pages. The function syncs the data with the current set of data.
        """
        sectionUid = response.meta[types.PARENT_UID_KEY]
        pagesOfSameSectionAlreadyLoaded = response.meta[types.PAGES_OF_SAME_SECTION_ALREADY_LOADED]
        pages = json.loads(response.text)["value"]

        modifiedPages = self.identify_modified_elements(pages)

        for page in modifiedPages:
            self.pagesModified.add(page['id'])
            self.update_modified_element(types.OneNoteType.PAGE, page)

        if "@odata.nextLink" in json.loads(response.text):
            yield req.AuthTokenRequest(meta={types.PARENT_UID_KEY: sectionUid,
                                             types.PAGES_OF_SAME_SECTION_ALREADY_LOADED: pagesOfSameSectionAlreadyLoaded + pages},
                                       url=json.loads(response.text)["@odata.nextLink"], method="GET",
                                       callback=self.parse_onenote_pages)

        if "@odata.nextLink" not in json.loads(response.text):
            deletedPagesUids = self.identify_deleted_pages_uids(sectionUid, pagesOfSameSectionAlreadyLoaded + pages)
            self.delete_recursively(deletedPagesUids)

    def identify_deleted_pages_uids(self, sectionUid, pages):
        """
        This function detects all the deleted pages of a section.
        For this to work, it is expected that the list of pages includes all the pages
        the section currently has.
        """
        pagesUids = set()
        for page in pages:
            pagesUids.add(page["id"])

        pastChildrenUids = self.alfred_parent_child_dictionary[
            sectionUid] if sectionUid in self.alfred_parent_child_dictionary else set()

        deletedPages = pastChildrenUids - pagesUids

        return deletedPages

    def identify_deleted_elements_uids(self, onenoteType, elements):
        """
        This function detects all the deleted elements of the same type.
        For this to work, it is expacted that the list of peers includes all the peers
        the onenote type currently reviewed.

        This function is used to detected deleted notebooks section groups and sections.
        """
        elementUids = set()
        for element in elements:
            elementUids.add(element["id"])

        pastElementUids = set()
        for pastElement in self.alfred_data_dictionary.values():
            if pastElement.onenoteType == onenoteType:
                pastElementUids.add(pastElement.uid)

        deletedElements = pastElementUids - elementUids

        return deletedElements

    def identify_modified_elements(self, elements):
        """
        Identifies all the elements in the list of elements that need to be updated.
        It is decided based on the name of an element and its lastModifiedTimestamp if an
        element needs to be updated or not.
        """

        for element in elements:
            if self.is_element_archived(element):
                continue

            # do only scrape elements which have been updated since the last sync
            lastModified = self.parse_datetime(element["lastModifiedDateTime"])
            if lastModified < self.lastSyncDate:
                continue

            yield element

    def is_element_archived(self, element):
        """
        Do only scrape elements which do not include "(Archiv)" in their name and
        therefore are not yet archived.
        """

        if self.extract_title(element).find("(Archiv)") > -1:
            return True

        if "parentNotebook" in element and element['parentNotebook']['displayName'].find("(Archiv)") > -1:
            return True

        link = self.extract_link(element)
        if link != None and link.find("/One%20Note/Archiv/") > -1:
            return True

        return False

    def scrape_pages(self, parent):
        """
        Scrapes the pages of the passed in element.
        """

        if "pagesUrl" in parent:
            return req.AuthTokenRequest(
                meta={types.PARENT_UID_KEY: parent["id"], types.PAGES_OF_SAME_SECTION_ALREADY_LOADED: []},
                url=parent["pagesUrl"], method="GET",
                callback=self.parse_onenote_pages)

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
            element['lastModifiedDateTime'],
            None
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
            element['lastModifiedDateTime'],
            None
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
            element['lastModifiedDateTime'],
            None
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
            element['lastModifiedDateTime'],
            None
        )

    def update_modified_element(self, elementOnenoteType, element):
        elementMapped = self.map_element(elementOnenoteType, element)
        self.alfred_data_dictionary[elementMapped.uid] = elementMapped

    def delete_recursively(self, uids: [str]):
        for uid in uids:
            if uid in self.alfred_parent_child_dictionary:
                children = self.alfred_parent_child_dictionary[uid]
                self.delete_recursively(children)

            if uid in self.alfred_data_dictionary and self.alfred_data_dictionary[
                uid].onenoteType == types.OneNoteType.PAGE:
                self.pagesDeleted.add(uid)

            if uid in self.alfred_data_dictionary:
                del self.alfred_data_dictionary[uid]

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

        raise RuntimeError("Cannot retrieve title of element: " + element["self"])

    def extract_parentUid(self, element):
        if 'parentSection' in element and element['parentSection'] != None:
            return element['parentSection']['id']

        if 'parentSectionGroup' in element and element['parentSectionGroup'] != None:
            return element['parentSectionGroup']['id']

        if 'parentNotebook' in element and element['parentNotebook'] != None:
            return element['parentNotebook']['id']

        raise RuntimeError("Cannot retrieve title of element: " + element["self"])

    def extract_link(self, element):
        if not 'links' in element:
            return None

        if 'href' in element['links']['oneNoteClientUrl']:
            return element['links']['oneNoteClientUrl']['href']

        return element['links']['oneNoteClientUrl']

    def genarateParentChildDictionaryFromDictionary(self, alfredDataDictionary: {str, types.OneNoteElement}):
        alfredParentChildDictionary = {}

        for element in alfredDataDictionary:
            element = alfredDataDictionary[element]

            if element.parentUid == None:
                continue

            if element.parentUid not in alfredParentChildDictionary:
                alfredParentChildDictionary[element.parentUid] = set()

            alfredParentChildDictionary[element.parentUid].add(element.uid)

        return alfredParentChildDictionary

    def recursively_find_url_of_first_child_page(self, element: types.OneNoteElement, alfredDataDictionary,
                                                 alfredParentChildDictionary):
        if (element.onenoteType == types.OneNoteType.PAGE):
            return element.arg

        if (element.uid in alfredParentChildDictionary):
            childElement = alfredDataDictionary[list(alfredParentChildDictionary[element.uid])[0]]
            return self.recursively_find_url_of_first_child_page(childElement, alfredDataDictionary,
                                                                 alfredParentChildDictionary)

        return None

    def recursively_generate_subtitle(self, element: types.OneNoteElement, alfredDataDictionary):
        if (element.onenoteType == types.OneNoteType.NOTEBOOK):
            return element.title

        return self.recursively_generate_subtitle(alfredDataDictionary[element.parentUid],
                                                  alfredDataDictionary) + " > " + element.title

    def add_page_urls_to_elements_without_url(self, alfredDataDictionary,
                                              alfredParentChildDictionary):
        for uid in alfredDataDictionary.keys():
            element: types.OneNoteElement = alfredDataDictionary[uid]
            if (element.arg == None):
                pageUrl = self.recursively_find_url_of_first_child_page(element, alfredDataDictionary,
                                                                        alfredParentChildDictionary)

                if (pageUrl != None):
                    sectionUrl = re.sub(r'page-id=.*&', '', pageUrl)
                    element.arg = sectionUrl

    def add_subtitle_and_match_string_to_elements(self, alfredDataDictionary):
        for uid in alfredDataDictionary.keys():
            element: types.OneNoteElement = alfredDataDictionary[uid]

            if (element.onenoteType == types.OneNoteType.NOTEBOOK):
                element.subtitle = "Notebook"
                element.match = element.title
                continue

            subtitle = self.recursively_generate_subtitle(alfredDataDictionary[element.parentUid], alfredDataDictionary)
            subtitle = subtitle.replace("--", "")

            element.subtitle = subtitle
            element.match = subtitle + " > " + element.title
