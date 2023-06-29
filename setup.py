"""
GitHub-Quart
------------

Adds support to authorize users with GitHub and make API requests with Quart.

Links
`````

* `documentation <http://github-quart.readthedocs.org>`_
* `development version
  <http://github.com/cenkalti/github-quart/zipball/master#egg=GitHub-Quart-dev>`_

"""
import os
import re
from setuptools import setup


def read(*fname):
    path = os.path.join(os.path.dirname(__file__), *fname)
    with open(path) as f:
        return f.read()


def get_version():
    for line in read('quart_github.py').splitlines():
        m = re.match(r"__version__\s*=\s'(.*)'", line)
        if m:
            return m.groups()[0].strip()
    raise Exception('Cannot find version')


setup(
    name='GitHub-Quart',
    version=get_version(),
    url='http://github.com/luckydonald/github-quart',
    license='MIT',
    author='Cenk Alti',
    author_email='github-quart+code@luckydonald.de',
    description='GitHub extension for Quart microframework',
    long_description=__doc__,
    py_modules=['quart_github'],
    test_suite='test_quart_github',
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'quart',
        'httpx',
    ],
    tests_require=['mock'],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
