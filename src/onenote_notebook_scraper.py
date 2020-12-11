# -*- coding: utf-8 -*-
import json

import scrapy

import onenote_types as types

'''
This spider loads all notebooks.
'''
class OneNoteNotebookSpider(scrapy.Spider):
    
    def __init__(self, accessToken, notebooks: [types.OneNoteElement]):
        self.name = 'OneNoteNotebookSpider'
        self.allowed_domains = ['graph.microsoft.com']
        self.accessToken = accessToken
        self.notebooks = notebooks

    def start_requests(self):
        yield scrapy.Request(url='https://graph.microsoft.com/v1.0/me/onenote/notebooks', method="GET",
                             headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_notebooks)

    def parse_notebooks(self, response):
        notebooks = json.loads(response.text)["value"]

        for notebook in notebooks:
           self.notebooks.append(self.map_element_to_notebook(notebook))

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
                    types.NOTEBOOKS_KEY
        )

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
