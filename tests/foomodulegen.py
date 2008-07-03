#! /usr/bin/env python

import sys
import re

import pybindgen
import pybindgen.utils
from pybindgen.typehandlers import base as typehandlers
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)
from pybindgen.function import CustomFunctionWrapper
from pybindgen.cppmethod import CustomCppMethodWrapper

import foomodulegen_common



def my_module_gen(out_file):

    mod = Module('foo')

    mod.add_include ('"foo.h"')

    Foo = mod.add_class('Foo', automatic_type_narrowing=True)

    Foo.add_static_attribute('instance_count', ReturnValue.new('int'))
    Foo.add_constructor([Parameter.new('std::string', 'datum')])
    Foo.add_constructor([])
    Foo.add_method('get_datum', ReturnValue.new('std::string'), [])
    Foo.add_method('is_initialized', ReturnValue.new('bool'), [], is_const=True)
    Foo.add_output_stream_operator()

    Zoo = mod.add_class('Zoo', automatic_type_narrowing=True)
    Zoo.add_constructor([Parameter.new('std::string', 'datum')])
    Zoo.add_constructor([])
    Zoo.add_method('get_datum', ReturnValue.new('std::string'), [])
    Zoo.implicitly_converts_to(Foo)

    Foobar = mod.add_class('Foobar')
    Foobar.add_static_attribute('instance_count', ReturnValue.new('int'))


    Bar = mod.add_class('Bar', parent=Foo)
    Bar.inherit_default_constructors()
    ## a static method..
    Bar.add_method('Hooray', ReturnValue.new('std::string'), [], is_static=True)

    ## to test RTTI with a hidden subclass
    mod.add_function('get_hidden_subclass_pointer',
                     ReturnValue.new('Foo*', caller_owns_return=True),
                     [])


    ## Zbr is a reference counted class
    Zbr = mod.add_class('Zbr', incref_method='Ref', decref_method='Unref',
                        peekref_method="GetReferenceCount", allow_subclassing=True)

    def helper_class_hook(helper_class):
        helper_class.add_custom_method(
            declaration="static int custom_method_added_by_a_hook(int x);",
            body="""
int %s::custom_method_added_by_a_hook(int x)
{
  return x + 1;
}
""" % helper_class.name)
        helper_class.add_post_generation_code("// this comment was written by a helper class hook function")
    Zbr.add_helper_class_hook(helper_class_hook)

    Zbr.add_constructor([Parameter.new('std::string', 'datum')])
    Zbr.add_method('get_datum', ReturnValue.new('std::string'), [])
    Zbr.add_method('get_int', ReturnValue.new('int'), [Parameter.new('int', 'x')],
                             is_virtual=True)
    Zbr.add_static_attribute('instance_count', ReturnValue.new('int'))
    
    mod.add_function('store_zbr', None,
                     [Parameter.new('Zbr*', 'zbr', transfer_ownership=True)])
    mod.add_function('invoke_zbr', ReturnValue.new('int'), [Parameter.new('int', 'x')])
    mod.add_function('delete_stored_zbr', None, [])


    mod.add_function('print_something', ReturnValue.new('int'),
                     [Parameter.new('char*', 'message', is_const=True)])
    mod.add_function('print_something_else', ReturnValue.new('int'),
                     [Parameter.new('char*', 'message2', is_const=True)])

    ## test overloaded functions
    mod.add_function('get_int_from_string', ReturnValue.new('int'),
                     [Parameter.new('char*', 'from_string', is_const=True),
                      Parameter.new('int', 'multiplier', default_value='1')], custom_name="get_int")
    mod.add_function('get_int_from_float', ReturnValue.new('int'),
                     [Parameter.new('double', 'from_float')], custom_name="get_int")



    SomeObject = mod.add_class('SomeObject', allow_subclassing=True)

    SomeObject.add_instance_attribute('foo', ReturnValue.new('Foo'),
                                      getter='get_foo_value',
                                      setter='set_foo_value')
    SomeObject.add_instance_attribute('m_prefix', ReturnValue.new('std::string'))
    SomeObject.add_static_attribute('staticData', ReturnValue.new('std::string'))

    SomeObject.add_static_attribute('instance_count', ReturnValue.new('int'))
    
    SomeObject.add_method('add_prefix', ReturnValue.new('int'),
                          [Parameter.new('std::string&', 'message',
                                         direction=Parameter.DIRECTION_INOUT)])
    SomeObject.add_constructor([Parameter.new('std::string', 'prefix')])
    SomeObject.add_constructor([Parameter.new('int', 'prefix_len')])

    # --- some virtual methods ---
    SomeObject.add_method('get_prefix', ReturnValue.new('std::string'), [],
                          is_virtual=True, is_const=True)

    SomeObject.add_method('get_prefix_with_foo_value', ReturnValue.new('std::string'),
                          [Parameter.new('Foo', 'foo')],
                          is_virtual=True, is_const=True)

    SomeObject.add_method('get_prefix_with_foo_ref',
                          ReturnValue.new('std::string'),
                          [Parameter.new('Foo&', 'foo', is_const=True,
                           direction=Parameter.DIRECTION_INOUT)],
                          is_virtual=True, is_const=True)

    SomeObject.add_method('get_prefix_with_foo_ptr',
                          ReturnValue.new('std::string'),
                          [Parameter.new('Foo*', 'foo', transfer_ownership=False, is_const=True)],
                          is_virtual=True, is_const=True)

    ## overloaded virtual methods
    SomeObject.add_method('get_something',
                          ReturnValue.new('std::string'),
                          [],
                          is_virtual=True, is_const=True)
    SomeObject.add_method('get_something',
                          ReturnValue.new('std::string'),
                          [Parameter.new('int', 'x')],
                          is_virtual=True, is_const=True)


    ## add a function that appears as a method of an object
    SomeObject.add_function_as_method('some_object_get_something_prefixed',
                                      ReturnValue.new('std::string'),
                                      [Parameter.new('SomeObject*', 'obj', transfer_ownership=False, is_const=True),
                                       Parameter.new('std::string', 'something')],
                                      custom_name='get_something_prefixed')

    ## add a function that appears as a method of an object
    SomeObject.add_function_as_method('some_object_val_get_something_prefixed',
                                      ReturnValue.new('std::string'),
                                      [Parameter.new('SomeObject', 'obj'),
                                       Parameter.new('std::string', 'something')],
                                      custom_name='val_get_something_prefixed')

    ## add a function that appears as a method of an object
    SomeObject.add_function_as_method('some_object_ref_get_something_prefixed',
                                      ReturnValue.new('std::string'),
                                      [Parameter.new('SomeObject&', 'obj', is_const=True),
                                       Parameter.new('std::string', 'something')],
                                      custom_name='ref_get_something_prefixed')

    # ---
    SomeObject.add_method('call_get_prefix', ReturnValue.new('std::string'), [])

    SomeObject.add_method('set_foo_value', None, [Parameter.new('Foo', 'foo')])
    SomeObject.add_method('get_foo_value', ReturnValue.new('Foo'), [])

    SomeObject.add_method('set_foo_ptr', ReturnValue.new('void'),
                          [Parameter.new('Foo*', 'foo', transfer_ownership=True)])
    SomeObject.add_method('set_foo_shared_ptr', ReturnValue.new('void'),
                          [Parameter.new('Foo*', 'foo', transfer_ownership=False)])

    SomeObject.add_method('get_foo_shared_ptr', ReturnValue.new('Foo*', caller_owns_return=False), [])
    SomeObject.add_method('get_foo_ptr', ReturnValue.new('Foo*', caller_owns_return=True), [])

    SomeObject.add_method('set_foo_by_ref', ReturnValue.new('void'),
                          [Parameter.new('Foo&', 'foo', direction=Parameter.DIRECTION_IN)])
    SomeObject.add_method('get_foo_by_ref', ReturnValue.new('void'),
                          [Parameter.new('Foo&', 'foo', direction=Parameter.DIRECTION_OUT)])

    ## custodian/ward tests
    SomeObject.add_method('get_foobar_with_self_as_custodian',
                          ReturnValue.new('Foobar*', custodian=0), [])
    SomeObject.add_method('get_foobar_with_other_as_custodian',
                          ReturnValue.new('Foobar*', custodian=1),
                          [Parameter.new('SomeObject*', 'other', transfer_ownership=False)])
    SomeObject.add_method('set_foobar_with_self_as_custodian', ReturnValue.new('void'),
                          [Parameter.new('Foobar*', 'foobar', custodian=0)])

    mod.add_function('get_foobar_with_other_as_custodian', ReturnValue.new('Foobar*', custodian=1),
                     [Parameter.new('SomeObject*', 'other', transfer_ownership=False)])

    mod.add_function('create_new_foobar', ReturnValue.new('Foobar*', caller_owns_return=True), [])

    mod.add_function('set_foobar_with_other_as_custodian', ReturnValue.new('void'),
                     [Parameter.new('Foobar*', 'foobar', custodian=2),
                      Parameter.new('SomeObject*', 'other', transfer_ownership=False)])

    mod.add_function('set_foobar_with_return_as_custodian', ReturnValue.new('SomeObject*', caller_owns_return=True),
                     [Parameter.new('Foobar*', 'foobar', custodian=-1)])


    ## get/set recfcounted object Zbr
    SomeObject.add_method('get_zbr', ReturnValue.new('Zbr*', caller_owns_return=True), [])
    SomeObject.add_method('peek_zbr', ReturnValue.new('Zbr*', caller_owns_return=False), [])
    SomeObject.add_method('set_zbr_transfer', ReturnValue.new('void'),
                          [Parameter.new('Zbr*', 'zbr', transfer_ownership=True)])
    SomeObject.add_method('set_zbr_shared', ReturnValue.new('void'),
                          [Parameter.new('Zbr*', 'zbr', transfer_ownership=False)])

    ## methods with transformed types
    SomeObject.add_method('set_zbr_pholder', ReturnValue.new('void'),
                          [Parameter.new('PointerHolder<Zbr>', 'zbr')])
    SomeObject.add_method('get_zbr_pholder',
                          ReturnValue.new('PointerHolder<Zbr>'), [])

    ## test overloaded methods
    SomeObject.add_method('get_int', ReturnValue.new('int'),
                          [Parameter.new('char*', 'from_string', is_const=True)],
                          custom_name="get_int")
    SomeObject.add_method('get_int', ReturnValue.new('int'),
                          [Parameter.new('double', 'from_float')],
                          custom_name="get_int")


    mod.add_function('store_some_object', ReturnValue.new('void'),
                     [Parameter.new('SomeObject*', 'obj', transfer_ownership=True)])
    mod.add_function('invoke_some_object_get_prefix', ReturnValue.new('std::string'),
                     [])
    mod.add_function('take_some_object', ReturnValue.new('SomeObject*', caller_owns_return=True), [])
    mod.add_function('delete_some_object', ReturnValue.new('void'), [])

    xpto = mod.add_cpp_namespace("xpto")
    xpto.add_function('some_function', ReturnValue.new('std::string'), [])

    ## enums..
    xpto.add_enum('FooType', ['FOO_TYPE_AAA', 'FOO_TYPE_BBB', 'FOO_TYPE_CCC'])
    xpto.add_function('get_foo_type', ReturnValue.new('FooType'), [])
    xpto.add_function('set_foo_type', ReturnValue.new('void'), [Parameter.new("FooType", 'type')])


    xpto_SomeClass = xpto.add_class('SomeClass')
    xpto_SomeClass.add_constructor([])

    ## ---- some implicity conversion APIs
    mod.add_function('function_that_takes_foo', ReturnValue.new('void'),
                               [Parameter.new('Foo', 'foo')])
    mod.add_function('function_that_returns_foo', ReturnValue.new('Foo'), [])
    
    cls = mod.add_class('ClassThatTakesFoo')
    cls.add_constructor([Parameter.new('Foo', 'foo')])
    cls.add_method('get_foo', ReturnValue.new('Foo'), [])

    cls = mod.add_class('SingletonClass', is_singleton=True)
    cls.add_method('GetInstance', ReturnValue.new('SingletonClass*', caller_owns_return=True),
                   [], is_static=True)


    ## A class that has no public default constructor...
    cls = mod.add_class('InterfaceId', is_singleton=True)
    ## A function that returns such a class...
    mod.add_function('make_interface_id', ReturnValue.new('InterfaceId'), [])


    ## A class the cannot be constructed; this will cause late CodeGenerationError's
    cls = mod.add_class('CannotBeConstructed')
    cls.set_cannot_be_constructed("no reason")
    cls.add_method('get_value', ReturnValue.new('CannotBeConstructed'),
                             [], is_static=True)
    cls.add_method('get_ptr', ReturnValue.new('CannotBeConstructed*', caller_owns_return=True),
                   [], is_static=True)
    mod.add_function('get_cannot_be_constructed_value',
                     ReturnValue.new('CannotBeConstructed'),
                     [])
    mod.add_function('get_cannot_be_constructed_ptr',
                     ReturnValue.new('CannotBeConstructed*', caller_owns_return=True),
                     [])


    ## A nested class
    NestedClass = mod.add_class('NestedClass', automatic_type_narrowing=True, outer_class=SomeObject)
    NestedClass.add_static_attribute('instance_count', ReturnValue.new('int'))
    NestedClass.add_constructor([Parameter.new('std::string', 'datum')])
    NestedClass.add_constructor([])
    NestedClass.add_method('get_datum', ReturnValue.new('std::string'), [])

    ## A nested enum..
    mod.add_enum('NestedEnum', ['FOO_TYPE_AAA', 'FOO_TYPE_BBB', 'FOO_TYPE_CCC'], outer_class=SomeObject)



    AbstractBaseClass2 = mod.add_class('AbstractBaseClass2', allow_subclassing=True)

    AbstractBaseClass2.add_method('invoke_private_virtual', ReturnValue.new('int'),
                                  [Parameter.new('int', 'x')], is_const=True)
    AbstractBaseClass2.add_method('invoke_protected_virtual', ReturnValue.new('int'),
                                  [Parameter.new('int', 'x')], is_const=True)
    AbstractBaseClass2.add_constructor([], visibility='protected')

    AbstractBaseClass2.add_method('protected_virtual',
                                  ReturnValue.new('int'),
                                  [Parameter.new('int', 'x')],
                                  is_virtual=True, visibility='protected', is_const=True)
    
    AbstractBaseClass2.add_method('private_virtual',
                                  ReturnValue.new('int'), [Parameter.new('int', 'x')],
                                  is_virtual=True, is_pure_virtual=True, visibility='private', is_const=True)




    AbstractXpto = mod.add_class('AbstractXpto', allow_subclassing=True)
    AbstractXpto.add_method('something', ReturnValue.new('void'),
                            [Parameter.new('int', 'x')], is_const=True,
                            is_virtual=True, is_pure_virtual=True)
    AbstractXpto.add_constructor([])

    AbstractXptoImpl = mod.add_class('AbstractXptoImpl', parent=AbstractXpto)
    AbstractXptoImpl.add_method('something', ReturnValue.new('void'),
                                [Parameter.new('int', 'x')], is_const=True,
                                is_virtual=True, is_pure_virtual=False)
    AbstractXptoImpl.add_constructor([])

    Word = mod.add_class('Word')
    Word.add_instance_attribute('low', 'uint8_t', is_const=False)
    Word.add_instance_attribute('high', 'uint8_t', is_const=False)
    Word.add_instance_attribute('word', 'uint16_t', is_const=False)
    Word.add_constructor([])


    mod.add_function('matrix_sum_of_elements',
                     ReturnValue.new('float'),
                     [Parameter.new("float*", 'matrix', direction=Parameter.DIRECTION_IN, array_length=6)])

    mod.add_function('matrix_identity_new',
                     ReturnValue.new('void'),
                     [Parameter.new("float*", 'matrix', direction=Parameter.DIRECTION_OUT, array_length=6)])

    top_ns = mod.add_cpp_namespace('TopNs')
    outer_base = top_ns.add_class('OuterBase')
    bottom_ns = top_ns.add_cpp_namespace('PrefixBottomNs')
    inner = bottom_ns.add_class('PrefixInner',parent=outer_base)
    inner.add_constructor([])
    inner.add_method('Do', 'void', [])
    



    #### --- error handler ---
    class MyErrorHandler(pybindgen.settings.ErrorHandler):
        def __init__(self):
            super(MyErrorHandler, self).__init__()
            self.num_errors = 0
        def handle_error(self, wrapper, exception, dummy_traceback_):
            print >> sys.stderr, "exception %s in wrapper %s" % (exception, wrapper)
            self.num_errors += 1
            return True
    pybindgen.settings.error_handler = MyErrorHandler()


    foomodulegen_common.customize_module(mod)

    ## ---- finally, generate the whole thing ----
    mod.generate(FileCodeSink(out_file))

if __name__ == '__main__':
    try:
        import cProfile as profile
    except ImportError:
        my_module_gen(sys.stdout)
    else:
        print >> sys.stderr, "** running under profiler"
        profile.run('my_module_gen(sys.stdout)', 'foomodulegen.pstat')

