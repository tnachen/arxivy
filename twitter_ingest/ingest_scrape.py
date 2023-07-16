import sys
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
from selenium.webdriver.common.keys import Keys
import requests

@dataclass
class Tweet:
    text: str
    profile_image_url: str
    embedded_image_url: Optional[str]
    paper_url: str
    user: str
    views: int

def resolve_url(base_url):
    r = requests.get(base_url)
    return r.url


def parse_views(view_str: str) -> int:
    view_str = view_str.replace(",", "")
    if view_str.endswith("K"):
        # Replace decimal and append 00
        view_str = view_str.replace(".", "")
        view_str = view_str[0:-1] + "00"

    return int(view_str)

def parse_tweet(element: WebElement, source: str) -> Optional[Tweet]:
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
        return None

    views = parse_views(lines[-1])

    return Tweet(text=element.text,
                 user=user,
                 views=views,
                 paper_url=paper_url,
                 profile_image_url=profile_image,
                 embedded_image_url=embedded_image)


def login(driver: Chrome, username: str, password: str) -> None:
    spans = driver.find_elements(By.TAG_NAME, "span")
    required_login = False
    for span in spans:
        if "Sign in to Twitter" in span.text:
            required_login = True        
    
    if not required_login:
        return
    
    login_box = driver.find_element(By.TAG_NAME, "input")
    login_box.send_keys(username)
    actions = ActionChains(driver)
    actions.send_keys(Keys.ENTER).perform()
    
    sleep(3)
    
    driver.switch_to.active_element.send_keys(password)
    actions = ActionChains(driver)
    actions.send_keys(Keys.ENTER).perform()

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

                tweet = parse_tweet(article, source)
                if tweet:
                    tweets.append(tweet)
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
        print(t.views)
        print()

def _main() -> None:
    """Main driver"""
    options = webdriver.ChromeOptions()
    driver = Chrome(options=options, service=Service(ChromeDriverManager().install()))
    driver.maximize_window()

    date = date_str()

    arxiv_links = [
        f"https://twitter.com/search?q=llms%20filter%3Alinks%20since%3A{date}%20&src=typed_query&f=top",
        f"https://twitter.com/search?q=llm%20since%3A{date}%20filter%3Alinks&src=typed_query&f=top",
    ]

    # Crawl arxiv papers from Twitter
    driver.get(arxiv_links[1])
    sleep(5)

    username = sys.argv[1]
    password = sys.argv[2]

    login(driver=driver, username=username, password=password)

    for arxiv_link in arxiv_links:
        driver.get(arxiv_link)
        # Sleep for tweet page to load
        sleep(10)

        arxiv_tweets = crawl_tweets(driver, "arxiv")
        print_tweets(arxiv_tweets)
    
    return

    # Crawl huggingface papers from Twitter
    driver.get(f"https://twitter.com/search?q=huggingface.co%2Fpapers%20filter%3Alinks%20since%3A{date}&src=typed_query&f=top")
    sleep(5)
    hf_tweets = crawl_tweets(driver, "huggingface.co")
    print_tweets(hf_tweets)

    driver.quit()

if __name__ == "__main__":
    _main()
