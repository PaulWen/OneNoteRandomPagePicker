# -*- coding: utf-8 -*-
import os

import scrapy

import auth_token_request as req
import onenote_types as types


class OneNotePageContentSpider(scrapy.Spider):
    """
    This spider scrapes all the content of the pages and stores them it html files.
    """

    def __init__(self, modified_pages_uids: set(), download_folder_path: str,
                 alfred_data_dictionary: {str, types.OneNoteElement}):
        self.name = 'OneNotePageContentSpider'
        self.allowed_domains = ['graph.microsoft.com']
        self.alfred_data_dictionary = alfred_data_dictionary
        self.modified_pages_uids = modified_pages_uids
        self.downloadFolderPath = download_folder_path

    def start_requests(self):
        for modifiedPageUid in self.modified_pages_uids:
            yield req.AuthTokenRequest(meta={types.PAGE_UID_KEY: modifiedPageUid},
                                       url='https://graph.microsoft.com/v1.0/users/me/onenote/pages/' + modifiedPageUid + '/content',
                                       method="GET", callback=self.parse_page_content)

    def parse_page_content(self, response):
        """
        Is used to parse page content and store it in a file.
        """
        pageUid = response.meta[types.PAGE_UID_KEY]
        pageContent = response.text
        pageContent = self.post_process_page_content(pageUid, pageContent)

        self.store_page_content_in_file(pageUid, pageContent)

    def post_process_page_content(self, pageUid, pageContent):
        """
        This function removes the head-tag so that the infromation eisting in head is also
        indexed by spotlight. Further, it adds the subtitle of the OneNote element to the
        HTML file so that the file can also be found based on the names of its parent elements.
        """
        pageContent = pageContent.replace("<head>", "")
        pageContent = pageContent.replace("</head>", self.alfred_data_dictionary[pageUid].subtitle)

        return pageContent

    def store_page_content_in_file(self, pageUid, data):
        """
        Stores content in an HTML file
        """
        file_path = self.downloadFolderPath + pageUid + ".html"

        if not os.path.isdir(self.downloadFolderPath):
            os.mkdir(self.downloadFolderPath)

        with open(file_path, mode='w') as file:
            file.write(data)
