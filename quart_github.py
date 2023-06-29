# -*- coding: utf-8 -*-
"""
    GitHub-Flask
    ============

    Authenticate users in your Flask app with GitHub.

"""
import asyncio
from weakref import finalize as Finalizer
import logging
from typing import Callable, Any, Dict, Awaitable
from werkzeug.wrappers import Response as WerkzeugResponse

from urllib.parse import urlencode, parse_qs
from functools import wraps

from httpx import AsyncClient, Response
from quart import redirect, request, json, Quart, current_app
from quart.utils import is_coroutine_function


__version__ = '3.2.0'

_logger = logging.getLogger(__name__)
# Add NullHandler to prevent logging warnings on startup
null_handler = logging.NullHandler()
_logger.addHandler(null_handler)


ASYNC_CALLABLE = Callable[[], Awaitable[None]]


def is_valid_response(response: Response) -> bool:
    """Returns ``True`` if response ``status_code`` is not an error type,
    returns ``False`` otherwise.

    :param response: :class:~`requests.Response` object to check
    :type response: :class:~`requests.Response`
    :returns: ``True`` if response ``status_code`` is not an error type,
              ``False`` otherwise.
    :rtype bool:
    """
    return 200 <= response.status_code <= 299


def is_json_response(response: Response) -> bool:
    """Returns ``True`` if response ``Content-Type`` is JSON.

    :param response: :class:~`requests.Response` object to check
    :type response: :class:~`requests.Response`
    :returns: ``True`` if ``response`` is JSON, ``False`` otherwise
    :rtype bool:
    """
    content_type = response.headers.get('Content-Type', '')
    return content_type == 'application/json' or content_type.startswith('application/json;')


class GitHubError(Exception):
    """Raised if a request fails to the GitHub API."""

    def __str__(self):
        try:
            message = self.response.json()['message']
        except Exception:
            message = None
        return "%s: %s" % (self.response.status_code, message)

    @property
    def response(self):
        """The :class:`~requests.Response` object for the request."""
        return self.args[0]


