import os
from flask import render_template
from app import app
import requests
from bs4 import BeautifulSoup
import libsql_client
from dotenv import load_dotenv

load_dotenv()

TURSO_URL = os.getenv("TURSO_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")


@app.route('/')
def index():
    category = 'cs.AI'  # to choose a different category
    xml_data = fetch_arxiv_papers(category)
    papers = parse_arxiv_papers(xml_data)
    return render_template('index.html', papers=papers)


@app.route('/twitter')
def twitter():
    papers = fetch_twitter_papers()
    return render_template('twitter.html', papers=papers)


def fetch_twitter_papers():
    with libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_AUTH_TOKEN) as client:
        return client.execute("SELECT * FROM papers WHERE views > 300 ORDER BY created_at DESC")

def fetch_arxiv_papers(category):
    url = f'http://export.arxiv.org/api/query?search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending'
    response = requests.get(url)
    return response.content


def parse_arxiv_papers(xml_data):
    soup = BeautifulSoup(xml_data, 'lxml')
    papers = []
    for entry in soup.find_all('entry'):
        paper = {
            'title': entry.title.text,
            'summary': entry.summary.text,
            'authors': [author.text for author in entry.find_all('name')],
            'published': entry.published.text,
            'link': entry.id.text,
        }
        papers.append(paper)
    return papers
