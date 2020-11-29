# -*- coding: utf-8 -*-
import json

import scrapy


class OneNotePageSpider(scrapy.Spider):
    name = 'OneNotePage'
    allowed_domains = ['graph.microsoft.com']
    accessToken=''

    def __init__(self, accessToken):
        self.accessToken = accessToken
    
    def start_requests(self):
        yield scrapy.Request(url='https://graph.microsoft.com/v1.0/me/onenote/sections',  method="GET", headers={"Authorization": "Bearer " + self.accessToken})

    def parse(self, response):
        sections = json.loads(response.text)
        yield scrapy.Request(url=sections["value"][0]["pagesUrl"], method="GET", headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_pages)
        # for section in sections["value"]:
        #     yield scrapy.Request(url=section["pagesUrl"], method="GET", headers={"Authorization": "Bearer " + self.accessToken}, callback=self.parse_pages)

    def parse_pages(self, response):
        pages = json.loads(response.text)

        for page in pages["value"]:
            yield {
                'pageName': page["title"],
                'pageOneNoteClientUrl': page["links"]["oneNoteClientUrl"]["href"]
            }
