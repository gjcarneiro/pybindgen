"""
Code to generate code for a C/C++ Python extension module.
"""

from function import Function
from typehandlers.base import CodeBlock, DeclarationsScope
from cppclass import CppClass


class Module(object):
    """
    A Module object takes care of generating the code for a Python module.
    """

    def __init__(self, name):
        """Constructor
        name -- module name
        """
        self.declarations = DeclarationsScope()
        self.name = name
        self.functions = [] # (name, wrapper) pairs
        self.classes = []
        self.before_init = CodeBlock('PyErr_Print();\nreturn;')
        self.after_init = CodeBlock('PyErr_Print();\nreturn;',
                                    predecessor=self.before_init)
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

        wrapper -- a Function instance that can generate the wrapper
        name -- name of the module function as it will appear from
                Python side; if not given, the
                c_function_name_transformer callback, or strip_prefix,
                will be used to guess the Python name.
        """
        assert name is None or isinstance(name, str)
        assert isinstance(wrapper, Function)
        if name is None:
            name = self.c_function_name_transformer(wrapper.function_name)
        self.functions.append((name, wrapper))


    def add_class(self, class_):
        """
        Add a class to the module.

        class_ -- a CppClass object
        """
        assert isinstance(class_, CppClass)
        self.classes.append(class_)


    def generate(self, code_sink, docstring=None):
        """Generates the module to a code sink"""
        m = self.declarations.declare_variable('PyObject*', 'm')
        assert m == 'm'
        self.before_init.write_code(
            "m = Py_InitModule3(\"%s\", %s_functions, %s);"
            % (self.name, self.name,
               docstring and '"'+docstring+'"' or 'NULL'))
        self.before_init.write_error_check("m == NULL")

        ## generate the function wrappers
        for func_name, func_wrapper in self.functions:
            code_sink.writeln()
            func_wrapper.generate(code_sink)
            code_sink.writeln()

        ## generate the function table
        code_sink.writeln("static PyMethodDef %s_functions[] = {"
                          % (self.name,))
        code_sink.indent()
        for func_name, func_wrapper in self.functions:
            code_sink.writeln(func_wrapper.get_py_method_def(func_name))
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")

        ## generate the classes
        for class_ in self.classes:
            code_sink.writeln()
            class_.generate(code_sink)
            code_sink.writeln()

            ## register the class type
            self.after_init.write_error_check('PyType_Ready(&%s)'
                                              % (class_.pytypestruct,))
            ## add to the module dict
            self.after_init.write_code(
                'PyModule_AddObject(m, \"%s\", (PyObject *) &%s);' % (
                class_.name, class_.pytypestruct))
        
        
        ## now generate the module init function itself
        code_sink.writeln()
        code_sink.writeln("PyMODINIT_FUNC")
        code_sink.writeln("init%s(void)" % (self.name,))
        code_sink.writeln('{')
        code_sink.indent()
        self.declarations.get_code_sink().flush_to(code_sink)
        self.before_init.sink.flush_to(code_sink)
        self.after_init.write_cleanup()
        self.after_init.sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')

        
