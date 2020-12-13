# -*- coding: utf-8 -*-
import json
import os
import time
from datetime import datetime

import scrapy
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

import onenote_types as types

'''
This spider scrapes all the content of the pages and stores them it html files.
'''
class OneNotePageContentSpider(scrapy.Spider):

    def __init__(self, accessToken, modifiedPagesUids: set(), downloadFolderPath: str):
        self.name = 'OneNotePageContentSpider'
        self.allowed_domains = ['graph.microsoft.com']
        self.accessToken = accessToken
        self.modifiedPagesUids = modifiedPagesUids
        self.downloadFolderPath = downloadFolderPath

    def start_requests(self):
        for modifiedPageUid in self.modifiedPagesUids:
            yield scrapy.Request(meta={types.PAGE_UID_KEY: modifiedPageUid}, url='https://graph.microsoft.com/v1.0/users/me/onenote/pages/' + modifiedPageUid + '/content', method="GET",
                                headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_page_content)

    '''
    Is used to parse page content and store it in a file.
    '''
    def parse_page_content(self, response):
        pageUid = response.meta[types.PAGE_UID_KEY]
        pageContent = response.text

        self.store_page_content_in_file(pageUid, pageContent)

    '''
    Stores content in an HTML file
    '''
    def store_page_content_in_file(self, pageUid, data):
        file_path = self.downloadFolderPath + pageUid + ".html" 

        if not os.path.isdir(self.downloadFolderPath):
            os.mkdir(self.downloadFolderPath)

        with open(file_path, mode='w') as file:
            file.write(data)
