#!/usr/bin/env python
from wutils import get_version, generate_version_py

from distutils.core import setup

generate_version_py()

setup(name='PyBindGen',
      version=get_version(),
      description='Python Bindings Generator',
      author='Gustavo Carneiro',
      author_email='gjcarneiro@gmail.com',
      url='https://launchpad.net/pybindgen',
      packages=['pybindgen', 'pybindgen.typehandlers', 'pybindgen.typehandlers.ctypeparser'],
     )

