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
        
        
        
if __name__ == '__main__':
    unittest.main()
