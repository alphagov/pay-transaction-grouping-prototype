import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import postgresql


engine = sqlalchemy.create_engine('sqlite:///transactions.sqlite')
connection = engine.connect()
metadata = sqlalchemy.MetaData()

transactions_table = sqlalchemy.Table(
    'transactions',
    metadata,
    sqlalchemy.Column('ammount', sqlalchemy.Integer),
    sqlalchemy.Column('metadata', sqlalchemy.String),
)
payment_links_table = sqlalchemy.Table(
    'payment_links',
    metadata,
    sqlalchemy.Column(
        'id',
        sqlalchemy.Integer,
        primary_key=True,
    ),
    sqlalchemy.Column('created', sqlalchemy.Boolean, default=False),
    sqlalchemy.Column('title', sqlalchemy.String),
    sqlalchemy.Column('slug', sqlalchemy.String),
    sqlalchemy.Column('description', sqlalchemy.String),
    sqlalchemy.Column('ammount', sqlalchemy.Integer),
    sqlalchemy.Column('metadata', sqlalchemy.String),

)
transactions_table.create(bind=engine, checkfirst=True)
payment_links_table.create(bind=engine, checkfirst=True)

Session = sessionmaker(bind=engine)
session = Session()
