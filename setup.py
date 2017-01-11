#!/usr/bin/env python
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Installation and build script for DVR-Scan.  To install DVR-Scan in the
# current environment, run:
#
#   > python setup.py install
#
# This will allow you to use the `dvr-scan` command from the terminal or
# command prompt.  When upgrading to a new version, running the above command
# will automatically overwrite any existing older version.
#


import sys

from setuptools import setup


if sys.version_info < (2, 6) or (3, 0) <= sys.version_info < (3, 3):
    print('DVR-Scan requires at least Python 2.6 or 3.3 to run.')
    sys.exit(1)


def get_requires():
    requires = ['numpy']
    if sys.version_info == (2, 6):
        requires += ['argparse']
    return requires


setup(
    name='DVR-Scan',
    version='1.0',
    description="Tool for finding and extracting motion events in video files (e.g. security camera footage).",
    long_description=open('package-info.rst').read(),
    author='Brandon Castellano',
    author_email='brandon248@gmail.com',
    url='https://github.com/Breakthrough/DVR-Scan',
    license="BSD 2-Clause",
    keywords="video computer-vision analysis",
    install_requires=get_requires(),
    extras_require={
        #'GUI': ['gi'],
        #'VIDEOENC': ['moviepy']
    },
    packages=['dvr_scan'],
    package_data={'': ['../LICENSE*', '../package-info.rst']},
    #include_package_data = True,   # Only works with this line commented.
    #test_suite="unitest.py",
    entry_points={"console_scripts": ["dvr-scan=dvr_scan:main"]},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Multimedia :: Video',
        'Topic :: Multimedia :: Video :: Conversion',
        'Topic :: Multimedia :: Video :: Non-Linear Editor',
        'Topic :: Utilities'
    ]
)
