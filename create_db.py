import sqlalchemy as db

engine = db.create_engine('sqlite+libsql://127.0.0.1:8080')
conn = engine.connect()
metadata = db.MetaData()
Users = db.Table('Users', metadata,
            db.Column('Id', db.Integer(), primary_key=True),
            db.Column('Name', db.String(255), nullable=False)
                 )
Comments = db.Table('Comments', metadata,
              db.Column('Id', db.Integer(), primary_key=True),
              db.Column('UserId', db.Integer(), nullable=False),
              db.Column('Comment', db.String(4096), nullable=False),
              db.Column('Created', db.Date(), default=True)
              )

metadata.create_all(engine)

print("Created all tables.")