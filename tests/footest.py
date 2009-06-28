import sys
import weakref
import gc
import os.path
import copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'build', 'default', 'tests'))
which = int(sys.argv[1])
del sys.argv[1]
if which == 1:
    import foo
elif which == 2:
    import foo2 as foo
elif which == 3:
    import foo3 as foo
elif which == 4:
    import foo4 as foo
else:
    raise AssertionError("bad command line arguments")

import unittest


class TestFoo(unittest.TestCase):

    def test_add_prefix(self):
        obj = foo.SomeObject("hello ")
        ln, msg = obj.add_prefix("gjc")
        self.assertEqual(msg, "hello gjc")
        self.assertEqual(ln, len("hello gjc"))

    def test_foo(self):
        f = foo.Foo("hello")
        self.assertEqual(f.get_datum(), "hello")

    def test_pass_foo_by_value(self):
        obj = foo.SomeObject("")
        f = foo.Foo("hello")
        obj.set_foo_value(f)

        f2 = obj.get_foo_value()
        self.assertEqual(f2.get_datum(), "hello")

    def test_pass_foo_by_transfer_ptr(self):
        obj = foo.SomeObject("")
        f = foo.Foo("hello")
        obj.set_foo_ptr(f)
        del f
        f2 = obj.get_foo_ptr()
        self.assertEqual(f2.get_datum(), "hello")
        
    def test_pass_foo_shared_ptr(self):
        obj = foo.SomeObject("")
        f = foo.Foo("hello")
        obj.set_foo_shared_ptr(f)
        self.assertEqual(f.get_datum(), "hello")
        f2 = obj.get_foo_shared_ptr()
        self.assertEqual(f2.get_datum(), "hello")
    
    def test_pass_by_reference(self):
        obj = foo.SomeObject("")
        f = foo.Foo("hello")
        obj.set_foo_by_ref(f)
        self.assertEqual(f.get_datum(), "hello")
        f2 = obj.get_foo_by_ref()
        self.assertEqual(f2.get_datum(), "hello")
        
    def test_refcounting(self):
        obj = foo.SomeObject("")
        z = foo.Zbr("hello")
        obj.set_zbr_transfer(z)

        self.assertEqual(z.get_datum(), "hello")
        z2 = obj.get_zbr()
        self.assertEqual(z2.get_datum(), "hello")
        z3 = obj.get_zbr()
        self.assertEqual(z3.get_datum(), "hello")

        zz = foo.Zbr("world")
        self.assertEqual(zz.get_datum(), "world")
        obj.set_zbr_shared(zz)

        ## previous z's should not have been changed
        self.assertEqual(z.get_datum(), "hello")
        self.assertEqual(z2.get_datum(), "hello")
        self.assertEqual(z3.get_datum(), "hello")

        self.assertEqual(zz.get_datum(), "world")
        zz2 = obj.get_zbr()
        self.assertEqual(zz2.get_datum(), "world")
        zz3 = obj.peek_zbr()
        self.assertEqual(zz3.get_datum(), "world")
        
    def test_instance_get_attribute(self):
        obj = foo.SomeObject("Hello")
        self.assertEqual(obj.m_prefix, "Hello")

    def test_instance_set_attribute(self):
        obj = foo.SomeObject("")
        obj.m_prefix = "World"
        self.assertEqual(obj.m_prefix, "World")

    def test_static_get_attribute(self):
        self.assertEqual(foo.SomeObject.staticData, "Hello Static World!")

    def test_static_set_attribute(self):
        foo.SomeObject.staticData = "Foo Bar Zbr"
        self.assertEqual(foo.SomeObject.staticData, "Foo Bar Zbr")

    def test_overloaded_functions(self):
        v1 = foo.get_int(123.0)
        self.assertEqual(v1, 123)

        v2 = foo.get_int("123")
        self.assertEqual(v2, 123)

        self.assertRaises(TypeError, foo.get_int, [123])

    def test_default_value(self):
        v1 = foo.get_int(123.0)
        self.assertEqual(v1, 123)

        v1 = foo.get_int(123.0, 2)
        self.assertEqual(v1, 123*2)

    def test_overloaded_methods(self):
        obj = foo.SomeObject("zbr")
        
        v1 = obj.get_int(123.0)
        self.assertEqual(v1, 123)

        v2 = obj.get_int("123")
        self.assertEqual(v2, 123)

        self.assertRaises(TypeError, obj.get_int, [123])
        

    def test_overloaded_constructors(self):
        obj1 = foo.SomeObject("zbr")
        self.assertEqual(obj1.get_prefix(), "zbr")
        obj2 = foo.SomeObject(5)
        self.assertEqual(obj2.get_prefix(), "XXXXX")
        self.assertRaises(TypeError, foo.SomeObject, [123])

    def test_return_type_narrowing(self):
        obj = foo.SomeObject("zbr")

        obj.set_foo_ptr(foo.Foo())
        foo1 = obj.get_foo_ptr()
        self.assertEqual(type(foo1), foo.Foo)
        
        bar2 = foo.Bar()
        self.assertEqual(type(bar2), foo.Bar)
        obj.set_foo_ptr(bar2)
        foo2 = obj.get_foo_ptr()
        self.assertEqual(type(foo2), foo.Bar)

    def test_type_narrowing_hidden_subclass(self):
        """This test only works with GCC >= 3.0 (and not with other compilers)"""
        obj = foo.get_hidden_subclass_pointer()
        self.assertEqual(type(obj), foo.Bar)

    def test_subclass_gc(self):
        """Check if subclassed object is garbage collected"""

        try:
            class Test(foo.SomeObject):
                pass
        except TypeError:
            self.fail()

        while gc.collect():
            pass
        count_before = foo.SomeObject.instance_count
        t = Test("xxx")
        t.xxx = t
        ref = weakref.ref(t)
        del t
        while gc.collect():
            pass
        self.assertEqual(ref(), None)
        self.assertEqual(foo.SomeObject.instance_count, count_before)

    def test_nosubclass_gc(self):
        """Check if subclassable object is garbage collected"""
        while gc.collect():
            pass
        count_before = foo.SomeObject.instance_count
        t = foo.SomeObject("xxx")
        t.xxx = t
        del t
        while gc.collect():
            pass
        self.assertEqual(foo.SomeObject.instance_count, count_before)

    def test_virtual_no_subclass(self):
        t = foo.SomeObject("xxx")
        self.assertEqual(t.call_get_prefix(), "xxx")

    def test_virtual_subclass(self):
        class Test(foo.SomeObject):
            def _get_prefix(self):
                return "yyy"

        t = Test("xxx")
        self.assertEqual(t.call_get_prefix(), "yyy")

    def test_virtual_with_chaining_to_parent_class(self):
        class Test(foo.SomeObject):
            def _get_prefix(self):
                prefix = super(Test, self)._get_prefix()
                return prefix + "yyy"

        t = Test("xxx")
        self.assertEqual(t.call_get_prefix(), "xxxyyy")


    def test_subclassable_transfer_ptr(self):
        while gc.collect():
            pass
        count_before = foo.SomeObject.instance_count
        obj = foo.SomeObject("xxx")
        foo.store_some_object(obj)
        del obj
        while gc.collect():
            pass
        ## check that SomeObject isn't prematurely deleted
        self.assertEqual(foo.SomeObject.instance_count, count_before + 1)

        ## now delete the object from the C side..
        foo.delete_some_object()
        while gc.collect():
            pass
        ## check that SomeObject was finally deleted
        self.assertEqual(foo.SomeObject.instance_count, count_before)

    def test_subclassable_store_and_take_back(self):
        while gc.collect():
            pass
        count_before = foo.SomeObject.instance_count
        obj = foo.SomeObject("xxx")
        foo.store_some_object(obj)
        del obj
        while gc.collect():
            pass
        ## check that SomeObject isn't prematurely deleted
        self.assertEqual(foo.SomeObject.instance_count, count_before + 1)

        ## now get the object back from the C side..
        obj = foo.take_some_object()
        self.assertEqual(obj.get_prefix(), "xxx")

        del obj
        while gc.collect():
            pass
        ## check that SomeObject was finally deleted
        self.assertEqual(foo.SomeObject.instance_count, count_before)
        

    def test_subclass_with_virtual_transfer_ptr(self):
        class Test(foo.SomeObject):
            def __init__(self, prefix, extra_prefix):
                super(Test, self).__init__(prefix)
                self.extra_prefix = extra_prefix
            def _get_prefix(self):
                prefix = super(Test, self)._get_prefix()
                return prefix + self.extra_prefix
        while gc.collect():
            pass
        count_before = foo.SomeObject.instance_count
        foo.store_some_object(Test("xxx", "yyy"))
        while gc.collect():
            pass

        ## check that SomeObject isn't prematurely deleted
        self.assertEqual(foo.SomeObject.instance_count, count_before + 1)

        ## invoke the virtual method and check that it returns the correct value
        prefix = foo.invoke_some_object_get_prefix()
        self.assertEqual(prefix, "xxxyyy")

        ## now delete the object from the C side..
        foo.delete_some_object()
        while gc.collect():
            pass

        ## check that SomeObject was finally deleted
        self.assertEqual(foo.SomeObject.instance_count, count_before)
        

    def test_subclassed_store_and_take_back(self):
        class Test(foo.SomeObject):
            pass

        while gc.collect():
            pass
        count_before = foo.SomeObject.instance_count
        obj1 = Test("xxx")
        obj1.attribute = 123
        foo.store_some_object(obj1)

        ## now get the object back from the C side..
        obj2 = foo.take_some_object()

        self.assert_(obj2 is obj1)
        self.assertEqual(obj2.attribute, 123)
        self.assertEqual(obj2.get_prefix(), "xxx")

        del obj1, obj2
        while gc.collect():
            pass
        ## check that SomeObject was finally deleted
        self.assertEqual(foo.SomeObject.instance_count, count_before)

    def test_namespaced_function(self):
        self.assertEqual(foo.xpto.some_function(), "hello")

    def test_namespaced_class(self):
        self.assert_(hasattr(foo.xpto, 'SomeClass'))

    def test_implicit_conversion_method_value(self):
        obj = foo.SomeObject("xxx")
        
        zoo1 = foo.Zoo("zpto")
        try:
            obj.set_foo_value(zoo1)
        except TypeError:
            self.fail()
        foo1 = obj.get_foo_value()
        self.assertEqual(foo1.get_datum(), "zpto")

        
    def test_implicit_conversion_function_value(self):
        zoo1 = foo.Zoo("zpto")
        try:
            foo.function_that_takes_foo(zoo1)
        except TypeError:
            self.fail()
        foo1 = foo.function_that_returns_foo()
        self.assertEqual(foo1.get_datum(), "zpto")

        
    def test_implicit_conversion_constructor_value(self):
        zoo1 = foo.Zoo("zpto")
        try:
            obj = foo.ClassThatTakesFoo(zoo1)
        except TypeError:
            self.fail()
        foo1 = obj.get_foo()
        self.assertEqual(foo1.get_datum(), "zpto")

    def test_custodian_method_self(self):
        while gc.collect():
            pass
        SomeObject_count_before = foo.SomeObject.instance_count
        obj1 = foo.SomeObject("xxx")
        Foobar_count1 = foo.Foobar.instance_count
        foo1 = obj1.get_foobar_with_self_as_custodian()
        Foobar_count2 = foo.Foobar.instance_count
        self.assertEqual(Foobar_count2, Foobar_count1 + 1)

        ## now, deleting foo1 should keep the Foobar count the same, since
        ## obj1 is keeping it alive
        del foo1
        while gc.collect():
            pass
        self.assertEqual(foo.Foobar.instance_count, Foobar_count2)

        ## now deleting obj1 should cause both foo1 and obj1 to be destroyed
        del obj1
        while gc.collect():
            pass
        self.assertEqual(foo.SomeObject.instance_count, SomeObject_count_before)
        self.assertEqual(foo.Foobar.instance_count, Foobar_count1)

    def test_custodian_method_other(self):
        while gc.collect():
            pass
        SomeObject_count_before = foo.SomeObject.instance_count
        Foobar_count1 = foo.Foobar.instance_count

        obj1 = foo.SomeObject("xxx")
        obj2 = foo.SomeObject("yyy")
        foo1 = obj1.get_foobar_with_other_as_custodian(obj2)

        while gc.collect():
            pass
        Foobar_count2 = foo.Foobar.instance_count

        ## now, deleting foo1 should keep Foobar count the same, since
        ## obj2 is keeping it alive
        del foo1
        while gc.collect():
            pass
        self.assertEqual(foo.Foobar.instance_count, Foobar_count2)

        ##  deleting obj1 should still keep Foobar count the same, since
        ## obj2, not obj1, is keeping it alive
        del obj1
        while gc.collect():
            pass
        self.assertEqual(foo.Foobar.instance_count, Foobar_count2)
        self.assertEqual(foo.SomeObject.instance_count, SomeObject_count_before + 1)

        ## now deleting obj2 should cause both foo1 and obj2 to be destroyed
        del obj2
        while gc.collect():
            pass
        self.assertEqual(foo.SomeObject.instance_count, SomeObject_count_before)
        self.assertEqual(foo.Foobar.instance_count, Foobar_count1)


    def test_custodian_function_other(self):
        while gc.collect():
            pass
        SomeObject_count_before = foo.SomeObject.instance_count
        Foobar_count1 = foo.Foobar.instance_count

        obj1 = foo.SomeObject("xxx")
        foo1 = foo.get_foobar_with_other_as_custodian(obj1)
        Foobar_count2 = foo.Foobar.instance_count

        ## now, deleting foo1 should keep Foobar count the same, since
        ## obj1 is keeping it alive
        del foo1
        while gc.collect():
            pass
        self.assertEqual(foo.Foobar.instance_count, Foobar_count2)

        ## now deleting obj1 should cause both foo1 and obj1 to be destroyed
        del obj1
        while gc.collect():
            pass
        self.assertEqual(foo.SomeObject.instance_count, SomeObject_count_before)
        self.assertEqual(foo.Foobar.instance_count, Foobar_count1)


    def test_custodian_function_param_other(self):
        while gc.collect():
            pass
        SomeObject_count_before = foo.SomeObject.instance_count
        Foobar_count1 = foo.Foobar.instance_count

        obj1 = foo.SomeObject("xxx")
        foo1 = foo.create_new_foobar()
        foo.set_foobar_with_other_as_custodian(foo1, obj1)
        Foobar_count2 = foo.Foobar.instance_count

        ## now, deleting foo1 should keep Foobar count the same, since
        ## obj1 is keeping it alive
        del foo1
        while gc.collect():
            pass
        self.assertEqual(foo.Foobar.instance_count, Foobar_count2)

        ## now deleting obj1 should cause both foo1 and obj1 to be destroyed
        del obj1
        while gc.collect():
            pass
        self.assertEqual(foo.SomeObject.instance_count, SomeObject_count_before)
        self.assertEqual(foo.Foobar.instance_count, Foobar_count1)


    def test_custodian_function_param_return(self):
        while gc.collect():
            pass
        SomeObject_count_before = foo.SomeObject.instance_count
        Foobar_count1 = foo.Foobar.instance_count

        foo1 = foo.create_new_foobar()
        obj1 = foo.set_foobar_with_return_as_custodian(foo1)
        Foobar_count2 = foo.Foobar.instance_count

        ## now, deleting foo1 should keep Foobar count the same, since
        ## obj1 is keeping it alive
        del foo1
        while gc.collect():
            pass
        self.assertEqual(foo.Foobar.instance_count, Foobar_count2)

        ## now deleting obj1 should cause both foo1 and obj1 to be destroyed
        del obj1
        while gc.collect():
            pass
        self.assertEqual(foo.SomeObject.instance_count, SomeObject_count_before)
        self.assertEqual(foo.Foobar.instance_count, Foobar_count1)


    def test_custodian_method_param_self(self):
        while gc.collect():
            pass
        SomeObject_count_before = foo.SomeObject.instance_count
        obj1 = foo.SomeObject("xxx")
        Foobar_count1 = foo.Foobar.instance_count
        foo1 = foo.create_new_foobar()
        obj1.set_foobar_with_self_as_custodian(foo1)
        Foobar_count2 = foo.Foobar.instance_count
        self.assertEqual(Foobar_count2, Foobar_count1 + 1)

        ## now, deleting foo1 should keep the Foobar count the same, since
        ## obj1 is keeping it alive
        del foo1
        while gc.collect():
            pass
        self.assertEqual(foo.Foobar.instance_count, Foobar_count2)

        ## now deleting obj1 should cause both foo1 and obj1 to be destroyed
        del obj1
        while gc.collect():
            pass
        self.assertEqual(foo.SomeObject.instance_count, SomeObject_count_before)
        self.assertEqual(foo.Foobar.instance_count, Foobar_count1)

    def test_subclass_with_virtual_with_foo_parameter_value(self):
        class Test(foo.SomeObject):
            def __init__(self, prefix, extra_prefix):
                super(Test, self).__init__(prefix)
                self.extra_prefix = extra_prefix
            def _get_prefix_with_foo_value(self, fooval):
                prefix = super(Test, self)._get_prefix_with_foo_value(fooval)
                return prefix + self.extra_prefix + fooval.get_datum()

        t = Test("123", "456")
        foo1 = foo.Foo("zbr")
        prefix = t.get_prefix_with_foo_value(foo1)
        self.assertEqual(prefix, "123zbr456zbr")

    def test_subclass_with_virtual_with_foo_parameter_ref(self):
        class Test(foo.SomeObject):
            def __init__(self, prefix, extra_prefix):
                super(Test, self).__init__(prefix)
                self.extra_prefix = extra_prefix
            def _get_prefix_with_foo_ref(self, fooval):
                prefix = super(Test, self)._get_prefix_with_foo_ref(fooval)
                return prefix + self.extra_prefix + fooval.get_datum()

        t = Test("123", "456")
        foo1 = foo.Foo("zbr")
        prefix = t.get_prefix_with_foo_ref(foo1)
        self.assertEqual(prefix, "123zbr456zbr")


    def test_subclass_with_virtual_with_foo_parameter_ptr(self):
        class Test(foo.SomeObject):
            def __init__(self, prefix, extra_prefix):
                super(Test, self).__init__(prefix)
                self.extra_prefix = extra_prefix
            def _get_prefix_with_foo_ptr(self, fooval):
                prefix = super(Test, self)._get_prefix_with_foo_ptr(fooval)
                return prefix + self.extra_prefix + fooval.get_datum()

        t = Test("123", "456")
        foo1 = foo.Foo("zbr")
        prefix = t.get_prefix_with_foo_ptr(foo1)
        self.assertEqual(prefix, "123zbr456zbr")

    def test_attribute_with_getset(self):
        obj = foo.SomeObject("")
        f1 = foo.Foo("hello")
        obj.foo = f1
        f2 = obj.foo
        self.assertEqual(f2.get_datum(), "hello")

    def test_function_as_method(self):
        while gc.collect():
            pass
        obj = foo.SomeObject("xpto")
        self.assertEqual(obj.get_something_prefixed("something"), "xptosomething")
        del obj
        while gc.collect():
            pass

    def test_function_as_method_val(self):
        while gc.collect():
            pass
        obj = foo.SomeObject("xpto")
        self.assertEqual(obj.val_get_something_prefixed("something"), "xptosomething")
        del obj
        while gc.collect():
            pass

    def test_function_as_method_ref(self):
        while gc.collect():
            pass
        obj = foo.SomeObject("xpto")
        self.assertEqual(obj.ref_get_something_prefixed("something"), "xptosomething")
        while gc.collect():
            pass

    def test_enum(self):
        foo.xpto.set_foo_type(foo.xpto.FOO_TYPE_BBB)
        self.assertEqual(foo.xpto.get_foo_type(), foo.xpto.FOO_TYPE_BBB)
        old = foo.xpto.set_foo_type_inout(foo.xpto.FOO_TYPE_CCC)
        self.assertEqual(old, foo.xpto.FOO_TYPE_BBB)

    def test_virtual_overload(self):
        ## first test the plain object
        obj = foo.SomeObject("")
        self.assertEqual(obj.get_something(), "something")
        self.assertEqual(obj.get_something(123), "123")

        ## now subclass it
        class MyObject(foo.SomeObject):
            def get_something(self, arg=None):
                self.arg = arg
                return str(arg)
            
        obj = MyObject("")
        s1 = obj.get_something()
        self.assertEqual(s1, "None")
        self.assertEqual(obj.arg, None)

        s2 = obj.get_something(123)
        self.assertEqual(s2, "123")
        self.assertEqual(obj.arg, 123)

    def test_nested_class(self):
        if not hasattr(foo.SomeObject, "NestedClass"):
            self.fail()
        f = foo.SomeObject.NestedClass("hello")
        self.assertEqual(f.get_datum(), "hello")

    def test_nested_enum(self):
        self.assert_(hasattr(foo.SomeObject, "FOO_TYPE_BBB"))

    def test_private_virtual(self):
        class Class(foo.AbstractBaseClass2):
            def _private_virtual(self, x):
                return x*x
        c = Class()
        x = c.invoke_private_virtual(2)
        self.assertEqual(x, 4)

    def test_protected_virtual(self):
        class Class(foo.AbstractBaseClass2):
            def _private_virtual(self, x):
                return x*x
            def _protected_virtual(self, x):
                y = super(Class, self)._protected_virtual(x)
                return y*y
        c = Class()
        x = c.invoke_protected_virtual(2)
        self.assertEqual(x, 9)


    def test_subclass_with_reference_counting(self):
        class Test(foo.Zbr):
            def __init__(self, y):
                super(Test, self).__init__("foo")
                self.y = y
            def _get_int(self, x):
                return getattr(self, 'y', 0) + x
                
        while gc.collect():
            pass
        count_before = foo.Zbr.instance_count
        foo.store_zbr(Test(123))
        while gc.collect():
            pass

        ## check that Zbr isn't prematurely deleted
        self.assertEqual(foo.Zbr.instance_count, count_before + 1)

        ## invoke the virtual method and check that it returns the correct value
        value = foo.invoke_zbr(456)
        self.assertEqual(value, 123+456)

        ## now delete the object from the C side..
        foo.delete_stored_zbr()
        while gc.collect():
            pass

        ## check that Zbr was finally deleted
        self.assertEqual(foo.Zbr.instance_count, count_before)


    def test_custom_function_wrapper(self):
        try:
            foo.function_that_takes_foo("yellow")
        except TypeError:
            self.fail()
        foo1 = foo.function_that_returns_foo()
        self.assertEqual(foo1.get_datum(), "yellow")

    def test_custom_method_wrapper(self):
        v1 = foo.Bar.Hooray()
        self.assertEqual(v1, "Hooray!")
        try:
            v2 = foo.Bar.Hooray(123) # this one is a fake method
        except TypeError:
            self.fail()
        else:
            self.assertEqual(v2, len("Hooray!") + 123)

    def test_instance_creation_function(self):
        f = foo.Foo()
        self.assert_(f.is_initialized())

        b = foo.Bar()
        self.assert_(b.is_initialized())

    def test_pure_virtual(self):
        self.assertRaises(TypeError, foo.AbstractXpto)
        try:
            foo.AbstractXptoImpl()
        except TypeError, ex:
            self.fail(str(ex))

    def test_parameter_default_value(self):
        x = foo.get_int("123")
        self.assertEqual(x, 123)
        y = foo.get_int("123", 2)
        self.assertEqual(y, 246)

    def test_anonymous_struct(self):
        """https://bugs.launchpad.net/pybindgen/+bug/237054"""

        word = foo.Word()

        word.word = 1
        self.assertEqual(word.word, 1)

        word.low = 2
        word.high = 3
        self.assertEqual(word.low, 2)
        self.assertEqual(word.high, 3)

    def test_float_array(self):
        array = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        s = foo.matrix_sum_of_elements(array)
        self.assertEqual(s, sum(array))

        result = foo.matrix_identity_new()
        expected = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        self.assertEqual(result, expected)

    def test_output_stream(self):
        f = foo.Foo("hello")
        self.assertEqual(str(f), "hello")

    def test_outer_inner_namespace(self):
        inner = foo.TopNs.PrefixBottomNs.PrefixInner ()
        inner.Do ()
        self.assertEqual (True, True)

    def test_overloaded_methods_and_inheritance(self):
        """https://bugs.launchpad.net/pybindgen/+bug/246069"""

        sock = foo.Socket()
        self.assertEqual(sock.Bind(), -1)
        self.assertEqual(sock.Bind(123), 123)

        udpsock = foo.UdpSocket()
        self.assertEqual(udpsock.Bind(), 0)
        try:
            self.assertEqual(udpsock.Bind(123), 123)
        except TypeError, ex:
            pass
        else:
            self.fail("UdpSocket.Bind(int) was not supposed to work")

    def test_struct(self):
        struct = foo.simple_struct_t()
        struct.xpto = 123
        self.assertEqual(struct.xpto, 123)

    def test_typedef(self):
        try:
            f = foo.xpto.FooXpto("hello")
        except AttributeError:
            self.fail()
        try:
            r = foo.xpto.get_foo_datum(f)
        except TypeError:
            self.fail()
        self.assertEqual(r, "hello")

    if 0:
        def test_deprecations(self):
            foo.print_something("zbr")

    def test_anon_enum(self):
        try:
            self.assertEqual(foo.SomeObject.CONSTANT_A, 0)
        except AttributeError:
            self.fail()

    def test_template_function(self):
        if not hasattr(foo, 'IntegerTypeNameGet'):
            self.fail()
        else:
            self.assertEqual(foo.IntegerTypeNameGet(), 'int')

    def test_operator_call(self):
        obj = foo.SomeObject("xpto_")
        l, s = obj("hello")
        self.assertEqual(s, "xpto_hello")
        self.assertEqual(l, len("xpto_hello"))

    def test_container_value_return_param(self):
        container = foo.get_simple_list()
        count = 0
        for i, simple in enumerate(container):
            self.assertEqual(simple.xpto, i)
            count += 1
        self.assertEqual(count, 10)
        #self.assertEqual(len(container), 10)

        rv = foo.set_simple_list(container)
        self.assertEqual(rv, sum(range(10)))



    def test_container_creation(self):
        container = foo.SimpleStructList()
        values = list(container)
        self.assertEqual(values, [])

        l = []
        for i in range(10):
            simple = foo.simple_struct_t()
            simple.xpto = i
            l.append(simple)

        container = foo.SimpleStructList(l)
        values = list(container)
        self.assertEqual(len(values), 10)
        for i, value in enumerate(values):
            self.assertEqual(value.xpto, i)
        
        rv = foo.set_simple_list(l)
        self.assertEqual(rv, sum(range(10)))

    def test_container_reverse_wrappers(self):
        class MyTestContainer(foo.TestContainer):
            def __init__(self):
                super(MyTestContainer, self).__init__()
                self.list_that_was_set = None

            def _get_simple_list(self):
                l = []
                for i in range(5):
                    simple = foo.simple_struct_t()
                    simple.xpto = i
                    l.append(simple)
                #container = foo.SimpleStructList(l)
                return l

            def _set_simple_list(self, container):
                self.list_that_was_set = container
                return sum([s.xpto for s in container])

        test = MyTestContainer()
        container = test.get_simple_list()
        count = 0
        for i, simple in enumerate(container):
            self.assertEqual(simple.xpto, i)
            count += 1
        self.assertEqual(count, 5)


        ## set 
        l = []
        for i in range(5):
            simple = foo.simple_struct_t()
            simple.xpto = i
            l.append(simple)

        rv = test.set_simple_list(l)
        self.assertEqual(rv, sum(range(5)))

        count = 0
        for i, simple in enumerate(test.list_that_was_set):
            self.assertEqual(simple.xpto, i)
            count += 1
        self.assertEqual(count, 5)
        

    def test_container_param_by_ref(self):
        l = []
        expected_sum = 0
        for i in range(10):
            simple = foo.simple_struct_t()
            simple.xpto = i
            l.append(simple)
            expected_sum += i*2

        test = foo.TestContainer()
        rv, container = test.set_simple_list_by_ref(l)
        l1 = list(container)
        self.assertEqual(rv, expected_sum)
        self.assertEqual(len(l1), len(l))
        for v, v1 in zip(l, l1):
            self.assertEqual(v1.xpto, 2*v.xpto)


    def test_unnamed_container(self):
        test = foo.TestContainer()
        container = test.get_simple_vec()
        count = 0
        for i, simple in enumerate(container):
            self.assertEqual(simple.xpto, i)
            count += 1
        self.assertEqual(count, 10)

        rv = test.set_simple_vec(container)
        self.assertEqual(rv, sum(range(10)))


    def test_map_container(self):
        test = foo.TestContainer()
        container = test.get_simple_map()
        count = 0
        for i, (simple_key, simple_val) in enumerate(container):
            self.assertEqual(simple_key, str(i))
            self.assertEqual(simple_val.xpto, i)
            count += 1
        self.assertEqual(count, 10)

        rv = test.set_simple_map(container)
        self.assertEqual(rv, sum(range(10)))

    def test_copy(self):
        s1 = foo.simple_struct_t()
        s1.xpto = 123

        # copy via constructor
        s2 = foo.simple_struct_t(s1)
        self.assertEqual(s2.xpto, 123)
        s2.xpto = 321
        self.assertEqual(s2.xpto, 321)
        self.assertEqual(s1.xpto, 123)

        # copy via __copy__
        s3 = copy.copy(s1)
        self.assertEqual(s3.xpto, 123)
        s3.xpto = 456
        self.assertEqual(s3.xpto, 456)
        self.assertEqual(s1.xpto, 123)
        

    def test_refcounting_v2(self):
        zbr_count_before = foo.Zbr.instance_count

        obj = foo.SomeObject("")
        z1 = obj.get_internal_zbr()
        z2 = obj.get_internal_zbr()

        self.assert_(z1 is z2)

        del obj, z1, z2

        while gc.collect():
            pass

        zbr_count_after = foo.Zbr.instance_count

        self.assertEqual(zbr_count_after, zbr_count_before)

    def test_refcounting_v3(self):
        zbr_count_before = foo.Zbr.instance_count
        
        class MyZbr(foo.Zbr):
            pass
        z_in = MyZbr()
        obj = foo.SomeObject("")
        obj.set_zbr_transfer(z_in)
        del z_in
        
        z1 = obj.get_zbr()
        z2 = obj.get_zbr()
        self.assert_(z1 is z2)
        del obj, z1, z2

        while gc.collect():
            pass

        zbr_count_after = foo.Zbr.instance_count

        self.assertEqual(zbr_count_after, zbr_count_before)

    def test_refcounting_v4(self): # same as v3 but using peek_zbr instead of get_zbr
        zbr_count_before = foo.Zbr.instance_count
        
        class MyZbr(foo.Zbr):
            pass
        z_in = MyZbr()
        obj = foo.SomeObject("")
        obj.set_zbr_transfer(z_in)
        del z_in
        
        z1 = obj.peek_zbr()
        z2 = obj.peek_zbr()
        self.assert_(z1 is z2)
        del obj, z1, z2

        while gc.collect():
            pass

        zbr_count_after = foo.Zbr.instance_count

        self.assertEqual(zbr_count_after, zbr_count_before)

    def test_scan_containers_in_attributes(self):
        t = foo.TestContainer()
        v = list(t.m_floatSet)
        self.assertEqual(v, [1,2,3])

    def test_out_vec(self):
        t = foo.TestContainer()
        v = list(t.get_vec())
        self.assertEqual(v, ["hello", "world"])

    def test_ptr_vec(self):
        t = foo.TestContainer()
        t.set_vec_ptr(["hello", "world"])
        r = t.get_vec_ptr()
        self.assertEqual(list(r), ["hello", "world"])

    def test_richcompare(self):
        t1 = foo.Tupl()

        t1.x = 1
        t1.y = 1

        t2 = foo.Tupl()
        t2.x = 1
        t2.y = 1

        t3 = foo.Tupl()
        t3.x = 1
        t3.y = 2

        self.assert_(t1 == t2)
        self.assert_(not (t1 != t2))
        self.assert_(t1 <= t2)
        self.assert_(t1 >= t2)
        self.assert_(t3 >= t2)
        self.assert_(t3 > t2)
        self.assert_(t2 <= t3)
        self.assert_(t2 < t3)
        self.assert_(t2 != t3)
        self.assert_(not(t2 == t3))
        
    def test_numeric_operators(self):
        t1 = foo.Tupl()

        t1.x = 4
        t1.y = 6

        t2 = foo.Tupl()
        t2.x = 2
        t2.y = 3

        r = t1 + t2
        self.assertEqual(r.x, t1.x + t2.x)
        self.assertEqual(r.y, t1.y + t2.y)

        r = t1 - t2
        self.assertEqual(r.x, t1.x - t2.x)
        self.assertEqual(r.y, t1.y - t2.y)

        r = t1 * t2
        self.assertEqual(r.x, t1.x * t2.x)
        self.assertEqual(r.y, t1.y * t2.y)

        r = t1 / t2
        self.assertEqual(r.x, t1.x / t2.x)
        self.assertEqual(r.y, t1.y / t2.y)

    def test_int_typedef(self):
        rv = foo.xpto.get_flow_id(123)
        self.assertEqual(rv, 124)

    def test_virtual_method_reference_parameter(self):
        class MyReferenceManipulator(foo.ReferenceManipulator):
            def _do_manipulate_object(self, obj):
                obj.SetValue(12345)
        manip = MyReferenceManipulator()
        retval = manip.manipulate_object()
        self.assertEqual(retval, 12345)


if __name__ == '__main__':
    unittest.main()
