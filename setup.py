from setuptools import setup
from setuptools.command.test import test as TestCommand
import pynginx
import io
import sys

__author__ = 'vedran'


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)


def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.md')

setup(
    name='py-nginx',
    version=pynginx.__version__,
    url='http://github.com/vvojvoda/py-nginx/',
    license='The MIT License (MIT)',
    author='Vedran Vojvoda',
    tests_require=['pytest'],
    cmdclass={'test': PyTest},
    author_email='vedran@protobit.hr',
    description='Small utility for controlling nginx configuration from python',
    long_description=long_description,
    packages=['pynginx'],
    include_package_data=True,
    platforms='any',
    #TODO Test suite
    test_suite='test.test_pynginx',
    classifiers = [
        'Programming Language :: Python',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: UNIX',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries :: Utilities',
        ],
    extras_require={
        'testing': ['pytest'],
    }
)