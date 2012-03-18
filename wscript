## -*- python -*-
## (C) 2007-2012 Gustavo J. A. M. Carneiro

from waflib import Options
from waflib import Build

import Scripting
# Scripting.excludes.remove('Makefile')
Scripting.dist_format = 'zip'

from waflib import Configure
#Configure.autoconfig = True

from waflib import Logs

#from Params import fatal

import os
import subprocess
import shutil
import sys
import Configure
import tarfile
import re
import types

#import Task
#Task.file_deps = Task.extract_deps


APPNAME='pybindgen'
top = '.'
out = 'build'



## Add the pybindgen dir to PYTHONPATH, so that the examples and tests are properly built before pybindgen is installed.
if 'PYTHONPATH' in os.environ:
    os.environ['PYTHONPATH'] = os.pathsep.join([os.getcwd(), os.environ['PYTHONPATH']])
else:
    os.environ['PYTHONPATH'] = os.getcwd()


def _get_version_from_bzr_lib(path):
    import bzrlib.tag, bzrlib.branch
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


def _get_version_from_bzr_command(path):
    # get most recent tag first
    most_recent_tag = None
    proc = subprocess.Popen(['bzr', 'log', '--short'], stdout=subprocess.PIPE)
    reg = re.compile('{([0-9]+)\.([0-9]+)\.([0-9]+)}')
    for line in proc.stdout:
        result = reg.search(line)
        if result is not None:
            most_recent_tag = [int(result.group(1)), int(result.group(2)), int(result.group(3))]
            break
    proc.stdout.close()
    proc.wait()
    assert most_recent_tag is not None
    # get most recent revno
    most_recent_revno = None
    proc = subprocess.Popen(['bzr', 'revno'], stdout=subprocess.PIPE)
    most_recent_revno = int(proc.stdout.read().strip())
    proc.wait()
    version = most_recent_tag + [most_recent_revno]
    return version
    

_version = None
def get_version_from_bzr(path):
    global _version
    if _version is not None:
        return _version
    try:
        import bzrlib.tag, bzrlib.branch
    except ImportError:
        return _get_version_from_bzr_command(path)
    else:
        return _get_version_from_bzr_lib(path)

    
def get_version(path=None):
    if path is None:
        path = srcdir
    try:
        return '.'.join([str(x) for x in get_version_from_bzr(path)])
    except ImportError:
        return 'unknown'

def generate_version_py(force=False, path=None):
    """generates pybindgen/version.py, unless it already exists"""

    filename = os.path.join('pybindgen', 'version.py')
    if not force and os.path.exists(filename):
        return

    if path is None:
        path = srcdir
    version = get_version_from_bzr(path)
    dest = open(filename, 'w')
    if isinstance(version, list):
        dest.write('__version__ = %r\n' % (version,))
        dest.write('"""[major, minor, micro, revno], '
                   'revno omitted in official releases"""\n')
    else:
        dest.write('__version__ = "%s"\n' % (version,))
    dest.close()
    

# http://coreygoldberg.blogspot.com/2009/07/python-zip-directories-recursively.html
def zipper(dir, zip_file, archive_main_folder=None):
    import zipfile
    zip = zipfile.ZipFile(zip_file, 'w', compression=zipfile.ZIP_DEFLATED)
    root_len = len(os.path.abspath(dir))
    for root, dirs, files in os.walk(dir):
        archive_root = os.path.abspath(root)[root_len:]
        for f in files:
            fullpath = os.path.join(root, f)
            archive_name = os.path.join(archive_root, f)
            if archive_main_folder is not None:
                if archive_name.startswith(os.sep):
                    n = archive_name[len(os.sep):]
                else:
                    n = archive_name
                archive_name = os.path.join(archive_main_folder, n)
            zip.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)
    zip.close()


def dist_hook():
    blddir = '../build'
    srcdir = '..'
    version = get_version(srcdir)
    subprocess.Popen([os.path.join(srcdir, "generate-ChangeLog")],  shell=True).wait()
    try:
        os.chmod(os.path.join(srcdir, "ChangeLog"), 0644)
    except OSError:
        pass
    try:
        os.unlink("ChangeLog")
    except OSError:
        pass
    shutil.copy(os.path.join(srcdir, "ChangeLog"), '.')

    ## Write a pybindgen/version.py file containing the project version
    generate_version_py(force=True, path=srcdir)

    ## Copy it to the source dir
    shutil.copy(os.path.join('pybindgen', 'version.py'), os.path.join(srcdir, "pybindgen"))

    ## Package the api docs in a separate tarball
    apidocs = 'apidocs'
    if not os.path.isdir('doc/_build/html'):
        Logs.warn("Not creating docs archive: the `doc/_build/html' directory does not exist")
    else:
        zipper('doc/_build/html', os.path.join("..", "pybindgen-%s-docs.zip" % version))

    # clean up the docs dir
    r = subprocess.Popen(["make", "clean"], cwd='doc').wait()
    if r:
        raise SystemExit(r)

    shutil.rmtree('.shelf', True)

    try:
        os.unlink('waf-light')
    except OSError:
        pass


