#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)


def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('f')
    mod.add_include('"f.h"')

    FBase = CppClass('FBase', allow_subclassing=True)
    mod.add_class(FBase)
    
    FBase.add_constructor(CppConstructor([]))
    FBase.add_method(CppMethod(ReturnValue.new('void'), 'DoA', [], is_virtual=True, is_pure_virtual=True))
    FBase.add_method(CppMethod(ReturnValue.new('void'), 'PrivDoB', [], is_virtual=True, is_pure_virtual=True, visibility='private'))
    FBase.add_method(CppMethod(ReturnValue.new('void'), 'DoB', []))

    mod.generate(FileCodeSink(out_file) )

if __name__ == '__main__':
    my_module_gen(sys.stdout)
