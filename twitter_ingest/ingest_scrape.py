import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import sleep
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import libsql_client
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from urllib3 import Retry
from webdriver_manager.chrome import ChromeDriverManager

from scrape_arxiv import ArxivPaper, scrape_arxiv_abstract, scrape_meta_abstract

## CONSTANTS

# Maximum tweets to crawl each page
MAX_TWEETS = 50

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
stdout = logging.StreamHandler(stream=sys.stdout)
stdout.setLevel(logging.DEBUG)
logger.addHandler(stdout)
logger.setLevel(logging.DEBUG)

class Driver:
    def __init__(self, driver: Chrome):
        self.driver = driver
        self.last_link = None

    def go_link(self, url: str, sleep_time: int):
        if self.last_link == url:
            return

        logger.info(f"Navigating to {url} with sleep {sleep_time}")
        self.driver.get(url)
        sleep(sleep_time)
        self.last_link = url

@dataclass
class Tweet:
    text: str
    profile_image_url: str
    embedded_image_url: Optional[str]
    paper_url: str
    user: str
    source: str
    views: int
    metadata: ArxivPaper


def write_papers_to_db(tweets: List[Tweet], url: str, auth_token: str, current_time: datetime) -> None:
    logger.info(f"Writing {len(tweets)} of papers to db")
    with libsql_client.create_client_sync(url=url, auth_token=auth_token) as client:
        for tweet in tweets:
            client.execute(
                "INSERT OR IGNORE INTO papers VALUES (:user, :profile_image, :link, :views, :source, :created_at, :title, :authors, :abstract)",
                {
                    "user": tweet.user,
                    "link": tweet.paper_url,
                    "profile_image": tweet.profile_image_url,
                    "views": tweet.views,
                    "source": tweet.source,
                    "abstract": tweet.metadata.abstract,
                    "title": tweet.metadata.title,
                    "authors": tweet.metadata.authors,
                    "created_at": current_time,
                })


def resolve_url(base_url):
    adapter = HTTPAdapter(max_retries=
                          Retry(total=2, backoff_factor=1, allowed_methods=None, status_forcelist=[429, 500, 502, 503, 504]))
    s = requests.Session()
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    try:
        r = s.get(base_url)
    except Exception as e:
        logger.warning(f"Cannot connect to {base_url}: {e}")

        # Return the url if we cannot connect to it
        return base_url

    return r.url


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

def has_enough_parts(url: str) -> bool:
    parsed = urlparse(url)
    return len(parsed.path[1:].split("/")) > 1


def parse_tweet(element: WebElement, sources: List[str], list_view: bool) -> Optional[Tweet]:
    text = element.text
    lines = text.split("\n")
    if len(lines) == 1:
        logger.warn("Found a unexpected tweet: " + text)
        return None

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
            if source in url and has_enough_parts(url):
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
                 embedded_image_url=embedded_image,
                 metadata=None)


def login(driver: Chrome, username: str, password: str) -> None:
    spans = driver.find_elements(By.TAG_NAME, "span")
    required_login = False
    for span in spans:
        if "Sign in to X" in span.text:
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


def date_ranges() -> (datetime, str, str):
    """
    Returns date range for twitter query and db time
    """
    t = datetime.now().date()
    y = (datetime.now() - timedelta(days=1)).date()
    return (datetime(year=y.year, month=y.month, day=y.day), y.strftime("%Y-%m-%d"), t.strftime("%Y-%m-%d"))


def normalize_arxiv_url(url: str) -> str:
    prefixes = [
         "https://huggingface.co/papers/",
         "https://arxiv.org/pdf/"
     ]

    for p in prefixes:
        if url.startswith(p):
            return "https://arxiv.org/abs/" + url[len(p):]

    return url

def fetch_paper_metadata(driver: Chrome, tweet: Tweet) -> None:
    """
    Populates the metadata object
    """
    url = normalize_arxiv_url(tweet.paper_url)
    if "ai.meta.com/research/publications" in url:
        metadata = scrape_meta_abstract(driver, url)
    else:
        metadata = scrape_arxiv_abstract(driver, url)
    tweet.metadata = metadata


def detect_show_more(article: WebElement) -> Optional[str]:
    """
    Finds if there is a "Show More" link in the tweet, which can cause us
    not able to crawl the tweet properly.
    In this case, get the tweet link so we can crawl those later.
    """
    spans = article.find_elements(By.TAG_NAME, "span")
    is_show_more = False
    for span in spans:
        if span.text.strip() == "Show more":
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


