#! /usr/bin/env python

import sys

import pybindgen
from pybindgen import ReturnValue, Parameter, Module, Function, FileCodeSink
from pybindgen import CppMethod, CppConstructor, CppClass, Enum
from pybindgen.typehandlers.base import ForwardWrapperBase
from pybindgen.typehandlers import base as typehandlers

class SharedPtrTransformation(typehandlers.TypeTransformation):
    def get_untransformed_name(self, name):
        if name == 'TestClass::Ptr':
            return 'TestClass *'
        return name

    def create_type_handler(self, type_handler, *args, **kwargs):
        if issubclass(type_handler, Parameter):
            kwargs['transfer_ownership'] = False
        elif issubclass(type_handler, ReturnValue):
            kwargs['caller_owns_return'] = False
        else:
            raise AssertionError
        handler = type_handler(*args, **kwargs)
        handler.set_transformation(self, self.get_untransformed_name(args[0]))
        return handler

    def untransform(self, type_handler, declarations, code_block, expression):
        return '(%s).get()' % (expression,)

    def transform(self, type_handler, declarations, code_block, expression):
        assert type_handler.untransformed_ctype[-1] == '*' # make sure it's a pointer
        return 'TestClass::Ptr (expression)'

transf = SharedPtrTransformation()
typehandlers.return_type_matcher.register_transformation(transf)
typehandlers.param_type_matcher.register_transformation(transf)
del transf


def my_module_gen(out_file):

    mod = Module('c')
    mod.add_include('"c.h"')

    mod.add_class('TestClass')

    mod.add_function("someFct", 'TestClass::Ptr', [])

    mod.generate(FileCodeSink(out_file))

if __name__ == '__main__':
    my_module_gen(sys.stdout)
