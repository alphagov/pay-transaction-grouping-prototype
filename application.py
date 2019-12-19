import json
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from flask import Flask, render_template, request, redirect, url_for
from itertools import chain

app = Flask(__name__)


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
    sqlalchemy.Column('link', sqlalchemy.String),
)
transactions_table.create(bind=engine, checkfirst=True)
payment_links_table.create(bind=engine, checkfirst=True)

Session = sessionmaker(bind=engine)
session = Session()


@app.route("/")
def home():

    total = session.query(
        sqlalchemy.func.sum(transactions_table.c.ammount).label('total'),
    ).scalar() or 0

    return render_template("index.html", total=total)


@app.route("/services")
def services():

    total = session.query(
        sqlalchemy.func.sum(transactions_table.c.ammount).label('total'),
    ).scalar() or 0

    return render_template("services.html", example_total=total)


@app.route("/payment-links", methods=['GET', 'POST'])
def payment_links():
    return render_template(
        "payment-links.html",
        links=session.query(payment_links_table).all()
    )


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
        insert = sqlalchemy.insert(payment_links_table).values(
            link=url_for(
                '.payment_link',
                ammount=ammount,
                **metadata,
            ),
        )
        session.execute(insert)
        return redirect(url_for('.payment_links'))
    return render_template(
        "create-payment-link.html",
    )


@app.route("/pay/<int:ammount>", methods=['GET', 'POST'])
def payment_link(ammount):
    if request.method == 'POST':
        insert = sqlalchemy.insert(transactions_table).values(
            ammount=ammount,
            metadata=json.dumps({
                k: v
                for k, v in request.args.items()
                if k and v
            }),
        )
        session.execute(insert)
        return redirect(url_for('confirmation', ammount=ammount))
    return render_template(
        "pay.html",
        ammount=ammount,
    )


@app.route("/confirmation/<int:ammount>", methods=['GET', 'POST'])
def confirmation(ammount):
    return render_template("confirmation.html", ammount=ammount)


def _get_rich_transactions(extra_columns=None):
    for ammount, metadata in session.query(transactions_table).all():
        metadata = json.loads(metadata)
        for key, value in (extra_columns or []):
            metadata.update({key: value})
        yield ammount, metadata


def _get_subquery(rich_transactions):
    stmts = [
        sqlalchemy.select([
            sqlalchemy.cast(
                sqlalchemy.literal(ammount),
                sqlalchemy.Float,
            ).label('ammount'),
        ] + [
            sqlalchemy.cast(
                sqlalchemy.literal(metadata.get(metadata_key)),
                sqlalchemy.String,
            ).label(metadata_key)
            for metadata_key in _column_names(rich_transactions)
        ])
        for ammount, metadata in rich_transactions
    ]
    subquery = sqlalchemy.union_all(*stmts)
    return subquery


def _column_names(rich_transactions):
    return list(filter(None, set(chain.from_iterable((
        metadata.keys() for ammount, metadata in rich_transactions
    )))))


def _get_reporting_results(subquery, grouping_columns):
    if grouping_columns:
        grouping_columns = [
            getattr(subquery.c, grouping_column)
            for grouping_column in grouping_columns
        ]
        return session.query(
            sqlalchemy.func.count(subquery.c.ammount).label('transactions'),
            sqlalchemy.func.sum(subquery.c.ammount).label('total'),
            *grouping_columns
        ).group_by(*grouping_columns).order_by(*grouping_columns).all()
    return session.query(
        sqlalchemy.func.count(subquery.c.ammount).label('transactions'),
        sqlalchemy.func.sum(subquery.c.ammount).label('total'),
    ).all()


@app.route("/reports")
def reports():

    grouping_columns = request.args.getlist('grouping_columns')

    rich_transactions = list(_get_rich_transactions())

    if not rich_transactions:
        return render_template('no-reports.html')

    column_names = _column_names(rich_transactions)

    for grouping_column in grouping_columns:
        if grouping_column not in column_names:
            return redirect(url_for('.reports'))

    subquery = _get_subquery(rich_transactions)
    reporting_results = _get_reporting_results(subquery, grouping_columns)

    return render_template(
        "reports.html",
        results=reporting_results,
        column_names=column_names,
    )


@app.route("/services/reports")
def services_reports():

    grouping_columns = request.args.getlist('grouping_columns')

    rich_transactions = list(_get_rich_transactions(
        extra_columns=[
            ('Service', 'Example service'),
            ('Merchant ID', 'EXAMPLE_SERVICE_0345_LIVE'),
        ]
    ))

    if not rich_transactions:
        return render_template('no-reports.html')

    column_names = _column_names(rich_transactions)

    for grouping_column in grouping_columns:
        if grouping_column not in column_names:
            return redirect(url_for('.reports'))

    subquery = _get_subquery(rich_transactions)
    reporting_results = _get_reporting_results(subquery, grouping_columns)

    return render_template(
        "services-reports.html",
        results=reporting_results,
        column_names=column_names,
    )


@app.route("/transactions")
def transactions():

    rich_transactions = list(_get_rich_transactions())
    if not rich_transactions:
        return render_template('no-reports.html')
    column_names = _column_names(rich_transactions)
    subquery = _get_subquery(rich_transactions)

    results = session.execute(
        subquery.select()
    )

    return render_template(
        "transactions.html",
        transactions=[
            dict(result) for result in results.fetchall()
        ],
        column_names=column_names,
    )


@app.route("/drop")
def drop():
    all = session.query(transactions_table)
    all.delete(synchronize_session=False)
    all = session.query(payment_links_table)
    all.delete(synchronize_session=False)
    return redirect(url_for('.reports'))


@app.route("/populate")
def populate():
    for ammount, metadata in ([
        (100, {'post': 'Bangkok', 'fee type': 'Fee 19', 'country': 'Thailand'}),
        (100, {'post': 'Bangkok', 'fee type': 'Fee 19', 'country': 'Thailand'}),
        (100, {'post': 'Phuket', 'fee type': 'Fee 19', 'country': 'Thailand'}),
        (55, {'post': 'Phuket', 'fee type': 'Fee 4', 'country': 'Thailand'}),
        (30, {'post': 'Phuket', 'fee type': 'Fee 6', 'country': 'Thailand'}),
        (100, {'post': 'Paris', 'fee type': 'Fee 19', 'country': 'France'}),
        (100, {'post': 'Marseille', 'fee type': 'Fee 19', 'country': 'France'}),
        (100, {'post': 'Ibiza', 'fee type': 'Fee 19', 'country': 'Spain'}),
        (100, {'post': 'Ibiza', 'fee type': 'Fee 19', 'country': 'Spain'}),
        (100, {'post': 'Ibiza', 'fee type': 'Fee 19', 'country': 'Spain'}),
        (55, {'post': 'Ibiza', 'fee type': 'Fee 4', 'country': 'Spain'}),
        (100, {'post': 'Barcelona', 'fee type': 'Fee 19', 'country': 'Spain'}),
    ] * 3) + [
        (100, {'post': 'Washington', 'fee type': 'Fee 19', 'country': 'USA'}),
        (55, {'post': 'Boston', 'fee type': 'Fee 4', 'country': 'USA'}),
        (100, {'post': 'Montreal', 'fee type': 'Fee 19', 'country': 'Canada'}),
    ]:
        insert = sqlalchemy.insert(transactions_table).values(
            ammount=ammount,
            metadata=json.dumps(metadata),
        )
        session.execute(insert)
    return redirect(url_for('.reports'))


@app.route("/settings")
def settings():
    return render_template("settings.html")
