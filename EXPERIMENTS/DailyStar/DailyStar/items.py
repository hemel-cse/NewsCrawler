# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy import Item, Field


class DailyStarItem(Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    category = Field()
    newspaper_section = Field()
    reporter = Field()
    last_updated = Field()
    published_date = Field()
    article = Field()
    shared = Field()
    comment_count = Field()
    title = Field()
    url = Field()
    breadcrumb = Field()
    images = Field()
    top_tag_line = Field()
    bottom_tag_line = Field()