class GitHub(object):
    """
    Provides decorators for authenticating users with GitHub within a Flask
    application. Helper methods are also provided interacting with GitHub API.
    """
    BASE_URL = 'https://api.github.com/'
    BASE_AUTH_URL = 'https://github.com/login/oauth/'

    app: Quart | None
    client_id: str
    client_secret: str
    base_url: str
    auth_url: str
    session: AsyncClient
    _session: AsyncClient | None
    _finalizer: Finalizer | None
    get_access_token: ASYNC_CALLABLE

    def __init__(self, app=None):
        self._session = None
        self._finalizer = None
        if app is not None:
            self.app = app
            self.init_app(self.app)
        else:
            self.app = None

    def init_app(self, app):
        self.client_id = app.config['GITHUB_CLIENT_ID']
        self.client_secret = app.config['GITHUB_CLIENT_SECRET']
        self.base_url = app.config.get('GITHUB_BASE_URL', self.BASE_URL)
        self.auth_url = app.config.get('GITHUB_AUTH_URL', self.BASE_AUTH_URL)
        self.session = AsyncClient()

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, value: AsyncClient):
        loop = asyncio.get_event_loop()
        self._close_session(self._session, loop)
        # end if
        self._session = value
        self._finalizer = Finalizer(value, self._close_session, value, loop)

    @staticmethod
    def _close_session(session: AsyncClient, loop: asyncio.AbstractEventLoop):
        if (
            not session or session.is_closed or
            not loop or loop.is_closed()
        ):
            return
        loop.call_soon(session.aclose)

    def access_token_getter(self, f: Callable[[], Any] | ASYNC_CALLABLE):
        """
        Registers a function as the access_token getter. Must return the
        access_token used to make requests to GitHub on the user's behalf.

        """
        if is_coroutine_function(f):
            self.get_access_token = f
        else:
            async def async_f(*args, **kwargs):
                return f(*args, **kwargs)
            # end def

            self.get_access_token = async_f
        # end if
        return f
    # end def

    async def get_access_token(self):
        raise NotImplementedError

    def authorize(self, scope: list[str] = None, redirect_uri: str | None = None, state: str | None = None) -> WerkzeugResponse:
        """
        Redirect to GitHub and request access to a user's data.

        :param scope: List of `Scopes`_ for which to request access, formatted
                      as a string or comma delimited list of scopes as a
                      string. Defaults to ``None``, resulting in granting
                      read-only access to public information (includes public
                      user profile info, public repository info, and gists).
                      For more information on this, see the examples in
                      presented in the GitHub API `Scopes`_ documentation, or
                      see the examples provided below.
        :type scope: str
        :param redirect_uri: `Redirect URL`_ to which to redirect the user
                             after authentication. Defaults to ``None``,
                             resulting in using the default redirect URL for
                             the OAuth application as defined in GitHub.  This
                             URL can differ from the callback URL defined in
                             your GitHub application, however it must be a
                             subdirectory of the specified callback URL,
                             otherwise raises a :class:`GitHubError`.  For more
                             information on this, see the examples in presented
                             in the GitHub API `Redirect URL`_ documentation,
                             or see the example provided below.
        :type redirect_uri: str
        :param state: An unguessable random string. It is used to protect
                      against cross-site request forgery attacks.
        :type state: str

        For example, if we wanted to use this method to get read/write access
        to user profile information, in addition to read-write access to code,
        commit status, etc., we would need to use the `Scopes`_ ``user`` and
        ``repo`` when calling this method.

        .. code-block:: python

            github.authorize(scope="user,repo")

        Additionally, if we wanted to specify a different redirect URL
        following authorization.

        .. code-block:: python

            # Our application's callback URL is "http://example.com/callback"
            redirect_uri="http://example.com/callback/my/path"

            github.authorize(scope="user,repo", redirect_uri=redirect_uri)


        .. _Scopes: https://developer.github.com/v3/oauth/#scopes
        .. _Redirect URL: https://developer.github.com/v3/oauth/#redirect-urls

        """
        _logger.debug("Called authorize(), creating redirect.")
        params = {'client_id': self.client_id}
        if scope:
            params['scope'] = scope
        if redirect_uri:
            params['redirect_uri'] = redirect_uri
        if state:
            params['state'] = state

        url = self.auth_url + 'authorize?' + urlencode(params)
        _logger.debug("Redirecting to %s", url)
        return redirect(url)

    def authorized_handler(self, f):
        """
        Decorator for the route that is used as the callback for authorizing
        with GitHub. This callback URL can be set in the settings for the app
        or passed in during authorization.
        """
        @wraps(f)
        async def decorated(*args, **kwargs):
            if 'code' in request.args:
                data = await self._handle_response()
            else:
                data = await self._handle_invalid_response()
            async_f = current_app.ensure_async(f)
            return await async_f(*((data,) + args), **kwargs)
        return decorated

    async def _handle_response(self):
        """
        Handles response after the redirect to GitHub. This response
        determines if the user has allowed the this application access. If we
        were then we send a POST request for the access_key used to
        authenticate requests to GitHub.

        """
        _logger.debug("Handling response from GitHub")
        params = {
            'code': request.args.get('code'),
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        url = self.auth_url + 'access_token'
        _logger.debug("POSTing to %s", url)
        _logger.debug(params)
        response = await self.session.post(url, data=params)
        data: dict[bytes, list[bytes]] = parse_qs(response.content)
        _logger.debug("response.content = %s", data)
        token = data.get(b'access_token', [None])[0]
        if token is None:
            return None
        # end if
        return token.decode('ascii')

    async def _handle_invalid_response(self):
        pass

    async def raw_request(self, method: str, resource: str, access_token=None, **kwargs) -> Response:
        """
        Makes a HTTP request and returns the raw
        :class:`~requests.Response` object.

        """
        headers = self._pop_headers(kwargs)
        headers['Authorization'] = await self._get_authorization_header(access_token)
        url = self._get_resource_url(resource)
        return await self.session.request(method, url, follow_redirects=True, headers=headers, **kwargs)

    def _pop_headers(self, kwargs: dict) -> dict:
        try:
            headers = kwargs.pop('headers')
        except KeyError:
            return {}
        if headers is None:
            return {}
        return headers.copy()

    async def _get_authorization_header(self, access_token: str | None) -> str:
        if access_token is None:
            access_token = await self.get_access_token()
        return 'token %s' % access_token

    def _get_resource_url(self, resource: str) -> str:
        if resource.startswith(("http://", "https://")):
            return resource
        elif resource.startswith("/"):
            return self.base_url[:-1] + resource
        else:
            return self.base_url + resource

    async def request(self, method, resource, all_pages=False, **kwargs) -> Dict[str, Any] | Response:
        """
        Makes a request to the given endpoint.
        Keyword arguments are passed to the :meth:`~requests.request` method.

        If the content type of the response is JSON, it will be decoded
        automatically and a dictionary will be returned.
        For that it will follow any pagination of the GitHub api.

        Otherwise, the :class:`~requests.Response` object is returned.

        """
        response = await self.raw_request(method, resource, **kwargs)

        if not is_valid_response(response):
            raise GitHubError(response)

        if is_json_response(response):
            result = response.json()
            while all_pages and response.links.get('next'):
                url = response.links['next']['url']
                response = await self.raw_request(method, url, **kwargs)
                if not is_valid_response(response) or \
                        not is_json_response(response):
                    raise GitHubError(response)
                body = response.json()
                if isinstance(body, list):
                    result += body
                elif isinstance(body, dict) and 'items' in body:
                    result['items'] += body['items']
                else:
                    raise GitHubError(response)
            return result
        else:
            return response

    async def get(self, resource: str, params=None, **kwargs) -> Dict[str, Any] | Response:
        """Shortcut for ``request('GET', resource)``."""
        return await self.request('GET', resource, params=params, **kwargs)

    async def post(self, resource: str, data=None, **kwargs) -> Dict[str, Any] | Response:
        """
        Shortcut for ``request('POST', resource)``.

        Use this to make POST requests, since it will also encode ``data`` to
        'application/json' format.
        """
        headers = dict(kwargs.pop('headers', {}))
        headers.setdefault('Content-Type', 'application/json')
        data = json.dumps(data)
        return await self.request('POST', resource, headers=headers,
                            data=data, **kwargs)

    async def head(self, resource: str, **kwargs) -> Dict[str, Any] | Response:
        """Shortcut for ``request('HEAD', resource)``."""
        return await self.request('HEAD', resource, **kwargs)

    async def patch(self, resource: str, data=None, **kwargs) -> Dict[str, Any] | Response:
        """
        Shortcut for ``request('PATCH', resource)``.

        Use this to make POST requests, since it will also encode ``data`` to
        'application/json' format.
        """
        headers = dict(kwargs.pop('headers', {}))
        headers.setdefault('Content-Type', 'application/json')
        data = json.dumps(data)
        return await self.request('PATCH', resource, headers=headers,
                            data=data, **kwargs)

    async def put(self, resource: str, data=None, **kwargs) -> Dict[str, Any] | Response:
        """
        Shortcut for ``request('PUT', resource)``.

        Use this to make POST requests, since it will also encode ``data`` to
        'application/json' format.
        """
        headers = dict(kwargs.pop('headers', {}))
        headers.setdefault('Content-Type', 'application/json')
        data = json.dumps(data)
        return await self.request('PUT', resource, headers=headers,
                            data=data, **kwargs)

    async def delete(self, resource: str, **kwargs) -> Dict[str, Any] | Response:
        """Shortcut for ``request('HEAD', resource)``."""
        return await self.request('DELETE', resource, **kwargs)
