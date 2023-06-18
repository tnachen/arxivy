from flask import render_template
from app import app
import requests
from bs4 import BeautifulSoup

@app.route('/')
def index():
    category = 'cs.AI'  # to choose a different category
    xml_data = fetch_arxiv_papers(category)
    papers = parse_arxiv_papers(xml_data)
    return render_template('index.html', papers=papers)

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
