#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages

with open('VERSION') as version_file:
    version = version_file.read().strip()

with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

setup(
    name='atlas_module_qc',
    version=version,
    description='ATLAS Module QC',
    url='https://github.com/SiLab-Bonn/atlas_module_qc',
    license='',
    long_description='',
    author='Yannick Dieter',
    maintainer='Tomasz Hemperek',
    author_email='dieter@physik.uni-bonn.de',
    maintainer_email='dieter@physik.uni-bonn.de',
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    setup_requires=[''],
    platforms='any'
)
