#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)

def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('g')
    mod.add_include('"g.h"')

    mod.add_function(Function('GDoA', ReturnValue.new('void'), []))
    G = mod.add_cpp_namespace("G")
    G.add_function(Function('GDoB', ReturnValue.new('void'), []))
    GInner = G.add_cpp_namespace("GInner")
    GInner.add_function(Function('GDoC', ReturnValue.new('void'), []))

    mod.generate(FileCodeSink(out_file))

if __name__ == '__main__':
    my_module_gen(sys.stdout)
