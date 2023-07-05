from datetime import datetime

from time import sleep
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement
from dataclasses import dataclass
from urlextract import URLExtract
import requests

@dataclass
class Tweet:
    text: str
    profile_image_url: str
    embedded_image_url: Optional[str]
    paper_url: str
    user: str
    views: str

def resolve_url(base_url):
    r = requests.get(base_url)
    return r.url

def parse_tweet(element: WebElement, source: str) -> Tweet:
    lines = element.text.split("\n")
    user = lines[1][1:] # remove @
    images = element.find_elements(By.TAG_NAME, "img")
    profile_image = images[0].get_attribute("src")
    embedded_image = None
    if len(images) > 1:
        embedded_image = images[1].get_attribute("src")        

    paper_url = None
    
    for u in element.find_elements(By.TAG_NAME, "a"):
        url = u.get_attribute("href")
        if "t.co" in url:
            url = resolve_url(url)

        if source in url:            
            paper_url = url
            break

    if not paper_url:
        raise Exception("Paper url not found in tweet: " + element.text)

    return Tweet(text=element.text,
                 user=user,
                 views=lines[-1],
                 paper_url=paper_url,
                 profile_image_url=profile_image,
                 embedded_image_url=embedded_image)


def login(driver):
    login = driver.find_by_ai("twitter_login")
    #login_next_btn = driver.find_by_ai("twitter_login_next_btn")
    sleep(3)
    #password = driver.find_by_ai("twitter_login_password")
    sleep(10)

def date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def crawl_tweets(driver: Chrome, source: str) -> List[Tweet]:
    action = ActionChains(driver)
    tweets: List[Tweet] = []
    ids = set()

    def scroll_and_crawl():
        articles = driver.find_elements(By.TAG_NAME, "article")
        tweet_added = False
        for article in articles:
            if article.id not in ids:
                if article.text.endswith("Promoted"):
                    # Skip promoted tweets
                    continue

                tweets.append(parse_tweet(article, source))
                ids.add(article.id)
                tweet_added = True

        if tweet_added:
            action.move_to_element(articles[-1]).perform()
            scroll_and_crawl()

    scroll_and_crawl()

    return tweets


def print_tweets(tweets: List[Tweet]) -> None:
    for t in tweets:
        print(t.user)
        print(t.text)        
        print(t.paper_url)
        print()

def _main() -> None:
    """Main driver"""
    options = webdriver.ChromeOptions()
    driver = Chrome(options=options, service=Service(ChromeDriverManager().install()))
    driver.maximize_window()

    #date = date_str()
    date = "2023-07-10"

    # Crawl arxiv papers from Twitter
    driver.get(f"https://twitter.com/search?q=arxiv.org%20llms%20filter%3Alinks%20since%3A{date}%20&src=typed_query&f=top")
    sleep(5)
    arxiv_tweets = crawl_tweets(driver, "arxiv")
    print_tweets(arxiv_tweets)

    # Crawl huggingface papers from Twitter
    driver.get(f"https://twitter.com/search?q=huggingface.co%2Fpapers%20filter%3Alinks%20since%3A{date}&src=typed_query&f=top")
    sleep(5)
    hf_tweets = crawl_tweets(driver, "huggingface.co")
    print_tweets(hf_tweets)

    driver.quit()

if __name__ == "__main__":
    _main()
