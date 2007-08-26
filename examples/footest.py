import sys
import weakref
import gc
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'build', 'default', 'examples'))
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
        obj = Test("xxx", "yyy")
        foo.store_some_object(obj)
        del obj
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
        foo1 = obj.function_that_returns_foo()
        self.assertEqual(foo1.get_datum(), "zpto")

        
    def test_implicit_conversion_constructor_value(self):
        zoo1 = foo.Zoo("zpto")
        try:
            obj = foo.ClassThatTakesFoo(zoo1)
        except TypeError:
            self.fail()
        foo1 = obj.get_foo()
        self.assertEqual(foo1.get_datum(), "zpto")


if __name__ == '__main__':
    unittest.main()
