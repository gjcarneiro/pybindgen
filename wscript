## -*- python -*-
## (C) 2007 Gustavo J. A. M. Carneiro

import Params

VERSION='0.1'

APPNAME='pybindgen'
srcdir = '.'
blddir = 'build'

def set_options(opt):
    opt.sub_options('tests')

def configure(conf):
    conf.sub_config('tests')

def build(bld):
    if Params.g_commands['check']:
        bld.add_subdirs('tests')

