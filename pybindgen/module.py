"""
Code to generate code for a C/C++ Python extension module.
"""

from function import Function, OverloadedFunction
from typehandlers.base import CodeBlock, DeclarationsScope
from typehandlers.codesink import MemoryCodeSink
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
        self.functions = {} # name => OverloadedFunction
        self.classes = []
        self.header = MemoryCodeSink()
        self.includes = []
        self.before_init = CodeBlock('PyErr_Print();\nreturn;', self.declarations)
        self.after_init = CodeBlock('PyErr_Print();\nreturn;', self.declarations,
                                    predecessor=self.before_init)
        self.c_function_name_transformer = None
        self.set_strip_prefix(name + '_')
        self.one_time_definitions = {}

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

    def add_include(self, include):
        """
        Adds an additional include directive, needed to compile this python module

        include -- the name of the header file to include, including
                   surrounding "" or <>.
        """
        assert isinstance(include, str)
        assert include.startswith('"') or include.startswith('<')
        assert include.endswith('"') or include.endswith('>')
        if include not in self.includes:
            self.includes.append(include)

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
        try:
            overload = self.functions[name]
        except KeyError:
            overload = OverloadedFunction(name) # FIXME: name should be C function name
            self.functions[name] = overload
        overload.add(wrapper)


    def add_class(self, class_):
        """
        Add a class to the module.

        class_ -- a CppClass object
        """
        assert isinstance(class_, CppClass)
        self.classes.append(class_)


    def declare_one_time_definition(self, definition_name):
        """
        Internal helper method for code geneneration to coordinate
        generation of code that can only be defined once per module

        (note: assuming here one-to-one mapping between 'module' and
        'compilation unit').

        definition_name -- a string that uniquely identifies the code
        definition that will be added.  If the given definition was
        already declared KeyError is raised.
        
        >>> module = Module('foo')
        >>> module.declare_one_time_definition("zbr")
        >>> module.declare_one_time_definition("zbr")
        Traceback (most recent call last):
        ...
        KeyError
        >>> module.declare_one_time_definition("bar")
        """
        assert isinstance(definition_name, str)
        if definition_name in self.one_time_definitions:
            raise KeyError
        self.one_time_definitions[definition_name] = None


    def generate(self, code_sink, docstring=None):
        """Generates the module to a code sink"""

        outer_code_sink = code_sink
        code_sink = MemoryCodeSink()

        m = self.declarations.declare_variable('PyObject*', 'm')
        assert m == 'm'
        self.before_init.write_code(
            "m = Py_InitModule3(\"%s\", %s_functions, %s);"
            % (self.name, self.name,
               docstring and '"'+docstring+'"' or 'NULL'))
        self.before_init.write_error_check("m == NULL")

        ## generate forward declarations for types
        if self.classes:
            code_sink.writeln('/* --- forward declarations --- */')
            code_sink.writeln()
            for class_ in self.classes:
                class_.generate_forward_declarations(code_sink)


        ## generate the function wrappers
        if self.functions:
            code_sink.writeln('/* --- module functions --- */')
            code_sink.writeln()
            for func_name, overload in self.functions.iteritems():
                code_sink.writeln()
                overload.generate(code_sink)
                code_sink.writeln()

        ## generate the function table
        code_sink.writeln("static PyMethodDef %s_functions[] = {"
                          % (self.name,))
        code_sink.indent()
        for func_name, overload in self.functions.iteritems():
            code_sink.writeln(overload.get_py_method_def(func_name))
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")

        ## generate the classes
        if self.classes:
            code_sink.writeln('/* --- classes --- */')
            code_sink.writeln()
            for class_ in self.classes:
                code_sink.writeln()
                class_.generate(code_sink, self)
                code_sink.writeln()

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

        ## generate the include directives
        for include in self.includes:
            outer_code_sink.writeln("#include %s" % include)

        ## now assemble the codesink pieces
        self.header.flush_to(outer_code_sink)
        code_sink.flush_to(outer_code_sink)
        
