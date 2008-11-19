## -*- python -*-
## (C) 2007,2008 Gustavo J. A. M. Carneiro

import Params
Params.g_autoconfig = True

from Params import fatal
import os
import pproc as subprocess
import shutil
import sys
import Configure
import tarfile


## Add the pybindgen dir to PYTHONPATH, so that the examples and tests are properly built before pybindgen is installed.
waf_version = [int (s) for s in Params.g_version.split('.')]
if waf_version >= [1,4,1]:
    ## Since WAF 1.4.1, WAF does not byte-compile python files during
    ## build, so we add the source dir instead of the build dir.
    os.environ['PYTHONPATH'] = os.getcwd()
else:
    os.environ['PYTHONPATH'] = os.path.join(os.getcwd(), 'build', 'default')
del waf_version


_version = None
def get_version_from_bzr(path=None):
    global _version
    if _version is not None:
        return _version
    import bzrlib.tag, bzrlib.branch
    if path is None:
        path = os.getcwd()
    
    fullpath = os.path.abspath(path)
    if sys.platform == 'win32':
        fullpath = fullpath.replace('\\', '/')
        fullpath = '/' + fullpath

    branch = bzrlib.branch.Branch.open('file://' + fullpath)
        
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
        dest.write('__version__ = %r\n' % (version,))
        dest.write('"""[major, minor, micro, revno], '
                   'revno omitted in official releases"""\n')
    else:
        dest.write('__version__ = "%s"\n' % (version,))
    dest.close()
    

def dist_hook():
    version = get_version()
    blddir = '../build'
    srcdir = '..'
    subprocess.Popen([os.path.join(srcdir, "generate-ChangeLog")],  shell=True).wait()
    try:
        os.chmod(os.path.join(srcdir, "ChangeLog"), 0644)
    except OSError:
        pass
    shutil.copy(os.path.join(srcdir, "ChangeLog"), '.')

    ## Write a pybindgen/version.py file containing the project version
    generate_version_py(force=True)

    ## Copy it to the source dir
    shutil.copy(os.path.join('pybindgen', 'version.py'), os.path.join(srcdir, "pybindgen"))

    ## Copy WAF to the distdir
    assert os.path.basename(sys.argv[0]) == 'waf'
    shutil.copy(sys.argv[0], '.')

    ## Package the api docs in a separate tarball
    apidocs = 'apidocs'
    if not os.path.isdir('apidocs'):
        Params.warning("Not creating apidocs archive: the `apidocs' directory does not exist")
    else:
        tar = tarfile.open(os.path.join("..", "pybindgen-%s-apidocs.tar.bz2" % version), 'w:bz2')
        tar.add('apidocs', "pybindgen-%s-apidocs" % version)
        tar.close()
        shutil.rmtree('apidocs', True)


def set_options(opt):
    opt.tool_options('python')
    opt.tool_options('compiler_cc')
    opt.tool_options('compiler_cxx')

    optgrp = opt.add_option_group("PyBindGen Options")

    if os.path.isdir(".bzr"):
        optgrp.add_option('--generate-version',
                          help=('Generate a new pybindgen/version.py file from version control'
                                ' introspection.  Only works from a bzr checkout tree, and is'
                                ' meant to be used by pybindgen developers only.'),
                          action="store_true", default=False,
                          dest='generate_version')

    optgrp.add_option('--generate-api-docs',
                      help=('Generate API html documentation, using epydoc.'),
                      action="store_true", default=False,
                      dest='generate_api_docs')

    optgrp.add_option('--examples',
                      help=('Compile the example programs.'),
                      action="store_true", default=False,
                      dest='examples')

    optgrp.add_option('--disable-pygccxml',
                      help=('Disable pygccxml for unit tests / examples.'),
                      action="store_true", default=False,
                      dest='disable_pygccxml')

