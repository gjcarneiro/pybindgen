#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)

def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('a')
    mod.add_include('"a.h"')

    mod.add_function(Function('ADoA', ReturnValue.new('void'), []))
    mod.add_function(Function('ADoB', ReturnValue.new('void'), [Parameter.new('uint32_t', 'b')]))
    mod.add_function(Function('ADoC', ReturnValue.new('uint32_t'), []))

    mod.generate(FileCodeSink(out_file) )

if __name__ == '__main__':
    my_module_gen(sys.stdout)
