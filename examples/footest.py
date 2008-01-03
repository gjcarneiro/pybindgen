import sys
import weakref
import gc
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'build', 'default', 'examples'))
if len(sys.argv) > 1:
    import foo2 as foo
    del sys.argv[1]
else:
    import foo
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
        obj = foo.SomeObject("xpto")
        self.assertEqual(obj.get_something_prefixed("something"), "xptosomething")

    def test_function_as_method_val(self):
        obj = foo.SomeObject("xpto")
        self.assertEqual(obj.val_get_something_prefixed("something"), "xptosomething")

    def test_function_as_method_ref(self):
        obj = foo.SomeObject("xpto")
        self.assertEqual(obj.ref_get_something_prefixed("something"), "xptosomething")

    def test_enum(self):
        foo.xpto.set_foo_type(foo.xpto.FOO_TYPE_BBB)
        self.assertEqual(foo.xpto.get_foo_type(), foo.xpto.FOO_TYPE_BBB)

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

if __name__ == '__main__':
    unittest.main()
