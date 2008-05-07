#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)

def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    mod = Module('g')
    mod.add_include('"g.h"')

    mod.add_function(Function(ReturnValue.new('void'), 'GDoA', []))
    G = mod.add_cpp_namespace("G")
    G.add_function(Function(ReturnValue.new('void'), 'GDoB', []))
    GInner = G.add_cpp_namespace("GInner")
    GInner.add_function(Function(ReturnValue.new('void'), 'GDoC', []))

    mod.generate(FileCodeSink(out_file))

if __name__ == '__main__':
    my_module_gen(sys.stdout)
