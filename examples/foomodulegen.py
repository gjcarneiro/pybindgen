#! /usr/bin/env python

import sys

from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass)

    
def my_module_gen(out_file):
    print >> out_file, "#include <Python.h>"
    print >> out_file, "#include \"foo.h\""

    mod = Module('foo')

    mod.add_function(Function(ReturnValue('int'), 'print_something',
                              [Parameter('const char*', 'message')]))

    mod.add_function(Function(ReturnValue('int'), 'print_something_else',
                              [Parameter('const char*', 'message2')]))


    SomeObject = CppClass('SomeObject')
    SomeObject.add_method(CppMethod(ReturnValue('int'), 'add_prefix',
                                    [Parameter('std::string&', 'message',
                                               direction=Parameter.DIRECTION_INOUT)]))
    SomeObject.add_constructor(
        CppConstructor([Parameter('std::string', 'prefix')]))

    mod.add_class(SomeObject)

    mod.generate(FileCodeSink(out_file))


if __name__ == '__main__':
    my_module_gen(sys.stdout)

