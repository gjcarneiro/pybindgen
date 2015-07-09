import os.path
import sys
import subprocess
import re


def get_version(path=None):
    filename = os.path.join(os.path.dirname(__file__), 'pybindgen', 'version.py')
    if os.path.exists(filename):
        # Read the version.py from the version file
        with open(filename, "rt") as versionpy:
            version_data = versionpy.read().strip().split("\n")[0]
            version_str = eval(version_data.split("=", 1)[1]).strip()
            #print version_str
            return version_str
    return 'unknown'

def generate_version_py(force=False, path=None):
    """generates pybindgen/version.py, unless it already exists"""

    filename = os.path.join(os.path.dirname(__file__), 'pybindgen', 'version.py')
    if not force and os.path.exists(filename):
        return

    if path is None:
        path = os.path.dirname(__file__)
    version = subprocess.check_output("git describe --tags".split(' ')).strip()
    dest = open(filename, 'w')
    if isinstance(version, list):
        dest.write('__version__ = %r\n' % (version,))
        dest.write('"""[major, minor, micro, revno], '
                   'revno omitted in official releases"""\n')
    else:
        dest.write('__version__ = "%s"\n' % (version,))
    dest.close()

