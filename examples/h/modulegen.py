#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, CppClass, CppMethod, CppConstructor, FileCodeSink)

def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('h')
    mod.add_include('"h.h"')

    H = CppClass('H')
    mod.add_class(H)
    H.add_constructor(CppConstructor([]))
    H.add_method(CppMethod(ReturnValue.new('void'), 'Do', []))

    Inner = CppClass('Inner', outer_class=H)
    mod.add_class(Inner)
    Inner.add_constructor(CppConstructor([]))
    Inner.add_method(CppMethod (ReturnValue.new('void'), 'Do', []))

    MostInner = CppClass('MostInner', outer_class=Inner)
    mod.add_class (MostInner)
    MostInner.add_constructor (CppConstructor([]))
    MostInner.add_method (CppMethod (ReturnValue.new('void'), 'Do', []))

    mod.generate(FileCodeSink(out_file))

if __name__ == '__main__':
    my_module_gen(sys.stdout)
