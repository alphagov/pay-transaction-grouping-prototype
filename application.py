import json
import pandas
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from flask import Flask, render_template, request, redirect, url_for, abort
from itertools import chain

app = Flask(__name__)


engine = sqlalchemy.create_engine('sqlite:///transactions.sqlite')
connection = engine.connect()
metadata = sqlalchemy.MetaData()


pandas.read_csv('./transactions.csv').to_sql(
    'transactions',
    connection,
    if_exists='append',
    index=False,
)
transactions = sqlalchemy.Table(
    'transactions',
    metadata,
    autoload=True,
    autoload_with=engine,
)
Session = sessionmaker(bind=engine)
session = Session()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create-payment-link", methods=['GET', 'POST'])
def create_payment_link():
    if request.method == 'POST':
        metadata = {
            request.form[k]: request.form[k.replace('key', 'value')]
            for k, v in request.form.items() if k.startswith('key')
        }
        try:
            ammount = int(request.form.get('ammount', 0))
        except ValueError:
            return "ammount must be a whole number", 400
        return redirect(url_for(
            '.payment_link',
            ammount=ammount,
            **metadata,
        ))
    return render_template(
        "create-payment-link.html",
    )


@app.route("/pay/<ammount>", methods=['GET', 'POST'])
def payment_link(ammount):
    if request.method == 'POST':
        insert = sqlalchemy.insert(transactions).values(
            ammount=ammount,
            metadata=json.dumps({
                k: v
                for k, v in request.args.items()
                if k and v
            }),
        )
        session.execute(insert)
        return redirect(url_for('confirmation'))
    return render_template(
        "pay.html",
        ammount=ammount,
    )


@app.route("/confirmation", methods=['GET', 'POST'])
def confirmation():
    return render_template("confirmation.html")


@app.route("/reports")
def reports():

    grouping_column = request.args.get('column')

    rich_transactions = [
        (ammount, json.loads(metadata))
        for ammount, metadata in session.query(transactions).all()
    ]

    column_names = set(chain.from_iterable((
        metadata.keys() for ammount, metadata in rich_transactions
    )))

    if grouping_column and grouping_column not in column_names:
        abort(400)

    if not rich_transactions:
        return render_template("no-reports.html")

    stmts = [
        sqlalchemy.select([
            sqlalchemy.cast(
                sqlalchemy.literal(ammount), sqlalchemy.Float
            ).label('ammount'),
        ] + [
            sqlalchemy.cast(
                sqlalchemy.literal(metadata.get(metadata_key)), sqlalchemy.String
            ).label(metadata_key)
            for metadata_key in column_names
        ])
        for ammount, metadata in rich_transactions
    ]
    subquery = sqlalchemy.union_all(*stmts)
    results = session.execute(
        subquery.select()
    )

    grouping_columns = request.args.getlist('grouping_columns')

    if grouping_columns:
        grouping_columns = [
            getattr(subquery.c, grouping_column)
            for grouping_column in grouping_columns
        ]

        s = session.query(
            sqlalchemy.func.count(subquery.c.ammount).label('transactions'),
            sqlalchemy.func.sum(subquery.c.ammount).label('total'),
            *grouping_columns
        ).group_by(*grouping_columns).all()
    else:
        s = []

    return render_template(
        "reports.html",
        transactions=[
            dict(result)
            for result in results.fetchall()
        ],
        results=s,
        column_names=list(filter(None, column_names)),
    )


@app.route("/drop")
def drop():
    all = session.query(transactions)
    all.delete(synchronize_session=False)
    return redirect(url_for('.reports'))
