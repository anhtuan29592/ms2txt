import io
from os.path import abspath, dirname, join

from setuptools import find_packages, setup

HERE = abspath(dirname(__file__))

EXCLUDE_FROM_PACKAGES = [
    '*.tests',
    '*.tests.*',
    'tests.*',
    'tests',
]

INSTALL_REQUIRES = [
]


setup(
    name='ms2txt',
    version='0.0.1.dev0',
    packages=find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    include_package_data=True,
    author='Tuan Nguyen',
    author_email='anhtuan29592@gmail.com',
    description='Metastock data viewer & parser',
    license='BSD',
    keywords='Metastock data viewer & parser',
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    classifiers=[
        'Development Status :: 4 - Beta'
        'Intended Audience :: Developers',
        'License :: Other/Proprietary License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    entry_points={
        'console_scripts': [
            'ms2txt = ms2txt:main'
        ]
    },
)
