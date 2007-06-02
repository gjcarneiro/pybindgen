## -*- python -*-
## (C) 2007 Gustavo J. A. M. Carneiro

import Params
from Params import fatal
import Utils
import os
import pproc as subprocess
import shutil
import sys

os.environ['PYTHONPATH'] = os.path.join(os.getcwd(), 'build', 'default')


def get_version_from_bzr(path=None):
    import bzrlib.tag, bzrlib.branch
    if path is None:
        path = os.getcwd()
    branch = bzrlib.branch.Branch.open('file://' + os.path.abspath(path))
    tags = bzrlib.tag.BasicTags(branch)
    current_rev = branch.last_revision()
    for tag, revid in tags.get_tag_dict().iteritems():
        if revid == current_rev:
            return str(tag)
    return str("bzr_r%i" % (branch.revno(),))


def get_version():
    try:
        return get_version_from_bzr()
    except ImportError:
        return 'unknown'

APPNAME='pybindgen'
srcdir = '.'
blddir = 'build'

def dist_hook(srcdir, blddir):
    subprocess.Popen([os.path.join(srcdir, "generate-ChangeLog")],  shell=True).wait()
    try:
        os.chmod(os.path.join(blddir, "ChangeLog"), 0644)
    except OSError:
        pass
    shutil.copy(os.path.join(srcdir, "ChangeLog"), blddir)

    ## Write a pybindgen/version.py file containing the project version
    version = get_version_from_bzr(srcdir)
    version_lst = version.split('.')
    dest = open(os.path.join('pybindgen', 'version.py'), 'w')
    if len(version_lst) > 1:
        dest.write('__version__ = (%s)\n' % (', '.join(version.split('.')),))
    else:
        dest.write('__version__ = "%s"\n' % (version,))
    dest.close()

    ## Copy it to the source dir
    shutil.copy(os.path.join('pybindgen', 'version.py'), os.path.join(srcdir, "pybindgen"))

    ## Copy WAF to the distdir
    assert os.path.basename(sys.argv[0]) == 'waf'
    shutil.copy(sys.argv[0], '.')


def set_options(opt):
    opt.tool_options('python')
    opt.tool_options('compiler_cxx')


def configure(conf):
    conf.check_tool('misc')
    if not conf.check_tool('compiler_cxx'):
        fatal("Error: no C compiler was found in PATH.")
    if not (conf.check_tool('python')
            and conf.check_python_version((2,4,2))
            and conf.check_python_headers()):
        fatal("Error: missing Python development environment.\n"
              "(Hint: if you do not have a debugging Python library installed"
              " try using the configure option '--debug-level release')")


def build(bld):
    if Params.g_commands['check']:
        bld.add_subdirs('tests')
    bld.add_subdirs('examples')
    bld.add_subdirs('pybindgen')

