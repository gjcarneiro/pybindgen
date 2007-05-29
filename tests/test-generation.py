#!/usr/bin/env python

import sys

try:
    path = sys.argv[1]
except IndexError:
    path = '..'
sys.path.insert(0, path)

from pybindgen import typehandlers
from pybindgen.typehandlers import codesink
from pybindgen.typehandlers.base import Parameter

class MyReverseWrapper(typehandlers.base.ReverseWrapperBase):
    def generate_python_call(self):
        params = ['NULL'] # function object to call
        params.extend(self.build_params.get_parameters())
        self.before_call.write_code('py_retval = PyObject_CallFunction(%s);' % (', '.join(params),))
        self.before_call.write_error_check('py_retval == NULL')

class MyForwardWrapper(typehandlers.base.ForwardWrapperBase):

    def __init__(self, return_value, parameters, function_name):
        super(MyForwardWrapper, self).__init__(
            return_value, parameters,
            parse_error_return="return NULL;",
            error_return="return NULL;")
        self.function_name = function_name
    
    def generate_call(self):
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' % (self.function_name, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = %s(%s);' % (self.function_name, ", ".join(self.call_params)))

    def generate(self, code_sink):
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject *")
        code_sink.writeln("_wrap_%s(PyObject *args, PyObject *kwargs)" % (self.function_name,))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')

        

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
    
    ## test generic forward wrappers
    for return_type, return_handler in typehandlers.base.return_type_matcher.items():
        for param_type, param_handler in typehandlers.base.param_type_matcher.items():
            for direction in param_handler.DIRECTIONS:
                wrapper_number += 1
                function_name = '_test_function_%i' % (wrapper_number,)
                ## declare a fake prototype
                print "%s %s(%s);" % (return_type, function_name, param_type)
                print

                if direction == (Parameter.DIRECTION_IN):
                    param_name = 'param'
                elif direction == (Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT):
                    param_name = 'param_inout'
                elif direction == (Parameter.DIRECTION_OUT):
                    param_name = 'param_out'
                wrapper = MyForwardWrapper(return_handler(return_type),
                                           [param_handler(param_type, param_name, direction)],
                                           function_name)
                try:
                    wrapper.generate(code_out)
                except typehandlers.base.CodeGenerationError, ex:
                    print >> sys.stderr, "SKIPPING %s %s(%s): %s" % \
                          (return_type, function_name, param_type, str(ex))
                print
    

if __name__ == '__main__':
    test()
