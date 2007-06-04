#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass)

    
def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    print >> out_file, "#include \"foo.h\""

    mod = Module('foo')

    Foo = CppClass('Foo')
    mod.add_class(Foo)
    Foo.add_constructor(
        CppConstructor([Parameter.new('std::string', 'datum')]))
    Foo.add_method(CppMethod(ReturnValue.new('std::string'), 'get_datum', []))
    

    Bar = CppClass('Bar', parent=Foo)
    mod.add_class(Bar)


    ## Zbr is a reference counted class
    Zbr = CppClass('Zbr', incref_method='Ref', decref_method='Unref')
    mod.add_class(Zbr)
    Zbr.add_constructor(
        CppConstructor([Parameter.new('std::string', 'datum')]))
    Zbr.add_method(CppMethod(ReturnValue.new('std::string'), 'get_datum', []))
    
    

    mod.add_function(Function(ReturnValue.new('int'), 'print_something',
                              [Parameter.new('const char*', 'message')]))
    mod.add_function(Function(ReturnValue.new('int'), 'print_something_else',
                              [Parameter.new('const char*', 'message2')]))



    SomeObject = CppClass('SomeObject')
    SomeObject.add_method(CppMethod(ReturnValue.new('int'), 'add_prefix',
                                    [Parameter.new('std::string&', 'message',
                                               direction=Parameter.DIRECTION_INOUT)]))
    SomeObject.add_constructor(
        CppConstructor([Parameter.new('std::string', 'prefix')]))

    SomeObject.add_method(CppMethod(ReturnValue.new('void'),
                                    'set_foo_value',
                                    [Parameter.new('Foo', 'foo')]))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('Foo'), 'get_foo_value', []))

    SomeObject.add_method(CppMethod(ReturnValue.new('void'),
                                    'set_foo_ptr',
                                    [Parameter.new('Foo*', 'foo', transfer_ownership=True)]))
    SomeObject.add_method(CppMethod(ReturnValue.new('void'),
                                    'set_foo_shared_ptr',
                                    [Parameter.new('Foo*', 'foo', transfer_ownership=False)]))

    SomeObject.add_method(CppMethod(
        ReturnValue.new('Foo*', caller_owns_return=False), 'get_foo_shared_ptr', []))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('Foo*', caller_owns_return=True), 'get_foo_ptr', []))

    SomeObject.add_method(CppMethod(
        ReturnValue.new('void'), 'set_foo_by_ref',
        [Parameter.new('Foo&', 'foo', direction=Parameter.DIRECTION_IN)]))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('void'), 'get_foo_by_ref',
        [Parameter.new('Foo&', 'foo', direction=Parameter.DIRECTION_OUT)]))

    ## get/set recfcounted object Zbr
    SomeObject.add_method(CppMethod(
        ReturnValue.new('Zbr*', caller_owns_return=True), 'get_zbr', []))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('Zbr*', caller_owns_return=False), 'peek_zbr', []))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('void'), 'set_zbr_transfer',
        [Parameter.new('Zbr*', 'zbr', transfer_ownership=True)]))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('void'), 'set_zbr_shared',
        [Parameter.new('Zbr*', 'zbr', transfer_ownership=False)]))

    mod.add_class(SomeObject)

    mod.generate(FileCodeSink(out_file))


if __name__ == '__main__':
    my_module_gen(sys.stdout)

