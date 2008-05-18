#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)


def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('f')
    mod.add_include('"f.h"')

    FBase = mod.add_class('FBase', allow_subclassing=True)
    
    FBase.add_constructor(CppConstructor([]))
    FBase.add_method(CppMethod('DoA', ReturnValue.new('void'), [], is_virtual=True, is_pure_virtual=True))
    FBase.add_method(CppMethod('PrivDoB', ReturnValue.new('void'), [], is_virtual=True, is_pure_virtual=True, visibility='private'))
    FBase.add_method(CppMethod('DoB', ReturnValue.new('void'), []))

    mod.generate(FileCodeSink(out_file) )

if __name__ == '__main__':
    my_module_gen(sys.stdout)