def options(opt):
    opt.tool_options('python')
    opt.tool_options('compiler_cc')
    opt.tool_options('compiler_cxx')
    opt.tool_options('cflags', tooldir="waf-tools")
    opt.sub_options('examples')


    optgrp = opt.add_option_group("PyBindGen Options")

    if os.path.isdir(".bzr"):
        optgrp.add_option('--generate-version',
                          help=('Generate a new pybindgen/version.py file from version control'
                                ' introspection.  Only works from a bzr checkout tree, and is'
                                ' meant to be used by pybindgen developers only.'),
                          action="store_true", default=False,
                          dest='generate_version')

    optgrp.add_option('--examples',
                      help=('Compile the example programs.'),
                      action="store_true", default=False,
                      dest='examples')

    optgrp.add_option('--disable-pygccxml',
                      help=('Disable pygccxml for unit tests / examples.'),
                      action="store_true", default=False,
                      dest='disable_pygccxml')

    optgrp.add_option('--valgrind',
                      help=('Run unit tests through valgrind.'),
                      action="store_true", default=False,
                      dest='valgrind')



def _check_compilation_flag(conf, flag, mode='cxx', linkflags=None):
    """
    Checks if the C++ compiler accepts a certain compilation flag or flags
    flag: can be a string or a list of strings
    """
    l = []
    if flag:
        l.append(flag)
    if isinstance(linkflags, list):
        l.extend(linkflags)
    else:
        if linkflags:
            l.append(linkflags)
    if len(l) > 1:
        flag_str = 'flags ' + ' '.join(l)
    else:
        flag_str = 'flag ' + ' '.join(l)
    if flag_str > 28:
        flag_str = flag_str[:28] + "..."

    conf.start_msg('Checking for compilation %s support' % (flag_str,))
    env = conf.env.copy()

    if mode == 'cc':
        mode = 'c'

    if mode == 'cxx':
        fname = 'test.cc'
        env.append_value('CXXFLAGS', flag)
    else:
        fname = 'test.c'
        env.append_value('CFLAGS', flag)

    if linkflags is not None:
        env.append_value("LINKFLAGS", linkflags)

    try:
        retval = conf.run_c_code(code='#include <stdio.h>\nint main() { return 0; }\n',
                                 env=env, compile_filename=fname,
                                 features=[mode, mode+'program'], execute=False)
    except Configure.ConfigurationError:
        ok = False
    else:
        ok = (retval == 0)
    conf.end_msg(ok)
    return ok



def configure(conf):

    conf.check_compilation_flag = types.MethodType(_check_compilation_flag, conf)

    ## Write a pybindgen/version.py file containing the project version
    generate_version_py()

    conf.check_tool('command', tooldir="waf-tools")
    conf.check_tool('python')
    conf.check_python_version((2,3))

    try:
        conf.check_tool('compiler_cc')
        conf.check_tool('compiler_cxx')
    except Configure.ConfigurationError:
        Logs.warn("C/C++ compiler not detected.  Unit tests and examples will not be compiled.")
        conf.env['CXX'] = ''
    else:
        conf.check_tool('cflags')
        conf.check_python_headers()

        if not Options.options.disable_pygccxml:
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

        # -fvisibility=hidden optimization
        if (conf.env['CXX_NAME'] == 'gcc' and [int(x) for x in conf.env['CC_VERSION']] >= [4,0,0]
            and conf.check_compilation_flag('-fvisibility=hidden')):
            conf.env.append_value('CXXFLAGS_PYEXT', '-fvisibility=hidden')
            conf.env.append_value('CCFLAGS_PYEXT', '-fvisibility=hidden')

        # Add include path for our stdint.h replacement, if needed (pstdint.h)
        if not conf.check(header_name='stdint.h'):
            conf.env.append_value('CPPPATH', os.path.join(conf.curdir, 'include'))

    conf.sub_config('benchmarks')
    conf.sub_config('examples')


def build(bld):
    #global g_bld
    #g_bld = bld
    if getattr(Options.options, 'generate_version', False):
        generate_version_py(force=True)

    bld.add_subdirs('pybindgen')

    if bld.cmd == 'check':
        bld.add_subdirs('tests')


    if 0: # FIXME
        if Options.options.examples:
            bld.add_subdirs('examples')

        if Options.commands.get('bench', False) or Options.commands['clean']:
            bld.add_subdirs('benchmarks')


