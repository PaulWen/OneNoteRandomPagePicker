# -*- coding: utf-8 -*-
import json

import scrapy

import onenote_types as types

'''
This spider loads all notebooks.
'''
class OneNoteSectionGroupSpider(scrapy.Spider):
    
    def __init__(self, accessToken, sectionGroups: [types.OneNoteElement]):
        self.name = 'OneNoteSectionGroupSpider'
        self.allowed_domains = ['graph.microsoft.com']
        self.accessToken = accessToken
        self.sectionGroups = sectionGroups

    def start_requests(self):
        yield scrapy.Request(url='https://graph.microsoft.com/v1.0/me/onenote/sectiongroups', method="GET",
                             headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_section_groups)

    def parse_section_groups(self, response):
        sectionGroups = json.loads(response.text)["value"]

        for sectionGroup in sectionGroups:
           self.sectionGroups.append(self.map_element_to_section_group(sectionGroup))

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
                    self.extract_parent(element)
                )

    def extract_title(self, element):
        if 'displayName' in element:
            return element['displayName']
        
        if 'title' in element:
            return element['title']

        raise RuntimeError("Cannot retrieve title of element: " + element ["self"]) 
    
    def extract_parent(self, element):
        if 'parentSectionGroup' in element and element['parentSectionGroup'] != None:
            return element['parentSectionGroup']['id']
        
        if 'parentNotebook' in element and element['parentNotebook'] != None:
            return element['parentNotebook']['id']

        raise RuntimeError("Cannot retrieve title of element: " + element ["self"]) 
   
    def extract_link(self, element):
        if 'href' in element['links']['oneNoteClientUrl']:
            return element['links']['oneNoteClientUrl']['href']
        
        return element['links']['oneNoteClientUrl'] 
