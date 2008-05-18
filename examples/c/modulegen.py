#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)


def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('c')
    mod.add_include('"c.h"')

    C = mod.add_class('C')
    C.add_constructor(CppConstructor([]))
    C.add_constructor(CppConstructor([Parameter.new('uint32_t', 'c')]))
    C.add_method(CppMethod('DoA', ReturnValue.new('void'), [], is_static=True))
    C.add_method(CppMethod('DoB', ReturnValue.new('void'), []))
    C.add_method(CppMethod('DoC', ReturnValue.new('void'), [Parameter.new('uint32_t', 'c')]))
    C.add_method(CppMethod('DoD', ReturnValue.new('uint32_t'), []))
    C.add_method(CppMethod('DoE', ReturnValue.new('void'), [], is_virtual=True))

    mod.generate(FileCodeSink(out_file) )

if __name__ == '__main__':
    my_module_gen(sys.stdout)
