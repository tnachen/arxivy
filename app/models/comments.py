from dataclasses import dataclass
from datetime import datetime
from typing import List
from sqlalchemy import create_engine

# TODO: Configure this
DATABASE_URL = "sqlite+libsql://127.0.0.1:8080"

@dataclass
class Comment:
    user: str
    body: str
    created: datetime

def get_comments(arxiv_id: str) -> List[Comment]:
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()

