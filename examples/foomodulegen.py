#! /usr/bin/env python

import sys
import re

import pybindgen
from pybindgen.typehandlers import base as typehandlers
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass)



class PointerHolderTransformation(typehandlers.TypeTransformation):
    def __init__(self):
        self.rx = re.compile(r'PointerHolder<(\w+)>')

    def get_untransformed_name(self, name):
        m = self.rx.match(name)
        if m is None:
            return None
        else:
            return m.group(1)+'*'

    def create_type_handler(self, type_handler, *args, **kwargs):
        if issubclass(type_handler, Parameter):
            kwargs['transfer_ownership'] = False
        elif issubclass(type_handler, ReturnValue):
            kwargs['caller_owns_return'] = True
        else:
            raise AssertionError
        handler = type_handler(*args, **kwargs)
        handler.set_tranformation(self, self.get_untransformed_name(args[0]))
        return handler

    def untransform(self, type_handler, declarations, code_block, expression):
        return '(%s).thePointer' % (expression,)

    def transform(self, type_handler, declarations, code_block, expression):
        assert type_handler.untransformed_ctype[-1] == '*'
        var = declarations.declare_variable(
            'PointerHolder<%s>' % type_handler.untransformed_ctype[:-1], 'tmp')
        return '(%s.thePointer = (%s), %s)' % (var, expression, var)

transf = PointerHolderTransformation()
typehandlers.return_type_matcher.register_transformation(transf)
typehandlers.param_type_matcher.register_transformation(transf)
del transf



def my_module_gen(out_file):
    pybindgen.write_preamble(FileCodeSink(out_file))

    print >> out_file, "#include \"foo.h\""

    mod = Module('foo')

    Foo = CppClass('Foo', automatic_type_narrowing=True)
    mod.add_class(Foo)
    Foo.add_constructor(
        CppConstructor([Parameter.new('std::string', 'datum')]))
    Foo.add_constructor(CppConstructor([]))
    Foo.add_method(CppMethod(ReturnValue.new('std::string'), 'get_datum', []))
    

    Bar = CppClass('Bar', parent=Foo)
    ## a static method..
    Bar.add_method(CppMethod(ReturnValue.new('std::string'), 'Hooray', [], is_static=True))
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

    ## test overloaded functions
    mod.add_function(Function(ReturnValue.new('int'), 'get_int_from_string',
                              [Parameter.new('const char*', 'from_string')]),
                     name="get_int")
    mod.add_function(Function(ReturnValue.new('int'), 'get_int_from_float',
                              [Parameter.new('double', 'from_float')]),
                     name="get_int")



    SomeObject = CppClass('SomeObject')
    SomeObject.add_instance_attribute(ReturnValue.new('std::string'), 'm_prefix')
    SomeObject.add_static_attribute(ReturnValue.new('std::string'), 'staticData') ## not working correctly
    
    SomeObject.add_method(CppMethod(ReturnValue.new('int'), 'add_prefix',
                                    [Parameter.new('std::string&', 'message',
                                               direction=Parameter.DIRECTION_INOUT)]))
    SomeObject.add_constructor(
        CppConstructor([Parameter.new('std::string', 'prefix')]))
    SomeObject.add_constructor(
        CppConstructor([Parameter.new('int', 'prefix_len')]))

    SomeObject.add_method(CppMethod(
        ReturnValue.new('std::string'), 'get_prefix', []))

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

    ## methods with transformed types
    SomeObject.add_method(CppMethod(
        ReturnValue.new('void'), 'set_zbr_pholder',
        [Parameter.new('PointerHolder<Zbr>', 'zbr')]))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('PointerHolder<Zbr>'), 'get_zbr_pholder', []))

    ## test overloaded methods
    SomeObject.add_method(CppMethod(ReturnValue.new('int'), 'get_int',
                                    [Parameter.new('const char*', 'from_string')]),
                          name="get_int")
    SomeObject.add_method(CppMethod(ReturnValue.new('int'), 'get_int',
                                    [Parameter.new('double', 'from_float')]),
                          name="get_int")


    mod.add_class(SomeObject)

    mod.generate(FileCodeSink(out_file))


if __name__ == '__main__':
    my_module_gen(sys.stdout)

