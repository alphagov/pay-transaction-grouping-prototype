import os
import jinja2
import json
import sqlalchemy
import uuid
from collections import OrderedDict
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import postgresql
from flask import Flask, render_template, request, redirect, url_for
from govuk_frontend_jinja.flask_ext import init_govuk_frontend
from datetime import datetime, timedelta
from itertools import chain
from slugify import slugify

app = Flask(__name__)

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
app.jinja_loader = jinja2.FileSystemLoader([
    os.path.join(repo_root, 'templates/vendor/govuk'),
    os.path.join(repo_root, 'templates'),
])

init_govuk_frontend(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


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
        postgresql.UUID(as_uuid=True),
        unique=True,
        nullable=False,
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


payment_links = Blueprint(
    'payment_links',
    __name__,
    template_folder='payment-links',
    url_prefix='/payment-links',
)
app.register_blueprint(payment_links)


@payment_links.route("/", methods=['GET', 'POST'])
def payment_links():
    return render_template(
        "index.html",
        links=session.query(payment_links_table).filter_by(created=True).all()
    )


@payment_links.route("/create")
def create_payment_link():
    id = uuid.uuid4()
    insert = sqlalchemy.insert(payment_links_table).values(id=id)
    session.execute(insert)
    return redirect(url_for(
        '.title_and_description',
        id=id,
    ))


@payment_links.route("/<id>/title-and-description", methods=['GET', 'POST'])
def title_and_description(id):
    if request.method == 'POST':
        update = session.query(payment_links_table).get(id).update({
            'title': request.form['title'],
            'description': request.form['description'],
            'slug': slugify(request.form['title']),
        })
        session.execute(update)
        return redirect(url_for('.ammount', id=id))
    return render_template(
        "title-and-description.html",
    )


@payment_links.route("/<id>/ammount", methods=['GET', 'POST'])
def ammount(id):
    if request.method == 'POST':
        try:
            ammount = int(request.form.get('ammount', 0))
        except ValueError:
            return "ammount must be a whole number", 400
        update = session.query(payment_links_table).get(id).update({
            'ammount': ammount,
        })
        session.execute(update)
        return redirect(url_for('.summary'))
    return render_template(
        "ammount.html",
    )


@payment_links.route("/<id>/summary", methods=['GET', 'POST'])
def title_and_description(id):
    link = session.query(payment_links_table).get(id)
    if request.method == 'POST':
        update = link.update({
            'created': True
        })
        session.execute(update)
    return render_template(
        "summary.html",
        title=link.title,
        description=link.description,
        ammount=link.ammount,
    )


@payment_links.route("/<id>/add-reporting", methods=['GET', 'POST'])
def add_reporting(id):
    link = session.query(payment_links_table).get(id)
    if request.method == 'POST':
        metadata = link.metadata or {}
        metadata.update({
            request.form['key']: request.form['value']
        })
        update = link.update({
            'metadata': JSON.dumps(metadata),
        })
        session.execute(update)
        return redirect(url_for('.payment_links'))
    return render_template(
        "payment-links/add-reporting.html",
    )


@app.route("/pay/<slug>", methods=['GET', 'POST'])
def payment_link(slug):
    link = session.query(payment_links_table).get(slug=slug)
    if request.method == 'POST':
        insert = sqlalchemy.insert(transactions_table).values(
            ammount=link.ammount,
            metadata=link.metadata,
        )
        session.execute(insert)
        return redirect(url_for('confirmation', ammount=link.ammount))
    return render_template(
        "pay.html",
        ammount=link.ammount,
    )


@app.route("/confirmation/<int:ammount>", methods=['GET', 'POST'])
def confirmation(ammount):
    return render_template("confirmation.html", ammount=ammount)


def _get_rich_transactions(extra_columns=None):
    for ammount, metadata in session.query(transactions_table).all():
        out = OrderedDict()
        for key, value in (extra_columns or []):
            out.update({key: value})
        out.update(json.loads(metadata))
        yield ammount, out


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


@app.route("/services/transactions")
def services_transactions():

    rich_transactions = list(_get_rich_transactions(
        extra_columns=[
            ('Service', 'Example service'),
            ('Merchant ID', 'EXAMPLE_SERVICE_0345_LIVE'),
        ]
    ))
    if not rich_transactions:
        return render_template('services-no-reports.html')

    transactions, column_names = get_transactions_and_column_names(rich_transactions)

    return render_template(
        "services-transactions.html",
        transactions=transactions,
        column_names=column_names,
    )


@app.route("/transactions")
def transactions():

    rich_transactions = list(_get_rich_transactions())
    if not rich_transactions:
        return render_template('no-reports.html')

    transactions, column_names = get_transactions_and_column_names(rich_transactions)
    return render_template(
        "transactions.html",
        transactions=transactions,
        column_names=column_names,
    )


def get_transactions_and_column_names(rich_transactions):

    column_names = _column_names(rich_transactions)
    subquery = _get_subquery(rich_transactions)

    results = session.execute(
        subquery.select()
    )

    def datemaker(i):
        return (
            datetime.utcnow() - timedelta(seconds=(i * 2345))
        ).strftime('%d %b %Y at %-I:%M%p')

    transactions = reversed([
        [
            {'text': '£{:,.2f}'.format(result.ammount)},
            {'text': datemaker(index)},
        ] + [
            {'text': dict(result).get(column_name)}
            for column_name in column_names
        ]
        for index, result in enumerate(results.fetchall())
    ])

    column_names = [
        {'text': 'Ammount'},
        {'text': 'Date'},
    ] + [
        {'text': column_name}
        for column_name in column_names
    ]

    return transactions, column_names


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
    return redirect(url_for('.transactions'))


@app.route("/settings")
def settings():
    return render_template("settings.html")
