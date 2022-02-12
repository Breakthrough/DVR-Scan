#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Copyright (C) 2014-2022 Brandon Castellano <http://www.bcastell.com>.
#

""" DVR-Scan setup.py

To install DVR-Scan:

    python setup.py install

To run the DVR-Scan unit tests:

    python setup.py test

"""

import sys

from setuptools import setup


if sys.version_info < (2, 7) or (3, 0) <= sys.version_info < (3, 3):
    print('DVR-Scan requires at least Python 2.7 or 3.3 to run.')
    sys.exit(1)


def get_requires():
    # type: () -> List[str]
    """ Get Requires: Returns a list of required packages. """
    requires = ['numpy', 'tqdm']
    return requires


def get_extra_requires():
    # type: () -> Dict[str, List[str]]
    """ Get Extra Requires: Returns a list of extra/optional packages. """
    return {
        'opencv:python_version <= "3.5"':
            ['opencv-python<=4.2.0.32', 'opencv-contrib-python<=4.2.0.32'],
        'opencv:python_version > "3.5"':
            ['opencv-python', 'opencv-contrib-python'],

        'opencv-headless:python_version <= "3.5"':
            ['opencv-python-headless<=4.2.0.32','opencv-contrib-python-headless<=4.2.0.32'],
        'opencv-headless:python_version > "3.5"':
            ['opencv-python-headless', 'opencv-contrib-python-headless'],
    }


setup(
    name='dvr-scan',
    version='1.4.1-dev',
    description="Tool for finding and extracting motion events in video files"
                "(e.g. security camera footage).",
    long_description=open('package-info.rst').read(),
    author='Brandon Castellano',
    author_email='brandon248@gmail.com',
    url='https://github.com/Breakthrough/DVR-Scan',
    license="BSD 2-Clause",
    keywords="video computer-vision analysis",
    install_requires=get_requires(),
    extras_require=get_extra_requires(),
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    packages=['dvr_scan'],
    package_data={'': ['../LICENSE*', '../package-info.rst']},
    #include_package_data = True,   # Only works with this line commented.
    #test_suite="unitest.py",
    entry_points={"console_scripts": ["dvr-scan=dvr_scan.__main__:main"]},
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
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Multimedia :: Video',
        'Topic :: Multimedia :: Video :: Conversion',
        'Topic :: Multimedia :: Video :: Non-Linear Editor',
        'Topic :: Utilities'
    ]
)
