#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (FileCodeSink)

import foomodulegen_split
import foomodulegen_common




def my_module_gen():
    out = FileCodeSink(sys.stdout)
    root_module = foomodulegen_split.module_init()

    foomodulegen_split.register_types(root_module)
    foomodulegen_split.register_methods(root_module)
    foomodulegen_split.register_functions(root_module)
    foomodulegen_common.customize_module(root_module)

    pybindgen.write_preamble(out)
    root_module.generate(out)


if __name__ == '__main__':
    try:
        import cProfile as profile
    except ImportError:
        my_module_gen()
    else:
        print >> sys.stderr, "** running under profiler"
        profile.run('my_module_gen()', 'foomodulegen4.pstat')