check_context = Build.BuildContext
def bench(bld):
    "run the benchmarks; requires many tools, used by maintainers only"
    Scripting.build(bld)
    env = g_bld.env

    print "Running benchmarks..."
    retval = subprocess.Popen([env['PYTHON'], '-O', 'benchmarks/bench.py',
                               "build/default/benchmarks/results.xml", ' '.join(env['CXXFLAGS_PYEXT'] + env['CXXFLAGS'])]).wait()
    if retval:
        raise SystemExit(retval)

    print "Generating benchmarks report..."
    retval = subprocess.Popen([env['PYTHON'], '-O', 'benchmarks/plotresults.py',
                               "build/default/benchmarks/results.xml",
                               "build/default/benchmarks/results"]).wait()
    if retval:
        raise SystemExit(retval)


from waflib import Context, Build
class CheckContext(Context.Context):
    """run the unit tests"""
    cmd = 'check'

    def execute(self):

        # first we execute the build
	bld = Context.create_context("build")
	bld.options = Options.options # provided for convenience
	bld.cmd = "check"
	bld.execute()


        if Options.options.verbose:
            verbosity = ['-v']
        else:
            verbosity = []

        if Options.options.valgrind:
            valgrind = ['valgrind', '--leak-check=full', '--leak-resolution=low']
        else:
            valgrind = []

        print "Running pure python unit tests..."
        python = bld.env['PYTHON'][0]
        retval1 = subprocess.Popen([python, 'tests/test.py'] + verbosity).wait()

        env = bld.env

        if env['CXX']:
            print "Running manual module generation unit tests (module foo)..."
            retval2 = subprocess.Popen(valgrind + [python, 'tests/footest.py', '1'] + verbosity).wait()
        else:
            print "Skipping manual module generation unit tests (no C/C++ compiler)..."
            retval2 = 0

        if env['ENABLE_PYGCCXML']:
            print "Running automatically scanned module generation unit tests (module foo2)..."
            retval3 = subprocess.Popen(valgrind + [python, 'tests/footest.py', '2'] + verbosity).wait()

            print "Running module generated by automatically generated python script unit tests (module foo3)..."
            retval3b = subprocess.Popen(valgrind + [python, 'tests/footest.py', '3'] + verbosity).wait()

            print "Running module generated by generated and split python script unit tests  (module foo4)..."
            retval3c = subprocess.Popen(valgrind + [python, 'tests/footest.py', '4'] + verbosity).wait()

            print "Running semi-automatically scanned c-hello module ('hello')..."
            retval4 = subprocess.Popen(valgrind + [python, 'tests/c-hello/hellotest.py'] + verbosity).wait()
        else:
            print "Skipping automatically scanned module generation unit tests (pygccxml missing)..."
            print "Skipping module generated by automatically generated python script unit tests (pygccxml missing)..."
            print "Skipping module generated by generated and split python script unit tests  (pygccxml missing)..."
            print "Skipping semi-automatically scanned c-hello module (pygccxml missing)..."
            retval3 = retval3b = retval3c = retval4 = 0

        if retval1 or retval2 or retval3 or retval3b or retval3c or retval4:
            Logs.error("Unit test failures")
            raise SystemExit(2)


def docs(ctx):
    "generate API documentation, using epydoc"
    generate_version_py(force=True)
    retval = subprocess.Popen(["make", "html"], cwd='doc').wait()
    if retval:
        Logs.error("make returned with code %i" % retval)
        raise SystemExit(2)


#
# FIXME: Remove this when upgrading beyond WAF 1.6.11; this here is
# only to fix a bug in WAF...
#
from waflib.Tools import python
from waflib import TaskGen
@TaskGen.feature('pyext')
@TaskGen.before_method('propagate_uselib_vars', 'apply_link')
@TaskGen.after_method('apply_bundle')
def init_pyext(self):
    """
    Change the values of *cshlib_PATTERN* and *cxxshlib_PATTERN* to remove the
    *lib* prefix from library names.
    """
    self.uselib = self.to_list(getattr(self, 'uselib', []))
    if not 'PYEXT' in self.uselib:
        self.uselib.append('PYEXT')
    # override shlib_PATTERN set by the osx module
    self.env['cshlib_PATTERN'] = self.env['cxxshlib_PATTERN'] = self.env['macbundle_PATTERN'] = self.env['pyext_PATTERN']

    try:
        if not self.install_path:
            return
    except AttributeError:
        self.install_path = '${PYTHONARCHDIR}'