def configure(conf):
    ## Write a pybindgen/version.py file containing the project version
    generate_version_py()

    conf.check_tool('misc')
    conf.check_tool('python')

    try:
        conf.check_python_module('pygccxml')
        conf.check_tool('compiler_cc')
        conf.check_tool('compiler_cxx')
    except Configure.ConfigurationError:
        Params.warning("C/C++ compiler not detected.  Unit tests and examples will not be compiled.")
        conf.env['CXX'] = ''
    else:
        if os.path.basename(conf.env['CXX']).startswith("g++"):
            conf.env.append_value('CXXFLAGS', ['-Wall', '-fno-strict-aliasing'])
            if Params.g_options.debug_level == 'ultradebug':
                conf.env.append_value('CXXFLAGS', ['-Wextra'])
        conf.check_python_version((2,3))
        conf.check_python_headers()

        if not Params.g_options.disable_pygccxml:
            gccxml = conf.find_program('gccxml')
            if not gccxml:
                conf.env['ENABLE_PYGCCXML'] = False
            else:
                try:
                    conf.check_python_module('pygccxml')
                except Configure.ConfigurationError:
                    conf.env['ENABLE_PYGCCXML'] = False
                else:
                    conf.env['ENABLE_PYGCCXML'] = True


def build(bld):
    if getattr(Params.g_options, 'generate_version', False):
        generate_version_py(force=True)

    bld.add_subdirs('pybindgen')
    if Params.g_options.examples:
        bld.add_subdirs('examples')
    if Params.g_commands['check'] or Params.g_commands['clean']:
        bld.add_subdirs('tests')

def shutdown():
    if Params.g_commands['check']:

        print "Running pure python unit tests..."
        retval1 = subprocess.Popen([Params.g_build.env()['PYTHON'], 'tests/test.py']).wait()

        env = Params.g_build.env()

        if env['CXX']:
            print "Running manual module generation unit tests (module foo)..."
            retval2 = subprocess.Popen([env['PYTHON'], 'tests/footest.py', '1']).wait()
        else:
            print "Skipping manual module generation unit tests (no C/C++ compiler)..."
            retval2 = 0

        if env['ENABLE_PYGCCXML']:
            print "Running automatically scanned module generation unit tests (module foo2)..."
            retval3 = subprocess.Popen([env['PYTHON'], 'tests/footest.py', '2']).wait()

            print "Running module generated by automatically generated python script unit tests (module foo3)..."
            retval3b = subprocess.Popen([env['PYTHON'], 'tests/footest.py', '3']).wait()

            print "Running module generated by generated and split python script unit tests  (module foo4)..."
            retval3c = subprocess.Popen([env['PYTHON'], 'tests/footest.py', '4']).wait()

            print "Running semi-automatically scanned c-hello module ('hello')..."
            retval4 = subprocess.Popen([env['PYTHON'], 'tests/c-hello/hellotest.py']).wait()
        else:
            print "Skipping automatically scanned module generation unit tests (pygccxml missing)..."
            print "Skipping module generated by automatically generated python script unit tests (pygccxml missing)..."
            print "Skipping module generated by generated and split python script unit tests  (pygccxml missing)..."
            print "Skipping semi-automatically scanned c-hello module (pygccxml missing)..."
            retval3 = retval3b = retval3c = retval4 = 0

        if retval1 or retval2 or retval3 or retval3b or retval3c or retval4:
            raise Params.fatal("Unit test failures")

    if Params.g_options.generate_api_docs:
        generate_version_py(force=True)
        retval = subprocess.Popen(["epydoc", "-v", "--html", "--graph=all",  "pybindgen",
                                   "-o", "apidocs",
                                   "--pstat=build/foomodulegen-auto.pstat",
                                   "--pstat=build/foomodulegen.pstat",
                                   "--pstat=build/hellomodulegen.pstat",
                                   "--no-private",
                                   ]).wait()
        if retval:
            raise Params.fatal("epydoc returned with code %i" % retval)

        # Patch the generated CSS file to highlight literal blocks (this is a copy of pre.py-doctest)
        css = open("apidocs/epydoc.css", "at")
        css.write("""
pre.literalblock {  padding: .5em; margin: 1em;
                    background: #e8f0f8; color: #000000;
                    border: 1px solid #708890; }
""")
        css.close()