def crawl_tweets(driver: Driver, sources: List[str]) -> List[Tweet]:
    action = ActionChains(driver.driver)
    tweets: List[Tweet] = []
    show_more_links = set()
    ids = set()
    # We track the last batch of ids, so when we get the exact same ones we know we're at the end.
    last_batch_ids = set()

    def parse_article(article: WebElement, override_views: int = 0) -> bool:
        if article.id not in ids:
            ids.add(article.id)
            if article.text.endswith("Promoted"):
                # Skip promoted tweets
                return False

            try:
                show_more_link = detect_show_more(article)
            except StaleElementReferenceException as e:
                logger.warn("Detected stale element in finding show more, skipping")
                return False

            if show_more_link:
                logger.info(f"Adding article {article.id} to show more")
                show_more_links.add(show_more_link)
                # Skip show more tweets, as we'll crawl them later
                return False

            tweet = parse_tweet(article, sources, True)
            if tweet:
                tweet.views = max(tweet.views, override_views)
                tweets.append(tweet)

        return True

    def scroll_and_crawl(count: int, override_views: int = 0):
        articles = driver.driver.find_elements(By.TAG_NAME, "article")
        article_ids = set(a.id for a in articles)
        if last_batch_ids == article_ids:
            return

        last_batch_ids.clear()
        for a in article_ids: last_batch_ids.add(a)

        logger.debug(f"Found {len(articles)} articles in scroll, {article_ids}")

        for article in sorted(articles, key=lambda x: int(x.id.split("_")[-1])):
            logger.debug(f"Processing article {article.id}")
            if article.id not in ids:
                try:
                    action.move_to_element(article).perform()
                except StaleElementReferenceException:
                    logger.warn(f"Found stale element navigating to article {article.id}")
                    break

                if parse_article(article=article, override_views=override_views):
                    count += 1

        if count < MAX_TWEETS:
            scroll_and_crawl(count)

    scroll_and_crawl(0)

    logger.info(f"Processing {len(show_more_links)} show more tweets")
    # Browse through all the show more tweets individually
    show_more_links_copy = show_more_links.copy()
    for show_more_link in show_more_links_copy:
        driver.go_link(urljoin("https://twitter.com", show_more_link), 5)
        articles = driver.driver.find_elements(By.TAG_NAME, "article")
        views = parse_views(articles[0].text.split("\n"), False)
        scroll_and_crawl(0, views)

    for tweet in tweets:
        fetch_paper_metadata(driver, tweet)

    return tweets


def print_tweets(tweets: List[Tweet]) -> None:
    for t in tweets:
        logger.debug(t.user)
        logger.debug(t.text)
        logger.debug(t.paper_url)
        logger.debug(t.views)


def _main() -> None:
    """Main driver"""
    options = webdriver.ChromeOptions()
    options.add_argument("--user-data-dir=/tmp/ingest_profile")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--ignore-ssl-errors=true")
    options.add_argument("--ignore-certificate-errors")

    driver = Chrome(options=options, service=Service(
        ChromeDriverManager().install()))
    driver.maximize_window()
    driver = Driver(driver)

    #date, y_str, t_str = date_ranges()
    date, y_str, t_str = (datetime(year=2023, month=8, day=24), "2023-08-24", "2023-08-25")

    arxiv_links = [
        f"https://twitter.com/search?q=llms%20filter%3Alinks%20until%3A{t_str}%20since%3A{y_str}&src=typed_query&f=top",
        f"https://twitter.com/search?q=llm%20until%3A{t_str}%20since%3A{y_str}%20filter%3Alinks&src=typed_query&f=top",
        f"https://twitter.com/search?q=gpt4%20filter%3Alinks%20until%3A{t_str}%20since%3A{y_str}%20&src=typed_query&f=top"
    ]

    # Crawl arxiv papers from Twitter
    driver.go_link(arxiv_links[0], 5)

    username = sys.argv[1]
    password = sys.argv[2]

    login(driver=driver.driver, username=username, password=password)

    for arxiv_link in arxiv_links:
        driver.go_link(arxiv_link, 10)

        arxiv_tweets = crawl_tweets(
            driver, ["arxiv.org", "ai.meta.com/research/publications"])
        write_papers_to_db(arxiv_tweets, os.getenv(
            "TURSO_URL"), os.getenv("TURSO_AUTH_TOKEN"), date)

    # Crawl huggingface papers from Twitter
    driver.go_link(
        f"https://twitter.com/search?q=huggingface.co%2Fpapers%20filter%3Alinks%20since%3A{date}&src=typed_query&f=top",
        5)

    hf_tweets = crawl_tweets(driver, ["huggingface.co"])
    write_papers_to_db(hf_tweets, os.getenv(
            "TURSO_URL"), os.getenv("TURSO_AUTH_TOKEN"), date)

    driver.driver.quit()


if __name__ == "__main__":
    load_dotenv()
    _main()
