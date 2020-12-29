# -*- coding: utf-8 -*-
import os

import scrapy

import auth_token_request as req
import onenote_types as types


class OneNotePageContentSpider(scrapy.Spider):
    """
    This spider scrapes all the content of the pages and stores them it html files.
    """

    def __init__(self, modified_pages_uids: set(), download_folder_path: str):
        self.name = 'OneNotePageContentSpider'
        self.allowed_domains = ['graph.microsoft.com']
        self.modifiedPagesUids = modified_pages_uids
        self.downloadFolderPath = download_folder_path

    def start_requests(self):
        for modifiedPageUid in self.modifiedPagesUids:
            yield req.AuthTokenRequest(meta={types.PAGE_UID_KEY: modifiedPageUid},
                                       url='https://graph.microsoft.com/v1.0/users/me/onenote/pages/' + modifiedPageUid + '/content',
                                       method="GET", callback=self.parse_page_content)

    def parse_page_content(self, response):
        """
        Is used to parse page content and store it in a file.
        """
        pageUid = response.meta[types.PAGE_UID_KEY]
        pageContent = response.text

        self.store_page_content_in_file(pageUid, pageContent)

    def store_page_content_in_file(self, pageUid, data):
        """
        Stores content in an HTML file
        """
        file_path = self.downloadFolderPath + pageUid + ".html"

        if not os.path.isdir(self.downloadFolderPath):
            os.mkdir(self.downloadFolderPath)

        with open(file_path, mode='w') as file:
            file.write(data)
