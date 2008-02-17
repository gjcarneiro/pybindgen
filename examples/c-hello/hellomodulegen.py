#! /usr/bin/env python

import sys
import re

import pybindgen
from pybindgen.typehandlers import base as typehandlers
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)
from pybindgen.gccxmlparser import ModuleParser
from pybindgen.function import CustomFunctionWrapper
from pybindgen.cppmethod import CustomCppMethodWrapper



def my_module_gen(out_file):
    out = FileCodeSink(out_file)
    pybindgen.write_preamble(out)
    out.writeln("#include \"hello.h\"")
    module_parser = ModuleParser('hello')
    module = module_parser.parse(sys.argv[1:])
    module.generate(out)


if __name__ == '__main__':
    my_module_gen(sys.stdout)

