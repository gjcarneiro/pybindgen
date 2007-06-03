#! /usr/bin/env python

import sys

from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass)

    
def my_module_gen(out_file):
    print >> out_file, "#include <Python.h>"
    print >> out_file, "#include \"foo.h\""

    mod = Module('foo')

    Foo = CppClass('Foo')
    mod.add_class(Foo)
    Foo.add_constructor(
        CppConstructor([Parameter('std::string', 'datum')]))
    Foo.add_method(CppMethod(ReturnValue('std::string'), 'get_datum', []))
    
    Bar = CppClass('Bar', parent=Foo)
    mod.add_class(Bar)
    

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

    SomeObject.add_method(CppMethod(ReturnValue('void'),
                                    'set_foo_value',
                                    [Parameter('Foo', 'foo')]))
    SomeObject.add_method(CppMethod(
        ReturnValue('Foo'), 'get_foo_value', []))

    SomeObject.add_method(CppMethod(ReturnValue('void'),
                                    'set_foo_ptr',
                                    [Parameter('Foo*', 'foo', transfer_ownership=True)]))
    SomeObject.add_method(CppMethod(ReturnValue('void'),
                                    'set_foo_shared_ptr',
                                    [Parameter('Foo*', 'foo', transfer_ownership=False)]))

    SomeObject.add_method(CppMethod(
        ReturnValue('Foo*', caller_owns_return=False), 'get_foo_shared_ptr', []))
    SomeObject.add_method(CppMethod(
        ReturnValue('Foo*', caller_owns_return=True), 'get_foo_ptr', []))

    mod.add_class(SomeObject)

    mod.generate(FileCodeSink(out_file))


if __name__ == '__main__':
    my_module_gen(sys.stdout)

