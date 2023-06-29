"""
    GitHub Example
    --------------

    Shows how to authorize users with Github.

    pip install sqlalchemy

"""
from quart import Quart, request, g, session, redirect, url_for
from quart import render_template_string, jsonify
from quart_github import GitHub

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

DATABASE_URI = 'sqlite:////tmp/github-quart.db'
SECRET_KEY = 'development key'
DEBUG = True

# Set these values
GITHUB_CLIENT_ID = 'XXX'
GITHUB_CLIENT_SECRET = 'YYY'

# setup quart
app = Quart(__name__)
app.config.from_object(__name__)

# setup github-quart
github = GitHub(app)

# setup sqlalchemy
engine = create_engine(app.config['DATABASE_URI'])
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


def init_db():
    Base.metadata.create_all(bind=engine)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    github_access_token = Column(String(255))
    github_id = Column(Integer)
    github_login = Column(String(255))

    def __init__(self, github_access_token):
        self.github_access_token = github_access_token


@app.before_request
async def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.get(session['user_id'])


@app.after_request
async def after_request(response):
    db_session.remove()
    return response


@app.route('/')
async def index():
    if g.user:
        t = 'Hello! %s <a href="{{ url_for("user") }}">Get user</a> ' \
            '<a href="{{ url_for("repo") }}">Get repo</a> ' \
            '<a href="{{ url_for("logout") }}">Logout</a>'
        t %= g.user.github_login
    else:
        t = 'Hello! <a href="{{ url_for("login") }}">Login</a>'

    return await render_template_string(t)


@github.access_token_getter
async def token_getter():
    user = g.user
    if user is not None:
        return user.github_access_token


@app.route('/github-callback')
@github.authorized_handler
async def authorized(access_token):
    next_url = request.args.get('next') or url_for('index')
    if access_token is None:
        return redirect(next_url)

    user = User.query.filter_by(github_access_token=access_token).first()
    if user is None:
        user = User(access_token)
        db_session.add(user)

    user.github_access_token = access_token

    # Not necessary to get these details here,
    # but it helps humans to identify users easily.
    g.user = user
    github_user = await github.get('/user')
    if not isinstance(github_user, dict):
        # must be a response with an error
        return github_user.status_code, github_user.content
    user.github_id = github_user['id']
    user.github_login = github_user['login']

    db_session.commit()

    session['user_id'] = user.id
    return redirect(next_url)


@app.route('/login')
async def login():
    if session.get('user_id', None) is None:
        return github.authorize()
    else:
        return 'Already logged in'


@app.route('/logout')
async def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/user')
async def user():
    return jsonify(await github.get('/user'))


@app.route('/repo')
async def repo():
    return jsonify(await github.get('/repos/luckydonald/github-quart'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
