import sys
import gc
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', 'build', 'default', 'examples', 'c-hello'))
import hello
import unittest


class TestHello(unittest.TestCase):

    def test_func(self):
        x = hello.sum(1, 2)
        self.assertEqual(x, 3)

    def test_foo(self):
        foo = hello.Foo()
        data = foo.get_data()
        self.assertEqual(data, '')
        del foo
        while gc.collect():
            pass


if __name__ == '__main__':
    unittest.main()
