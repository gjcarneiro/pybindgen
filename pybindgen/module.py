"""
Code to generate code for a C/C++ Python extension module.
"""

from functionwrapper import FunctionWrapper
from typehandlers.base import CodeBlock

class Module(object):
    """
    A Module object takes care of generating the code for a Python module.
    """

    def __init__(self, name):
        """Constructor
        name -- module name
        """
        self.name = name
        self.functions = [] # (name, wrapper) pairs
        self.before_init = CodeBlock('return;')
        self.after_init = CodeBlock('return;', predecessor=self.before_init)
        self.c_function_name_transformer = None
        self.set_strip_prefix(name + '_')

    def set_strip_prefix(self, prefix):
        """Sets the prefix string to be used when transforming a C
        function name into the python function name; the given prefix
        string is removed from the C function name."""

        def strip_prefix(c_name):
            """A C funtion name transformer that simply strips a
            common prefix from the name"""
            if c_name.startswith(prefix):
                return c_name[len(prefix):]
            else:
                return c_name
        self.c_function_name_transformer = strip_prefix

    def set_c_function_name_transformer(self, transformer):
        """Sets the function to be used when transforming a C function
        name into the python function name; the given given function
        is called like this:

        python_name = transformer(c_name)
        """
        self.c_function_name_transformer = transformer

    def add_function(self, wrapper, name=None):
        """
        Add a function to the module.

        wrapper -- a FunctionWrapper instance that can generate the wrapper
        name -- name of the module function as it will appear from
                Python side; if not given, the
                c_function_name_transformer callback, or strip_prefix,
                will be used to guess the Python name.
        """
        assert name is None or isinstance(name, str)
        assert isinstance(wrapper, FunctionWrapper)
        if name is None:
            name = self.c_function_name_transformer(wrapper.function_name)
        self.functions.append((name, wrapper))

    def generate(self, code_sink, docstring=None):
        """Generates the module to a code sink"""
        self.before_init.write_error_check("!Py_InitModule3(\"%s\", %s_functions, %s)"
                                           % (self.name, self.name,
                                              docstring and '"'+docstring+'"' or 'NULL'))
        self.after_init.write_cleanup()

        ## generate the function wrappers
        for func_name, func_wrapper in self.functions:
            code_sink.writeln()
            func_wrapper.generate(code_sink)
            code_sink.writeln()

        ## generate the function table
        code_sink.writeln("static PyMethodDef %s_functions[] = {" % (self.name,))
        code_sink.indent()
        for func_name, func_wrapper in self.functions:
            code_sink.writeln(func_wrapper.get_py_method_def(func_name))
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")
        
        ## now generate the module init function itself
        code_sink.writeln()
        code_sink.writeln("PyMODINIT_FUNC")
        code_sink.writeln("init%s(void)" % (self.name,))
        code_sink.writeln('{')
        code_sink.indent()
        self.before_init.sink.flush_to(code_sink)
        self.after_init.sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')

        
