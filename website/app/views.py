from flask import render_template, request
from app import app
from models.comments import get_comments
import requests
from bs4 import BeautifulSoup

@app.route('/')
def index():
    category = 'cs.AI'  # to choose a different category
    xml_data = fetch_arxiv_papers(category)
    papers = parse_arxiv_papers(xml_data)
    return render_template('index.html', papers=papers)

@app.route('/comments')
def comments():
    arxiv_id = request.args.get("id")
    comments = get_comments(arxiv_id=arxiv_id)
    # Fetch paper summary from arxiv or we store it locally?
    paper = None
    #paper = fetch_arxiv_paper(arxiv_id = arxiv_id)
    return render_template('comments.html', paper=paper, comments=comments)

def parse_arxiv_id(link: str):
    return link.split("/")[-1]


def fetch_arxiv_papers(category: str):
    url = f'http://export.arxiv.org/api/query?search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending'
    response = requests.get(url)
    return response.content

def parse_arxiv_papers(xml_data):
    soup = BeautifulSoup(xml_data, 'lxml')
    papers = []
    for entry in soup.find_all('entry'):
        paper = {
            'id': parse_arxiv_id(entry.id.text),
            'title': entry.title.text,
            'summary': entry.summary.text,
            'authors': [author.text for author in entry.find_all('name')],
            'published': entry.published.text,
            'link': entry.id.text,
        }
        papers.append(paper)
    return papers
