GitHub-Quart
============

.. module:: quart_github

GitHub-Quart is an extension to `Quart`_ that allows you authenticate your
users via GitHub using `OAuth`_ protocol and call `GitHub API`_ methods.

This work is based on the excellent Flask extension `GitHub-Flask`_ and is essentially a port of that to Quart.

GitHub-Quart depends on the `requests`_ library.

.. _Quart: http://quart.pocoo.org/
.. _OAuth: http://oauth.net/
.. _GitHub API: http://developer.github.com/v3/
.. _requests: http://python-requests.org/
.. _GitHub-Flask: https://github.com/cenkalti/github-flask/


Installation
------------

Install the extension with the following command:

.. code-block:: bash

    $ pip install GitHub-Quart


Configuration
-------------

Here’s an example of how GitHub-Quart is typically initialized and configured:

.. code-block:: python

    from quart import Quart
    from quart_github import GitHub

    app = Quart(__name__)
    app.config['GITHUB_CLIENT_ID'] = 'XXX'
    app.config['GITHUB_CLIENT_SECRET'] = 'YYY'

    # For GitHub Enterprise
    app.config['GITHUB_BASE_URL'] = 'https://HOSTNAME/api/v3/'
    app.config['GITHUB_AUTH_URL'] = 'https://HOSTNAME/login/oauth/'

    github = GitHub(app)

The following configuration settings exist for GitHub-Quart:

=================================== ==========================================
`GITHUB_CLIENT_ID`                  Your GitHub application's client id. Go to
                                    https://github.com/settings/applications
                                    to register new application.

`GITHUB_CLIENT_SECRET`              Your GitHub application's client secret.

`GITHUB_BASE_URL`                   Base URL for API requests. Override this
                                    to use with GitHub Enterprise. Default is
                                    "https://api.github.com/".

`GITHUB_AUTH_URL`                   Base authentication endpoint. Override this
                                    to use with GitHub Enterprise. Default is
                                    "https://github.com/login/oauth/".
=================================== ==========================================


Authenticating / Authorizing Users
----------------------------------

To authenticate your users with GitHub simply call
:meth:`~quart_github.GitHub.authorize` at your login handler:

.. code-block:: python

    @app.route('/login')
    async def login():
        return github.authorize()

It will redirect the user to GitHub. If the user accepts the authorization
request GitHub will redirect the user to your callback URL with the
OAuth ``code`` parameter. Then the extension will make another request to
GitHub to obtain access token and call your
:meth:`~quart_github.GitHub.authorized_handler` function with that token.
If the authorization fails ``oauth_token`` parameter will be ``None``:

.. code-block:: python

    @app.route('/github-callback')
    @github.authorized_handler
    async def authorized(oauth_token):
        next_url = request.args.get('next') or url_for('index')
        if oauth_token is None:
            flash("Authorization failed.")
            return redirect(next_url)

        user = await User.query.filter_by(github_access_token=oauth_token).first()
        if user is None:
            user = User(oauth_token)
            db_session.add(user)

        user.github_access_token = oauth_token
        await db_session.commit()
        return redirect(next_url)

Store this token somewhere securely. It is needed later to make requests on
behalf of the user.


Invoking Remote Methods
-----------------------

We need to register a function as a token getter for Github-Quart extension.
It will be called automatically by the extension to get the access token of
the user. It should return the access token or ``None``:

.. code-block:: python

    @github.access_token_getter
    async def token_getter():
        user = g.user
        if user is not None:
            return user.github_access_token

After setting up you can use the
:meth:`~quart_github.GitHub.get`,  :meth:`~quart_github.GitHub.post`
or other verb methods of the :class:`~quart_github.GitHub` object.
They will return a dictionary representation of the given API endpoint.

.. code-block:: python

    @app.route('/repo')
    async def repo():
        repo_dict = await github.get('repos/luckydonald/github-quart')
        return str(repo_dict)


Full Example
------------

A full example can be found in `example.py`_ file.
Install the required `Quart-SQLAlchemy`_ package first.
Then edit the file and change
``GITHUB_CLIENT_ID`` and ``GITHUB_CLIENT_SECRET`` settings.
Then you can run it as a python script:

.. code-block:: bash

    $ pip install Quart-SQLAlchemy
    $ python example.py

.. _example.py: https://github.com/luckydonald/github-quart/blob/master/example.py
.. _Quart-SQLAlchemy: http://pythonhosted.org/Quart-SQLAlchemy/

API Reference
-------------

.. autoclass:: GitHub
   :members:

.. autoclass:: GitHubError
   :members:
