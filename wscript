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
    history = branch.revision_history()
    history.reverse()
    ## find closest tag
    version = None
    extra_vesion = []
    for revid in history:
        for tag_name, tag_revid in tags.get_tag_dict().iteritems():
            if tag_revid == revid:
                version = [int(s) for s in tag_name.split('.')]
                if tag_revid != branch.last_revision():
                    extra_version = [branch.revision_id_to_revno(revid)]
                break
        if version:
            break
    assert version is not None
    return version + extra_version


def get_version():
    try:
        return '.'.join([str(x) for x in get_version_from_bzr()])
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
    dest = open(os.path.join('pybindgen', 'version.py'), 'w')
    if isinstance(version, list):
        dest.write('# [major, minor, micro, revno], '
                   'revno omitted in official releases\n')
        dest.write('__version__ = %r\n' % (version,))
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

