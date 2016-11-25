import scrapy
import logging
import datetime

from NewsCrawler.items import DailyStarItem
from newspaper import Article

from NewsCrawler.Helpers.CustomNERTagger import Tagger
from NewsCrawler.credentials_and_configs.stanford_ner_path import STANFORD_CLASSIFIER_PATH, STANFORD_NER_PATH

from scrapy.exceptions import CloseSpider

# Using elasticsearch
from elasticsearch import Elasticsearch

es = Elasticsearch()

class DailyStarSpider(scrapy.Spider):
    name = 'dailystar'

    def increase_day_by_one(self, d):
        d += datetime.timedelta(days=1)
        return d

    def __init__(self, start_date='01-01-2016', end_date='02-01-2016', delimiter='-'):
        self.start_day, self.start_month, self.start_year = [int(i) for i in start_date.split(delimiter)]
        self.end_day, self.end_month, self.end_year = [int(i) for i in end_date.split(delimiter)]

        #Datetime Format 
        # Example: '26-11-2016 12:36 AM'
        self.datetime_format = "%d-%m-%Y %I:%M %p"


    def start_requests(self):
        # Saving a copy of start date as begin date
        self.begin_date = datetime.date(self.start_year, self.start_month, self.start_day)
        
        # Will be updated as next date 
        self.start_date = datetime.date(self.start_year , self.start_month , self.start_day)
        self.end_date = datetime.date(self.end_year, self.end_month, self.end_day)

        self.url = 'http://www.thedailystar.net/newspaper?' + self.start_date.__str__()

        # Creating the Tagger object
        self.tagger = Tagger(classifier_path=STANFORD_CLASSIFIER_PATH, ner_path=STANFORD_NER_PATH)

        self.id = 0

        yield scrapy.Request(self.url, self.parse)

    def parse(self, response):
        self.main_url = 'http://www.thedailystar.net'
        self.baseurl = 'http://www.thedailystar.net/newspaper?date='


        self.main_selection = response.xpath("//h5")

        for sel in self.main_selection:
            news_item = DailyStarItem()
            news_item['newspaper_name'] = 'The Daily Star'
            news_item['newspaper_section'] = sel.xpath("../../../../../../../div[1]/h2/text()").extract_first()
            news_item['url'] = self.main_url + sel.xpath("a/@href").extract_first()
            news_item['title'] = sel.xpath("a/text()").extract_first().strip()

            request = scrapy.Request(news_item['url'], callback=self.parseNews)

            request.meta['news_item'] = news_item
            yield request

        self.start_date = self.increase_day_by_one(self.start_date)

        self.next_page = self.baseurl + self.start_date.__str__()

        # Crawling termination condition
        if self.start_date > self.end_date:
            raise CloseSpider('Done scraping from '+ self.begin_date.__str__() + ' upto ' +  self.end_date.__str__())

        try:
            self.logger.info("TRYING")
            yield scrapy.Request(self.next_page, callback=self.parse)
        except:
            self.logger.info("PROBLEM")
            self.start_date = self.increase_day_by_one(self.start_date)
            self.next_page = self.baseurl + self.start_date.__str__()
            yield scrapy.Request(self.next_page, callback=self.parse)

    

    def parseNews(self, response):

        self.id += 1
        
        news_item = response.meta['news_item']
        
        #Getting the Article
        paragraphs = response.xpath("//div[@class='field-body view-mode-teaser']//p/text()").extract()
        news_item['article'] = ''.join([para.strip() for para in paragraphs])

        # Getting bottom tag line
        news_item['bottom_tag_line'] = response.xpath("//h2[@class='h5 margin-bottom-zero']/em/text()").extract_first()
        # Getting top tag line
        news_item['top_tag_line'] = response.xpath("//h4[@class='uppercase']/text()").extract_first()
        
        # Getting the published time
        news_item = self.getPublishedTime(news_item, response)

        # Getting the image source and captions
        news_item['images'] = response.xpath("//div[@class='caption']/../img/@src").extract()
        news_item['image_captions'] = response.xpath("//div[@class='caption']/text()").extract()

        # Get the breadcrumb
        news_item['breadcrumb'] = response.xpath("//div[@class='breadcrumb']//span[@itemprop='name']/text()").extract()

        # Get reporter
        news_item['reporter'] = response.xpath("//div[@class='author-name margin-bottom-big']/span/a/text()").extract_first()


        # Get the summary and keywords using 'newspaper' package
        # [WARNING : This section slows down the overall scraping process]
        article = Article(url=news_item['url'])
        article.download()
        article.parse()
        article.nlp()
        news_item['generated_summary'] = article.summary
        news_item['generated_keywords'] = article.keywords


        # Tagging the article
        try:
            self.tagger.entity_group(news_item['article'])
        except:
            print "NER Tagger exception"
        # Getting the ner tags
        news_item['ner_person'] = self.tagger.PERSON
        news_item['ner_organization'] = self.tagger.ORGANIZATION
        news_item['ner_time'] = self.tagger.TIME
        news_item['ner_percent'] = self.tagger.PERCENT
        news_item['ner_money'] = self.tagger.MONEY
        news_item['ner_location'] = self.tagger.LOCATION

        # Contains all occurances
        news_item['ner_list_person'] = self.tagger.LIST_PERSON
        news_item['ner_list_organization'] = self.tagger.LIST_ORGANIZATION
        news_item['ner_list_time'] = self.tagger.LIST_TIME
        news_item['ner_list_money'] = self.tagger.LIST_MONEY
        news_item['ner_list_location'] = self.tagger.LIST_LOCATION
        news_item['ner_list_percent'] = self.tagger.LIST_PERCENT

        # ML tags
        news_item['ml_tags'] = None

        news_item['sentiment'] = self.tagger.get_indico_sentiment(news_item['article'])

        doc = {
            "news_url" : news_item['url'],
            "reporter" : news_item['reporter'],
            "published" : news_item['published_date'],
            "title" : news_item['title'],
            "content" : news_item['article'],
            "top_tagline" : news_item['top_tag_line'],
            "bottom_tagline" : news_item['bottom_tag_line'],
            "images" : news_item['images'],
            "image_captions" : news_item['image_captions'],
            "breadcrumb" : news_item['breadcrumb'],
            "sentiment" : news_item['sentiment'],
            "ml_tags" : None,
            "section" : news_item['newspaper_section'],
            
            "ner_person" : news_item['ner_person'],
            "ner_organization" : news_item['ner_organization'],
            "ner_money" : news_item['ner_money'],
            "ner_time" : news_item['ner_time'],
            "ner_location" : news_item['ner_location'],
            "ner_percent" : news_item['ner_percent'],

            "ner_list_person" : news_item['ner_list_person'],
            "ner_list_organization" : news_item['ner_list_organization'],
            "ner_list_money" : news_item['ner_list_money'],
            "ner_list_time" : news_item['ner_list_time'],
            "ner_list_location" : news_item['ner_list_location'],
            "ner_list_percent" : news_item['ner_list_percent'],

            "generated_keywords" : news_item['generated_keywords'],
            "generated_summary" : news_item['generated_summary'],
            "timestamp" : datetime.datetime.now().strftime(self.datetime_format),
        }

        res = es.index(index="newspaper_index", doc_type='news', id=self.id, body=doc)

        # Data can be collected as csv also 
        yield doc

    def getPublishedTime(self, news_item, response):
        dt = response.xpath("//meta[@itemprop='datePublished']/@content").extract_first()
        converted_dt = datetime.datetime.strptime( dt.split("+")[0], "%Y-%m-%dT%H:%M:%S")
        formatted_dt = converted_dt.strftime("%Y-%m-%d %I:%M %p")
        news_item['published_date'] = formatted_dt
        return news_item
        