import sys
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

if __name__ == '__main__':
    unittest.main()
