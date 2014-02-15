#!/usr/bin/env python
import sys
import os
from distutils.core import setup

sys.path.insert(0, os.path.dirname(__file__))
from wutils import get_version, generate_version_py
generate_version_py(force=False)

setup(name='PyBindGen',
      version=get_version(),
      description='Python Bindings Generator',
      author='Gustavo Carneiro',
      author_email='gjcarneiro@gmail.com',
      url='https://launchpad.net/pybindgen',
      packages=['pybindgen', 'pybindgen.typehandlers', 'pybindgen.typehandlers.ctypeparser'],
     )

