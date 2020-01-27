import json
import sqlalchemy
from collections import OrderedDict
from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime, timedelta
from itertools import chain
from db import session, payment_links_table, transactions_table


dashboard = Blueprint(
    'dashboard',
    __name__,
)

services = Blueprint(
    'services',
    __name__,
)

transactions = Blueprint(
    'transactions',
    __name__,
)

pay = Blueprint(
    'pay',
    __name__,
)

settings = Blueprint(
    'settings',
    __name__,
)


@dashboard.route("/")
def home():

    total = session.query(
        sqlalchemy.func.sum(transactions_table.c.ammount).label('total'),
    ).scalar() or 0

    return render_template("index.html", total=total)


@services.route("/")
def services_index():

    total = session.query(
        sqlalchemy.func.sum(transactions_table.c.ammount).label('total'),
    ).scalar() or 0

    return render_template("services.html", example_total=total)


@pay.route("/<slug>", methods=['GET', 'POST'])
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


@pay.route("/confirmation/<int:ammount>", methods=['GET', 'POST'])
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


@transactions.route("/reports")
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


@services.route("/reports")
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


@transactions.route("/services")
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


@transactions.route("/")
def transactions_index():

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


@settings.route("/drop")
def drop():
    all = session.query(transactions_table)
    all.delete(synchronize_session=False)
    all = session.query(payment_links_table)
    all.delete(synchronize_session=False)
    return redirect(url_for('transactions.transactions_index'))


@settings.route("/populate")
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
    return redirect(url_for('transactions.transactions_index'))


@settings.route("/")
def settings_index():
    return render_template("settings.html")
