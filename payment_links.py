import json
import sqlalchemy
from db import session, payment_links_table
from flask import Blueprint, abort, render_template, request, redirect, url_for
from slugify import slugify


payment_links = Blueprint(
    'payment_links',
    __name__,
)


def update_payment_link_by_id(id, **kwargs):
    try:
        update = payment_links_table.update().values(
            **kwargs
        ).where(
            payment_links_table.c.id == int(id)
        )
        session.execute(update)
    except Exception as e:
        print(e)
        return redirect(url_for('.create_payment_link'))


def get_payment_link_by_id(id):
    select = sqlalchemy.select([payment_links_table]).where(
        payment_links_table.c.id == int(id)
    )
    result = session.execute(select).fetchone()
    if not result:
        abort(404)
    id, created, title, slug, description, ammount, metadata = (
        session.execute(select).fetchone()
    )
    return {
        'id': id,
        'created': created,
        'title': title,
        'slug': slug,
        'description': description,
        'ammount': ammount,
        'metadata': metadata,
    }


@payment_links.route("/", methods=['GET', 'POST'])
def index():
    return render_template(
        "payment-links/index.html",
        links=session.query(payment_links_table).filter_by(created=True).all(),
        metadata_loader=lambda json_string: json.loads(json_string or {}).items(),
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
        update_payment_link_by_id(
            id,
            title=request.form.get('title', 'Untitled'),
            description=request.form.get('description', ''),
            slug=slugify(request.form.get('title', 'Untitled')),
        )
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
        update_payment_link_by_id(
            id, ammount=ammount
        )
        return redirect(url_for('.summary', id=id))
    return render_template(
        "payment-links/ammount.html",
    )


@payment_links.route("/<id>/summary", methods=['GET', 'POST'])
def summary(id):
    if request.method == 'POST':
        update_payment_link_by_id(
            id, created=True
        )
        return redirect(url_for('.index'))
    link = get_payment_link_by_id(id)
    return render_template(
        "payment-links/summary.html",
        id=link['id'],
        created=link['created'],
        title=link['title'],
        slug=link['slug'],
        description=link['description'],
        ammount=link['ammount'],
        metadata=[
            [{'text': key}, {'text': value}]
            for key, value in json.loads(link['metadata']).items()
        ] if link['metadata'] else None,
    )


@payment_links.route("/<id>/add-reporting", methods=['GET', 'POST'])
def add_reporting(id):
    link = get_payment_link_by_id(id)
    if request.method == 'POST':
        metadata = json.loads(link['metadata'] or '{}')
        metadata.update({
            request.form['key']: request.form['value']
        })
        update_payment_link_by_id(
            id,
            metadata=json.dumps(metadata),
        )
        return redirect(url_for('.summary', id=id))
    return render_template(
        "payment-links/add-reporting.html",
    )
