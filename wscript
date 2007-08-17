## -*- python -*-
## (C) 2007 Gustavo J. A. M. Carneiro

import Params
from Params import fatal
import os
import pproc as subprocess
import shutil
import sys

os.environ['PYTHONPATH'] = os.path.join(os.getcwd(), 'build', 'default')


_version = None
def get_version_from_bzr(path=None):
    global _version
    if _version is not None:
        return _version
    import bzrlib.tag, bzrlib.branch
    if path is None:
        path = os.getcwd()
    branch = bzrlib.branch.Branch.open('file://' + os.path.abspath(path))
    tags = bzrlib.tag.BasicTags(branch)
    #print "Getting version information from bzr branch..."
    history = branch.revision_history()
    history.reverse()
    ## find closest tag
    version = None
    extra_version = []
    for revid in history:
        #print revid
        for tag_name, tag_revid in tags.get_tag_dict().iteritems():
            if tag_revid == revid:
                #print "%s matches tag %s" % (revid, tag_name)
                version = [int(s) for s in tag_name.split('.')]
                ## if the current revision does not match the last
                ## tag, we append current revno to the version
                if tag_revid != branch.last_revision():
                    extra_version = [branch.revno()]
                break
        if version:
            break
    assert version is not None
    _version = version + extra_version
    return _version


def get_version():
    try:
        return '.'.join([str(x) for x in get_version_from_bzr()])
    except ImportError:
        return 'unknown'

APPNAME='pybindgen'
srcdir = '.'
blddir = 'build'

def generate_version_py(force=False):
    """generates pybindgen/version.py, unless it already exists"""

    filename = os.path.join('pybindgen', 'version.py')
    if not force and os.path.exists(filename):
        return

    version = get_version_from_bzr(srcdir)
    dest = open(filename, 'w')
    if isinstance(version, list):
        dest.write('# [major, minor, micro, revno], '
                   'revno omitted in official releases\n')
        dest.write('__version__ = %r\n' % (version,))
    else:
        dest.write('__version__ = "%s"\n' % (version,))
    dest.close()
    

def dist_hook(srcdir, blddir):
    subprocess.Popen([os.path.join(srcdir, "generate-ChangeLog")],  shell=True).wait()
    try:
        os.chmod(os.path.join(blddir, "ChangeLog"), 0644)
    except OSError:
        pass
    shutil.copy(os.path.join(srcdir, "ChangeLog"), blddir)

    ## Write a pybindgen/version.py file containing the project version
    generate_version_py(force=True)

    ## Copy it to the source dir
    shutil.copy(os.path.join('pybindgen', 'version.py'), os.path.join(srcdir, "pybindgen"))

    ## Copy WAF to the distdir
    assert os.path.basename(sys.argv[0]) == 'waf'
    shutil.copy(sys.argv[0], '.')


def set_options(opt):
    opt.tool_options('python')
    opt.tool_options('compiler_cxx')


def configure(conf):
    ## Write a pybindgen/version.py file containing the project version
    generate_version_py()

    conf.check_tool('misc')
    if not conf.check_tool('compiler_cxx'):
        fatal("Error: no C compiler was found in PATH.")
    if os.path.basename(conf.env['CXX']).startswith("g++"):
        conf.env.append_value('CXXFLAGS', ['-Wall', '-fno-strict-aliasing'])
        if Params.g_options.debug_level == 'ultradebug':
            conf.env.append_value('CXXFLAGS', ['-Wextra'])
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

def shutdown():
    if Params.g_commands['check']:
        if subprocess.Popen(['python', 'examples/footest.py']).wait():
            raise SystemExit(1)
