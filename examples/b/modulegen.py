#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)


def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('b')
    mod.add_include('"b.h"')

    B = mod.add_class('B')
    B.add_constructor(CppConstructor([]))
    B.add_instance_attribute(ReturnValue.new('uint32_t'), 'b_a')
    B.add_instance_attribute(ReturnValue.new('uint32_t'), 'b_b')

    mod.add_function(Function('BDoA', ReturnValue.new('void'), [Parameter.new('B', 'b')]))
    mod.add_function(Function('BDoB', ReturnValue.new('B'), []))

    mod.generate(FileCodeSink(out_file) )

if __name__ == '__main__':
    my_module_gen(sys.stdout)
