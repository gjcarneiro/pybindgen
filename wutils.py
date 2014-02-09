import os.path
import sys
import subprocess
import re


def _get_version_from_bzr_lib(path):
    import bzrlib.tag, bzrlib.branch
    fullpath = os.path.abspath(path)
    if sys.platform == 'win32':
        fullpath = fullpath.replace('\\', '/')
        fullpath = '/' + fullpath
    branch = bzrlib.branch.Branch.open('file://' + fullpath)
    tags = bzrlib.tag.BasicTags(branch)
    #print "Getting version information from bzr branch..."
    branch.lock_read()
    try:
        history = branch.iter_merge_sorted_revisions(direction="reverse")
        version = None
        extra_version = []
        for revid, depth, revno, end_of_merge in history:
            for tag_name, tag_revid in tags.get_tag_dict().iteritems():
                #print tag_revid, "<==>", revid
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
    finally:
        branch.unlock()
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
    filename = os.path.join(os.path.dirname(__file__), 'pybindgen', 'version.py')
    if os.path.exists(filename):
        # Read the version.py from the version file
        with open(filename, "rt") as versionpy:
            version_data = versionpy.read().strip().split("\n")[0]
            version = eval(version_data.split("=", 1)[1])
            version_str = '.'.join(str(x) for x in version)
            #print version_str
            return version_str
    if path is None:
        path = os.path.dirname(__file__)
    try:
        return '.'.join([str(x) for x in get_version_from_bzr(path)])
    except ImportError:
        return 'unknown'

def generate_version_py(force=False, path=None):
    """generates pybindgen/version.py, unless it already exists"""

    filename = os.path.join(os.path.dirname(__file__), 'pybindgen', 'version.py')
    if not force and os.path.exists(filename):
        return

    if path is None:
        path = os.path.dirname(__file__)
    version = get_version_from_bzr(path)
    dest = open(filename, 'w')
    if isinstance(version, list):
        dest.write('__version__ = %r\n' % (version,))
        dest.write('"""[major, minor, micro, revno], '
                   'revno omitted in official releases"""\n')
    else:
        dest.write('__version__ = "%s"\n' % (version,))
    dest.close()

