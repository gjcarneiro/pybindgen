#! /usr/bin/env python

import sys
import re

import pybindgen
from pybindgen.typehandlers import base as typehandlers
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)
from pybindgen.gccxmlparser import ModuleParser
from pybindgen.function import CustomFunctionWrapper
from pybindgen.cppmethod import CustomCppMethodWrapper

import foomodulegen_common

def my_module_gen():
    out = FileCodeSink(sys.stdout)
    pygen_file = open(sys.argv[2], "wt")
    pybindgen.write_preamble(out)
    module_parser = ModuleParser('foo2', '::')
    module = module_parser.parse([sys.argv[1]], includes=['"foo.h"'], pygen_sink=FileCodeSink(pygen_file))
    pygen_file.close()

    foomodulegen_common.customize_module(module)

    module.generate(out)


if __name__ == '__main__':
    try:
        import cProfile as profile
    except ImportError:
        my_module_gen()
    else:
        print >> sys.stderr, "** running under profiler"
        profile.run('my_module_gen()', 'foomodulegen-auto.pstat')

