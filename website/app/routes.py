from flask import redirect, render_template, request, session, url_for
from app import app
import requests
from flask import jsonify
from bs4 import BeautifulSoup
from supabase import create_client, Client
import os

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@app.route('/')
def index():
    category = 'cs.AI'  # to choose a different category
    xml_data = fetch_arxiv_papers(category)
    papers = parse_arxiv_papers(xml_data)
    return render_template('index.html', papers=papers)

@app.route('/sign_up')
def sign_up():
    return render_template('sign_up.html')

@app.route('/sign_in')
def sign_in():
    return render_template('sign_in.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    result = supabase.auth.sign_in_with_password(data)
    if result.user:  # Check if user exists in result
        user_obj = result.user  # Access user object
        user_dict = {
            'id': user_obj.id,
            'app_metadata': user_obj.app_metadata,
            'user_metadata': user_obj.user_metadata,
            'aud': user_obj.aud,
            'email': user_obj.email,
            'phone': user_obj.phone,
            'created_at': user_obj.created_at.isoformat(),
            'confirmed_at': user_obj.confirmed_at.isoformat(),
            'email_confirmed_at': user_obj.email_confirmed_at.isoformat(),
            'last_sign_in_at': user_obj.last_sign_in_at.isoformat(),
            'role': user_obj.role,
            'updated_at': user_obj.updated_at.isoformat(),
        }
        session['username'] = user_dict['email']  # Store username in session
        return jsonify({"message": "Logged in!", "user": user_dict}), 200
    return jsonify({"message": "Failed to log in"}), 401


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    result = supabase.auth.sign_up(data)
    if result.user:  # Check if user exists in result
        user_obj = result.user  # Access user object
        user_dict = {
            'id': user_obj.id,
            'app_metadata': user_obj.app_metadata,
            'user_metadata': user_obj.user_metadata,
            'aud': user_obj.aud,
            'email': user_obj.email,
            'phone': user_obj.phone,
            'created_at': user_obj.created_at.isoformat(),
        }
        session['username'] = user_dict['email']  # Store username in session
        return jsonify({"message": "User registered successfully!", "user": user_dict}), 200
    return jsonify({"message": "Failed to sign up"}), 401

@app.route('/comments', methods=['POST'])
def create_comment():
    data = request.get_json()
    result = supabase.table("comments").insert(data).execute()
    return jsonify(result), 201

@app.route('/comments/<int:post_id>', methods=['GET'])
def get_comments(post_id):
    result = supabase.table("comments").select().filter("post_id", "eq", post_id).execute()
    return jsonify(result)
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
