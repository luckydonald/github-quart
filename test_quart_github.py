import asyncio
import logging
import unittest
import httpx
from mock import patch, Mock

from quart import Quart, request, redirect
from quart_github import GitHub

logger = logging.getLogger(__name__)


class GitHubTestCase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.loop = asyncio.get_running_loop()
    # end if

    @patch.object(httpx.AsyncClient, 'post')
    @patch.object(GitHub, 'BASE_AUTH_URL')
    async def test_authorization(self, auth_url, post):
        def assert_params(*args, **kwargs):
            data = kwargs.pop('data')
            logger.info(f'assert_params(*{args!r}, **{kwargs}')
            self.assertEqual(data['client_id'], '123', "data['client_id'] == '123'")
            self.assertEqual(data['client_secret'], 'SEKRET', "data['client_secret'] == 'SEKRET'")
            self.assertEqual(data['code'], 'KODE', "data['code'] == 'KODE'")
            response = Mock()
            response.content = b'access_token=asdf&token_type=bearer'
            return response
        post.side_effect = assert_params
        auth_url.__get__ = Mock(return_value='http://localhost/oauth/')

        app = Quart(__name__)

        app.config['GITHUB_CLIENT_ID'] = '123'
        app.config['GITHUB_CLIENT_SECRET'] = 'SEKRET'

        github = GitHub(app)

        @app.route('/login')
        async def login():
            logger.info(f'login()')
            return github.authorize(redirect_uri="http://localhost/callback")

        @app.route('/callback')
        @github.authorized_handler
        async def authorized(token):
            logger.info(f'authorized(token={token!r})')
            access_token.append(token)
            return ''

        # Mimics GitHub authorization URL
        # http://developer.github.com/v3/oauth/#web-application-flow
        @app.route('/oauth/authorize')
        async def handle_auth():
            logger.info(f'handle_auth()')
            logger.info("in /oauth/authorize")
            called_auth.append(1)
            self.assertEqual(request.args['client_id'], '123', "request.args['client_id'] == '123'")
            logger.info("client_id OK")
            self.assertEqual(request.args['redirect_uri'], 'http://localhost/callback', "request.args['redirect_uri'] == 'http://localhost/callback'")
            logger.info("redirect_uri OK")
            return redirect(request.args['redirect_uri'] + '?code=KODE')

        access_token = []
        called_auth = []

        client = app.test_client()
        logger.info('CALLING /login')
        await client.get('/login', follow_redirects=True)
        logger.info('CALLED /login')

        self.assertTrue(called_auth)
        self.assertTrue(access_token)
        self.assertEqual(access_token, ['asdf'], "access_token == ['asdf']")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
