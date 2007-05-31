#!/usr/bin/env python

import sys

try:
    path = sys.argv[1]
except IndexError:
    path = '..'
sys.path.insert(0, path)

from pybindgen import typehandlers
from pybindgen.typehandlers import codesink
from pybindgen.typehandlers.base import Parameter, ReturnValue
from pybindgen.functionwrapper import FunctionWrapper
from pybindgen.module import Module


class MyReverseWrapper(typehandlers.base.ReverseWrapperBase):
    def generate_python_call(self):
        params = ['NULL'] # function object to call
        params.extend(self.build_params.get_parameters())
        self.before_call.write_code('py_retval = PyObject_CallFunction(%s);' % (', '.join(params),))
        self.before_call.write_error_check('py_retval == NULL')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')

        

def test():
    print "#include <Python.h>"
    print "#include <string>"
    print
    
    code_out = codesink.FileCodeSink(sys.stdout)
    wrapper_number = 0

    ## test generic reverse wrappers
    for return_type, return_handler in typehandlers.base.return_type_matcher.items():
        for param_type, param_handler in typehandlers.base.param_type_matcher.items():
            for direction in param_handler.DIRECTIONS:
                if direction == (Parameter.DIRECTION_IN):
                    param_name = 'param'
                elif direction == (Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT):
                    param_name = 'param_inout'
                elif direction == (Parameter.DIRECTION_OUT):
                    param_name = 'param_out'
                wrapper = MyReverseWrapper(return_handler(return_type),
                                           [param_handler(param_type, param_name, direction)])
                wrapper_number += 1
                wrapper.generate(code_out,
                                 '_test_wrapper_number_%i' % (wrapper_number,),
                                 ['static'])
                print
    
    ## test generic forward wrappers, and module
    module = Module("foo")
    
    function_defs = []
    for return_type, return_handler in typehandlers.base.return_type_matcher.items():
        for param_type, param_handler in typehandlers.base.param_type_matcher.items():
            for direction in param_handler.DIRECTIONS:
                wrapper_number += 1
                function_name = 'foo_function_%i' % (wrapper_number,)
                ## declare a fake prototype
                print "%s %s(%s);" % (return_type, function_name, param_type)
                print
                if direction == (Parameter.DIRECTION_IN):
                    param_name = 'param'
                elif direction == (Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT):
                    param_name = 'param_inout'
                elif direction == (Parameter.DIRECTION_OUT):
                    param_name = 'param_out'
                wrapper = FunctionWrapper(return_handler(return_type), function_name,
                                          [param_handler(param_type, param_name, direction)])

                module.add_function(wrapper)

    module.generate(code_out)



if __name__ == '__main__':
    test()
