## -*- python -*-
## (C) 2007 Gustavo J. A. M. Carneiro

import Params
from Params import fatal
import os
import pproc as subprocess
import shutil

def get_version_from_bzr():
    import bzrlib.tag, bzrlib.branch
    branch = bzrlib.branch.Branch.open('file://' + os.getcwd())
    tags = bzrlib.tag.BasicTags(branch)
    current_rev = branch.revision_history()[-1]
    for tag, revid in tags.get_tag_dict().iteritems():
        if revid == current_rev:
            return str(tag)
    return str("bzr_r%i" % (branch.revno(),))


try:
    VERSION = get_version_from_bzr()
except ImportError:
    VERSION = 'unknown'

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

