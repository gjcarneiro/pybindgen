#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import ReturnValue, Parameter, Module, Function, FileCodeSink

def my_module_gen(out_file):
    mod = Module('g')
    mod.add_include('"g.h"')

    mod.add_function('GDoA', None, [])
    G = mod.add_cpp_namespace("G")
    G.add_function('GDoB', None, [])
    GInner = G.add_cpp_namespace("GInner")
    GInner.add_function('GDoC', None, [])

    mod.generate(FileCodeSink(out_file))

if __name__ == '__main__':
    my_module_gen(sys.stdout)
