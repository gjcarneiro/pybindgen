#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)

def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('a')
    mod.add_include('"a.h"')

    mod.add_function(Function(ReturnValue.new('void'), 'ADoA', []))
    mod.add_function(Function(ReturnValue.new('void'), 'ADoB', [Parameter.new('uint32_t', 'b')]))
    mod.add_function(Function(ReturnValue.new('uint32_t'), 'ADoC', []))

    mod.generate(FileCodeSink(out_file) )

if __name__ == '__main__':
    my_module_gen(sys.stdout)
