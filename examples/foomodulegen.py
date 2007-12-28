#! /usr/bin/env python

import sys
import re

import pybindgen
import pybindgen.utils
from pybindgen.typehandlers import base as typehandlers
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)



class PointerHolderTransformation(typehandlers.TypeTransformation):
    def __init__(self):
        self.rx = re.compile(r'(?:::)?PointerHolder<(\w+)>')

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
    Foo.add_static_attribute(ReturnValue.new('int'), 'instance_count')
    Foo.add_constructor(
        CppConstructor([Parameter.new('std::string', 'datum')]))
    Foo.add_constructor(CppConstructor([]))
    Foo.add_method(CppMethod(ReturnValue.new('std::string'), 'get_datum', []))

    Zoo = CppClass('Zoo', automatic_type_narrowing=True)
    mod.add_class(Zoo)
    Zoo.add_constructor(
        CppConstructor([Parameter.new('std::string', 'datum')]))
    Zoo.add_constructor(CppConstructor([]))
    Zoo.add_method(CppMethod(ReturnValue.new('std::string'), 'get_datum', []))
    Zoo.implicitly_converts_to(Foo)


    Foobar = CppClass('Foobar')
    mod.add_class(Foobar)
    Foobar.add_static_attribute(ReturnValue.new('int'), 'instance_count')


    Bar = CppClass('Bar', parent=Foo)
    mod.add_class(Bar)
    ## a static method..
    Bar.add_method(CppMethod(ReturnValue.new('std::string'), 'Hooray', [], is_static=True))

    ## to test RTTI with a hidden subclass
    mod.add_function(Function(ReturnValue.new('Foo*', caller_owns_return=True),
                              'get_hidden_subclass_pointer', []))


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



    SomeObject = CppClass('SomeObject', allow_subclassing=True)
    mod.add_class(SomeObject)

    SomeObject.add_instance_attribute(ReturnValue.new('Foo'), 'foo',
                                      getter='get_foo_value',
                                      setter='set_foo_value')
    SomeObject.add_instance_attribute(ReturnValue.new('std::string'), 'm_prefix')
    SomeObject.add_static_attribute(ReturnValue.new('std::string'), 'staticData')

    SomeObject.add_static_attribute(ReturnValue.new('int'), 'instance_count')
    
    SomeObject.add_method(CppMethod(ReturnValue.new('int'), 'add_prefix',
                                    [Parameter.new('std::string&', 'message',
                                               direction=Parameter.DIRECTION_INOUT)]))
    SomeObject.add_constructor(
        CppConstructor([Parameter.new('std::string', 'prefix')]))
    SomeObject.add_constructor(
        CppConstructor([Parameter.new('int', 'prefix_len')]))

    # --- some virtual methods ---
    SomeObject.add_method(CppMethod(
        ReturnValue.new('std::string'), 'get_prefix', [],
        is_virtual=True, is_const=True))

    SomeObject.add_method(CppMethod(
        ReturnValue.new('std::string'), 'get_prefix_with_foo_value',
        [Parameter.new('Foo', 'foo')],
        is_virtual=True, is_const=True))

    SomeObject.add_method(CppMethod(
            ReturnValue.new('std::string'), 'get_prefix_with_foo_ref',
            [Parameter.new('Foo&', 'foo', is_const=True,
                           direction=Parameter.DIRECTION_INOUT)],
            is_virtual=True, is_const=True))

    SomeObject.add_method(CppMethod(
        ReturnValue.new('std::string'), 'get_prefix_with_foo_ptr',
        [Parameter.new('Foo*', 'foo', transfer_ownership=False, is_const=True)],
        is_virtual=True, is_const=True))

    ## overloaded virtual methods
    SomeObject.add_method(CppMethod(
        ReturnValue.new('std::string'), 'get_something',
        [],
        is_virtual=True, is_const=True))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('std::string'), 'get_something',
        [Parameter.new('int', 'x')],
        is_virtual=True, is_const=True))


    ## add a function that appears as a method of an object
    SomeObject.add_method(
        Function(ReturnValue.new('std::string'), 'some_object_get_something_prefixed',
                 [Parameter.new('SomeObject*', 'obj', transfer_ownership=False, is_const=True),
                  Parameter.new('std::string', 'something')]),
        name='get_something_prefixed')

    ## add a function that appears as a method of an object
    SomeObject.add_method(
        Function(ReturnValue.new('std::string'), 'some_object_val_get_something_prefixed',
                 [Parameter.new('SomeObject', 'obj'),
                  Parameter.new('std::string', 'something')]),
        name='val_get_something_prefixed')

    ## add a function that appears as a method of an object
    SomeObject.add_method(
        Function(ReturnValue.new('std::string'), 'some_object_ref_get_something_prefixed',
                 [Parameter.new('SomeObject&', 'obj', is_const=True),
                  Parameter.new('std::string', 'something')]),
        name='ref_get_something_prefixed')

    # ---
    SomeObject.add_method(CppMethod(
        ReturnValue.new('std::string'), 'call_get_prefix', []))

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

    ## custodian/ward tests
    SomeObject.add_method(CppMethod(
        ReturnValue.new('Foobar*', custodian=0), 'get_foobar_with_self_as_custodian',
        []))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('Foobar*', custodian=1), 'get_foobar_with_other_as_custodian',
        [Parameter.new('SomeObject*', 'other', transfer_ownership=False)]))
    SomeObject.add_method(CppMethod(
        ReturnValue.new('void'), 'set_foobar_with_self_as_custodian',
        [Parameter.new('Foobar*', 'foobar', custodian=0)]))

    mod.add_function(Function(ReturnValue.new('Foobar*', custodian=1),
                              'get_foobar_with_other_as_custodian',
                              [Parameter.new('SomeObject*', 'other', transfer_ownership=False)]))

    mod.add_function(Function(ReturnValue.new('Foobar*', caller_owns_return=True),
                              'create_new_foobar', []))

    mod.add_function(Function(ReturnValue.new('void'),
                              'set_foobar_with_other_as_custodian',
                              [Parameter.new('Foobar*', 'foobar', custodian=2),
                               Parameter.new('SomeObject*', 'other', transfer_ownership=False)]))

    mod.add_function(Function(ReturnValue.new('SomeObject*', caller_owns_return=True),
                              'set_foobar_with_return_as_custodian',
                              [Parameter.new('Foobar*', 'foobar', custodian=-1)]))


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


    mod.add_function(Function(ReturnValue.new('void'), 'store_some_object',
                              [Parameter.new('SomeObject*', 'obj', transfer_ownership=True)]))
    mod.add_function(Function(ReturnValue.new('std::string'), 'invoke_some_object_get_prefix',
                              []))
    mod.add_function(Function(ReturnValue.new('SomeObject*', caller_owns_return=True),
                              'take_some_object', []))
    mod.add_function(Function(ReturnValue.new('void'), 'delete_some_object', []))

    xpto = mod.add_cpp_namespace("xpto")
    xpto.add_function(Function(ReturnValue.new('std::string'), 'some_function', []))

    ## enums..
    xpto.add_enum(Enum('FooType', ['FOO_TYPE_AAA', 'FOO_TYPE_BBB', 'FOO_TYPE_CCC']))
    xpto.add_function(Function(ReturnValue.new('FooType'), 'get_foo_type', []))
    xpto.add_function(Function(ReturnValue.new('void'), 'set_foo_type', [Parameter.new("FooType", 'type')]))


    xpto_SomeClass = CppClass('SomeClass')
    xpto.add_class(xpto_SomeClass)
    xpto_SomeClass.add_constructor(CppConstructor([]))

    ## ---- some implicity conversion APIs
    mod.add_function(Function(ReturnValue.new('void'),
                               'function_that_takes_foo',
                               [Parameter.new('Foo', 'foo')]))
    mod.add_function(Function(ReturnValue.new('Foo'), 'function_that_returns_foo', []))
    
    cls = CppClass('ClassThatTakesFoo')
    mod.add_class(cls)
    cls.add_constructor(CppConstructor([Parameter.new('Foo', 'foo')]))
    cls.add_method(CppMethod(ReturnValue.new('Foo'), 'get_foo', []))

    cls = CppClass('SingletonClass', is_singleton=True)
    mod.add_class(cls)
    cls.add_method(CppMethod(ReturnValue.new('SingletonClass*', caller_owns_return=True),
                             'GetInstance', [], is_static=True))


    ## A class that has no public default constructor...
    cls = CppClass('InterfaceId', is_singleton=True)
    mod.add_class(cls)
    ## A function that returns such a class...
    mod.add_function(Function(ReturnValue.new('InterfaceId'),
                              'make_interface_id', []))


    ## A class the cannot be constructed; this will cause late CodeGenerationError's
    cls = CppClass('CannotBeConstructed')
    mod.add_class(cls)
    cls.set_cannot_be_constructed(True)
    cls.add_method(CppMethod(ReturnValue.new('CannotBeConstructed'),
                             'get_value', [], is_static=True))
    cls.add_method(CppMethod(ReturnValue.new('CannotBeConstructed*', caller_owns_return=True),
                             'get_ptr', [], is_static=True))
    mod.add_function(Function(ReturnValue.new('CannotBeConstructed'),
                              'get_cannot_be_constructed_value', []))
    mod.add_function(Function(ReturnValue.new('CannotBeConstructed*', caller_owns_return=True),
                              'get_cannot_be_constructed_ptr', []))


    ## A nested class
    NestedClass = CppClass('NestedClass', automatic_type_narrowing=True, outer_class=SomeObject)
    mod.add_class(NestedClass)
    NestedClass.add_static_attribute(ReturnValue.new('int'), 'instance_count')
    NestedClass.add_constructor(
        CppConstructor([Parameter.new('std::string', 'datum')]))
    NestedClass.add_constructor(CppConstructor([]))
    NestedClass.add_method(CppMethod(ReturnValue.new('std::string'), 'get_datum', []))

    ## A nested enum..
    mod.add_enum(Enum('NestedEnum', ['FOO_TYPE_AAA', 'FOO_TYPE_BBB', 'FOO_TYPE_CCC'],
                      outer_class=SomeObject))

    class MyErrorHandler(pybindgen.settings.ErrorHandler):
        def __init__(self):
            self.num_errors = 0
        def handle_error(self, wrapper, exception, traceback_):
            print >> sys.stderr, "exception %s in wrapper %s" % (exception, wrapper)
            self.num_errors += 1
            return True
    pybindgen.settings.error_handler = MyErrorHandler()

    ## ---- finally, generate the whole thing ----
    mod.generate(FileCodeSink(out_file))

if __name__ == '__main__':
    my_module_gen(sys.stdout)

