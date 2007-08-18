"""
C function wrapper
"""
from typehandlers.base import ForwardWrapperBase
from typehandlers import codesink
import overloading


class Function(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C function.
    """

    def __init__(self, return_value, function_name, parameters, docstring=None):
        """
        return_value -- the function return value
        function_name -- name of the C function
        parameters -- the function parameters
        """
        super(Function, self).__init__(
            return_value, parameters,
            parse_error_return="return NULL;",
            error_return="return NULL;")
        self.function_name = function_name
        self.wrapper_base_name = "_wrap_%s" % (self.function_name,)
        self.wrapper_actual_name = None
        self.docstring = docstring
    
    def generate_call(self):
        "virtual method implementation; do not call"
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' % (self.function_name, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = %s(%s);' % (self.function_name, ", ".join(self.call_params)))

    def generate(self, code_sink, wrapper_name=None, extra_wrapper_params=()):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        wrapper_name -- name of wrapper function
        """
        if wrapper_name is None:
            self.wrapper_actual_name = self.wrapper_base_name
        else:
            self.wrapper_actual_name = wrapper_name
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject *")
        prototype_line = ("%s(PyObject * PYBINDGEN_UNUSED dummy, "
                          "PyObject *args, PyObject *kwargs") % (self.wrapper_actual_name,)
        if extra_wrapper_params:
            prototype_line += ", " + ", ".join(extra_wrapper_params)
        prototype_line += ')'
        code_sink.writeln(prototype_line)
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')
        

    def get_py_method_def(self, name):
        """Returns an array element to use in a PyMethodDef table.
         Should only be called after code generation.

        name -- python function/method name
        """
        flags = self.get_py_method_def_flags()
        return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
               (name, self.wrapper_actual_name, '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))


class OverloadedFunction(overloading.OverloadedWrapper):
    RETURN_TYPE = 'PyObject *'
    ERROR_RETURN = 'return NULL;'

