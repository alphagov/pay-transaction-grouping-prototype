import sqlalchemy
from db import session, payment_links_table
from flask import Blueprint, render_template, request, redirect, url_for, abort
from slugify import slugify


payment_links = Blueprint(
    'payment_links',
    __name__,
)


def get_payment_link_by_id(id):
    try:
        result = session.execute(
            payment_links_table.select().where(
                payment_links_table.columns.id == int(id)
            )
        )
        return result.fetchone()
    except Exception as e:
        print(e)
        abort(404)


@payment_links.route("/", methods=['GET', 'POST'])
def index():
    return render_template(
        "payment-links/index.html",
        links=session.query(payment_links_table).filter_by(created=True).all()
    )


@payment_links.route("/create")
def create_payment_link():
    insert = sqlalchemy.insert(payment_links_table).values(created=False)
    result = session.execute(insert)
    return redirect(url_for(
        '.title_and_description',
        id=result.lastrowid,
    ))


@payment_links.route("/<id>/title-and-description", methods=['GET', 'POST'])
def title_and_description(id):
    if request.method == 'POST':
        update = sqlalchemy.get_payment_link_by_id(id).update({
            'title': request.form['title'],
            'description': request.form['description'],
            'slug': slugify(request.form['title']),
        })
        session.execute(update)
        return redirect(url_for('.ammount', id=id))
    return render_template(
        "payment-links/title-and-description.html",
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
        "payment-links/ammount.html",
    )


@payment_links.route("/<id>/summary", methods=['GET', 'POST'])
def summary(id):
    link = session.query(payment_links_table).get(id)
    if request.method == 'POST':
        update = link.update({
            'created': True
        })
        session.execute(update)
    return render_template(
        "payment-links/summary.html",
        link=link,
        metadata=[
            [
                {'text': key},
                {'text': value},
                {'html': '<a href="#">Edit</a>'},
            ]
            for key, value in (link.metadata or {}).items()
        ]
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
