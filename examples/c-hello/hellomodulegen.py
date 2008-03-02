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

constructor_rx = re.compile("hello_foo_new(_.*)?")
method_rx = re.compile("hello_foo(_.*)?")

def pre_scan_hook(module_parser,
                  pygccxml_definition,
                  global_annotations,
                  parameter_annotations):
    if pygccxml_definition.name == "_HelloFoo":
        global_annotations['free_function'] = 'hello_foo_unref'
        global_annotations['incref_function'] = 'hello_foo_ref'
        global_annotations['decref_function'] = 'hello_foo_unref'

    ## constructor?
    m = constructor_rx.match(pygccxml_definition.name)
    if m:
        global_annotations['is_constructor_of'] = 'HelloFoo'
        return

    ## method?
    m = method_rx.match(pygccxml_definition.name)
    if m:
        method_name = m.group(1)[1:]
        if method_name in ['ref', 'unref']:
            return
        print >> sys.stderr, ">>>>>>>>", m.group(1)[1:]
        global_annotations['as_method'] = m.group(1)[1:]
        global_annotations['of_class'] = 'HelloFoo'
        parameter_annotations['foo'] = {'transfer_ownership': 'false'}

       
    #print >> sys.stderr, ">>>>>>>>>>>>", pygccxml_definition


def my_module_gen(out_file):
    out = FileCodeSink(out_file)
    pybindgen.write_preamble(out)
    out.writeln("#include \"hello.h\"")
    module_parser = ModuleParser('hello')
    module_parser.add_pre_scan_hook(pre_scan_hook)
    module = module_parser.parse(sys.argv[1:])
    module.generate(out)


if __name__ == '__main__':
    my_module_gen(sys.stdout)

