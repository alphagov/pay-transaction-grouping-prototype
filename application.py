import os
import jinja2
from flask import Flask
from govuk_frontend_jinja.flask_ext import init_govuk_frontend
from main import dashboard, services, transactions, pay, settings
from payment_links import payment_links

app = Flask(__name__)


app.register_blueprint(
    dashboard,
)
app.register_blueprint(
    services,
    url_prefix='/services',
)
app.register_blueprint(
    transactions,
    url_prefix='/transactions',
)
app.register_blueprint(
    pay,
    url_prefix='/pay',
)
app.register_blueprint(
    settings,
    url_prefix='/settings',
)
app.register_blueprint(
    payment_links,
    url_prefix='/payment-links',
)

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
app.jinja_loader = jinja2.FileSystemLoader([
    os.path.join(repo_root, 'templates/vendor/govuk'),
    os.path.join(repo_root, 'templates'),
])

init_govuk_frontend(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
