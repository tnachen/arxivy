import logging
from urllib.parse import urljoin
from dotenv import load_dotenv
import os
import sys
from datetime import datetime, timedelta

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

import libsql_client

## CONSTANTS

# Maximum tweets to crawl each page
MAX_TWEETS = 50

logger = logging.getLogger(__name__)
stdout = logging.StreamHandler(stream=sys.stdout)
stdout.setLevel(logging.DEBUG)
logger.addHandler(stdout)
logger.setLevel(logging.DEBUG)

@dataclass
class Tweet:
    text: str
    profile_image_url: str
    embedded_image_url: Optional[str]
    paper_url: str
    user: str
    source: str
    views: int


def write_papers_to_db(tweets: List[Tweet], url: str, auth_token: str) -> None:
    with libsql_client.create_client_sync(url=url, auth_token=auth_token) as client:
        for tweet in tweets:
            client.execute(
                "INSERT OR IGNORE INTO papers VALUES (:user, :link, :profile_image, :views, :source, :created_at)",
                {
                    "user": tweet.user,
                    "link": tweet.paper_url,
                    "profile_image": tweet.profile_image_url,
                    "views": tweet.views,
                    "source": tweet.source,
                    "created_at": datetime.now()
                })


def resolve_url(base_url):
    try:
        r = requests.get(base_url)
    except Exception as e:
        logger.warn(f"Cannot connect to {base_url}: {e}")

        # Return the url if we cannot connect to it
        return base_url

    return r.url


def go_link(driver: Chrome, url: str, sleep_time: int):
    logger.info(f"Navigating to {url} with sleep {sleep_time}")
    driver.get(url)
    sleep(sleep_time)


def parse_views(lines: List[str], list_view: bool) -> int:
    if list_view:
        # Last line of the list tweet view is the view count
        view_str = lines[-1]
    else:
        # In the per tweet status view, need to find the views line
        found_views = False
        for line in reversed(lines):
            if found_views:
                view_str = line
                break

            if line.strip() == "Views":
                found_views = True

    view_str = view_str.replace(",", "")
    if view_str.endswith("K"):
        # Replace decimal and append 00
        view_str = view_str.replace(".", "")
        view_str = view_str[0:-1] + "00"

    if view_str.endswith("M"):
        # Replace decimal and append 00
        view_str = view_str.replace(".", "")
        view_str = view_str[0:-1] + "00000"

    return int(view_str)


def parse_tweet(element: WebElement, sources: List[str], list_view: bool) -> Optional[Tweet]:
    logger.debug("Parsing tweet text: " + element.text)
    lines = element.text.split("\n")
    user = lines[1][1:]  # remove @
    images = element.find_elements(By.TAG_NAME, "img")
    profile_image = images[0].get_attribute("src")
    embedded_image = None
    if len(images) > 1:
        embedded_image = images[1].get_attribute("src")

    paper_url = None
    found_source = None

    for u in element.find_elements(By.TAG_NAME, "a"):
        url = u.get_attribute("href")
        if "t.co" in url:
            url = resolve_url(url)

        for source in sources:
            if source in url:
                paper_url = url
                found_source = source
                break

    if not paper_url:
        return None

    views = parse_views(lines, list_view)

    return Tweet(text=element.text,
                 user=user,
                 views=views,
                 paper_url=paper_url,
                 profile_image_url=profile_image,
                 source=found_source,
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
    sleep(3)


def yesterday() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def detect_show_more(article: WebElement) -> Optional[str]:
    """
    Finds if there is a "Show More" link in the tweet, which can cause us
    not able to crawl the tweet properly.
    In this case, get the tweet link so we can crawl those later.
    """
    spans = article.find_elements(By.TAG_NAME, "span")
    is_show_more = False
    for span in spans:
        if span.text == "Show more":
            is_show_more = True
            break

    link = None
    if is_show_more:
        logger.debug(f"Attempting to find link in show more tweet")
        # Find the status link since this is a Tweet with "show more"
        time_element = article.find_element(By.TAG_NAME, "time")
        link_element = time_element.find_element(By.XPATH, "parent::*")
        link = link_element.get_attribute("href")
        logger.debug(f"Found show more tweet with link {link}")

    return link


def crawl_tweets(driver: Chrome, sources: List[str]) -> List[Tweet]:
    action = ActionChains(driver)
    tweets: List[Tweet] = []
    show_more_links = set()
    ids = set()

    def scroll_and_crawl(count: int):
        last_id = None

        articles = driver.find_elements(By.TAG_NAME, "article")
        for article in articles:
            if article.id not in ids:
                if article.text.endswith("Promoted"):
                    # Skip promoted tweets
                    continue

                show_more_link = detect_show_more(article)
                if show_more_link:
                    show_more_links.add(show_more_link)
                    # Skip show more tweets, as we'll crawl them later
                    continue

                count += 1

                tweet = parse_tweet(article, sources, True)
                if tweet:
                    tweets.append(tweet)
                    ids.add(article.id)

        if last_id != articles[-1].id:
            action.move_to_element(articles[-1]).perform()
            last_id = articles[-1].id
            if count < MAX_TWEETS:
                scroll_and_crawl(count)

    scroll_and_crawl(0)

    # Browse through all the show more tweets individually
    for show_more_link in show_more_links:
        go_link(driver, urljoin("https://twitter.com", show_more_link), 5)
        article = driver.find_element(By.TAG_NAME, "article")
        tweet = parse_tweet(article, sources, False)
        if tweet:
            tweets.append(tweet)

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
    options.add_argument("--user-data-dir=/tmp/ingest_profile")
    driver = Chrome(options=options, service=Service(
        ChromeDriverManager().install()))
    driver.maximize_window()

    date = yesterday()

    arxiv_links = [
        f"https://twitter.com/search?q=llms%20filter%3Alinks%20since%3A{date}%20&src=typed_query&f=top",
        f"https://twitter.com/search?q=llm%20since%3A{date}%20filter%3Alinks&src=typed_query&f=top",
        f"https://twitter.com/search?q=gpt4%20filter%3Alinks%20since%3A{date}%20&src=typed_query&f=top"
    ]

    # Crawl arxiv papers from Twitter
    go_link(driver, arxiv_links[0], 5)

    username = sys.argv[1]
    password = sys.argv[2]

    login(driver=driver, username=username, password=password)

    for arxiv_link in arxiv_links:
        go_link(driver, arxiv_link, 10)

        arxiv_tweets = crawl_tweets(
            driver, ["arxiv", "ai.meta.com/research/publications"])
        print_tweets(arxiv_tweets)
        write_papers_to_db(arxiv_tweets, os.getenv(
            "TURSO_URL"), os.getenv("TURSO_AUTH_TOKEN"))

    # Crawl huggingface papers from Twitter
    driver.get(
        f"https://twitter.com/search?q=huggingface.co%2Fpapers%20filter%3Alinks%20since%3A{date}&src=typed_query&f=top")
    sleep(5)
    hf_tweets = crawl_tweets(driver, "huggingface.co")
    print_tweets(hf_tweets)
    write_papers_to_db(hf_tweets, os.getenv(
            "TURSO_URL"), os.getenv("TURSO_AUTH_TOKEN"))

    driver.quit()


if __name__ == "__main__":
    load_dotenv()
    _main()
