from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from time import sleep
from dataclasses import dataclass
from typing import List

@dataclass
class ArxivPaper:
    title: str
    abstract: str
    authors: str

def scrape_arxiv_abstract(driver, arxiv_link: str):
    driver.go_link(arxiv_link, 5)

    title = driver.driver.find_element(By.XPATH, "//h1[contains(@class, 'title')]").text
    abstract = driver.driver.find_element(By.TAG_NAME, "blockquote").text
    authors = driver.driver.find_element(By.XPATH, "//div[contains(@class, 'authors')]").text

    return ArxivPaper(title=title, abstract=abstract, authors=authors)



