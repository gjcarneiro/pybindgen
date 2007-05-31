"""
C function wrapper
"""
from typehandlers.base import ForwardWrapperBase
from typehandlers import codesink


class FunctionWrapper(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C function.
    """

    def __init__(self, return_value, parameters, function_name):
        """
        return_value -- the function return value
        parameters -- the function parameters
        function_name -- name of the C function
        """
        super(FunctionWrapper, self).__init__(
            return_value, parameters,
            parse_error_return="return NULL;",
            error_return="return NULL;")
        self.function_name = function_name
    
    def generate_call(self):
        "virtual method implementation; do not call"
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' % (self.function_name, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = %s(%s);' % (self.function_name, ", ".join(self.call_params)))

    def generate(self, code_sink):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        """
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject *")
        code_sink.writeln("_wrap_%s(PyObject *args, PyObject *kwargs)"
                          % (self.function_name,))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')
