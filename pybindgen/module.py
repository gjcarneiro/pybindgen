"""
Code to generate code for a C/C++ Python extension module.
"""

from function import Function, OverloadedFunction
from typehandlers.base import CodeBlock, DeclarationsScope
from typehandlers.codesink import MemoryCodeSink
from cppclass import CppClass
from enum import Enum


class Module(object):
    """
    A Module object takes care of generating the code for a Python module.
    """

    def __init__(self, name, parent=None, docstring=None, cpp_namespace=None):
        """Constructor
        name -- module name
        """
        self.name = name
        self.parent = parent
        self.docstring = docstring
        self.submodules = []
        self.enums = []

        if parent is None:
            self.prefix = self.name
            error_return = 'PyErr_Print();\nreturn;'
        else:
            parent.submodules.append(self)
            self.prefix = parent.prefix + "_" + self.name
            error_return = 'return NULL;'

        self.cpp_namespace = cpp_namespace
        path = self.get_namespace_path()
        if path and path[0] == '::':
            del path[0]
        self.cpp_namespace_prefix = '::'.join(path)

        self.init_function_name = "init%s" % self.prefix
        self.declarations = DeclarationsScope()
        self.functions = {} # name => OverloadedFunction
        self.classes = []
        self.header = MemoryCodeSink()
        self.before_init = CodeBlock(error_return, self.declarations)
        self.after_init = CodeBlock(error_return, self.declarations,
                                    predecessor=self.before_init)
        self.c_function_name_transformer = None
        self.set_strip_prefix(name + '_')
        if parent is None:
            self.one_time_definitions = {}
            self.includes = []
        else:
            self.one_time_definitions = parent.one_time_definitions
            self.includes = parent.includes

    def get_submodule(self, submodule_name):
        for submodule in self.submodules:
            if submodule.name == submodule_name:
                return submodule
        raise ValueError("submodule %s not found" % submodule_name)
        
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
        wrapper.module = self
        overload.add(wrapper)


    def add_class(self, class_):
        """
        Add a class to the module.

        class_ -- a CppClass object
        """
        assert isinstance(class_, CppClass)
        class_.module = self
        self.classes.append(class_)

    def add_cpp_namespace(self, name):
        """
        Add a nested module namespace corresponding to a C++ namespace.
        Returns a Module object that maps to this namespace.
        """
        assert isinstance(name, str)
        return Module(name, parent=self, cpp_namespace=name)

    def add_enum(self, enum):
        """
        Add an enumeration.
        """
        assert isinstance(enum, Enum)
        self.enums.append(enum)
        enum.module = self

    def declare_one_time_definition(self, definition_name):
        """
        Internal helper method for code geneneration to coordinate
        generation of code that can only be defined once per compilation unit

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

    def generate_forward_declarations(self, code_sink):
        """generate forward declarations for types"""
        if self.classes:
            code_sink.writeln('/* --- forward declarations --- */')
            code_sink.writeln()
            for class_ in self.classes:
                class_.generate_forward_declarations(code_sink)
        ## recurse to submodules
        for submodule in self.submodules:
            submodule.generate_forward_declarations(code_sink)

    def get_module_path(self):
        """Get the full [module, submodule, submodule,...] path """
        names = [self.name]
        parent = self.parent
        while parent is not None:
            names.insert(0, parent.name)
            parent = parent.parent
        return names

    def get_namespace_path(self):
        """Get the full [root_namespace, namespace, namespace,...] path """
        if self.cpp_namespace is None:
            names = []
        else:
            names = [self.cpp_namespace]
        parent = self.parent
        while parent is not None:
            if parent.cpp_namespace is not None:
                names.insert(0, parent.cpp_namespace)
            parent = parent.parent
        return names

    def generate(self, code_sink):
        """Generates the module to a code sink"""
        includes_code_sink = code_sink
        main_code_sink = MemoryCodeSink()
        self.do_generate(main_code_sink, includes_code_sink)
        main_code_sink.flush_to(code_sink)

    def do_generate(self, code_sink, includes_code_sink):
        """Generates the module"""
        if self.parent is None:
            self.generate_forward_declarations(code_sink)

        ## generate the submodules
        for submodule in self.submodules:
            submodule.do_generate(code_sink, includes_code_sink)

        m = self.declarations.declare_variable('PyObject*', 'm')
        assert m == 'm'
        self.before_init.write_code(
            "m = Py_InitModule3(\"%s\", %s_functions, %s);"
            % ('.'.join(self.get_module_path()), self.prefix,
               self.docstring and '"'+self.docstring+'"' or 'NULL'))
        self.before_init.write_error_check("m == NULL")

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
                          % (self.prefix,))
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

        ## generate the enums
        if self.enums:
            code_sink.writeln('/* --- enumerations --- */')
            code_sink.writeln()
            for enum in self.enums:
                code_sink.writeln()
                enum.generate(code_sink)
                code_sink.writeln()

        ## register the submodules
        if self.submodules:
            submodule_var = self.declarations.declare_variable('PyObject*', 'submodule')
        for submodule in self.submodules:
            self.after_init.write_code('%s = %s();' % (
                    submodule_var, submodule.init_function_name))
            self.after_init.write_error_check('%s == NULL' % submodule_var)
            self.after_init.write_code('Py_INCREF(%s);' % (submodule_var,))
            self.after_init.write_code('PyModule_AddObject(m, "%s", %s);'
                                       % (submodule.name, submodule_var,))

        ## now generate the module init function itself
        code_sink.writeln()
        if self.parent is None:
            code_sink.writeln("PyMODINIT_FUNC")
        else:
            code_sink.writeln("static PyObject *")
        code_sink.writeln("%s(void)" % (self.init_function_name,))
        code_sink.writeln('{')
        code_sink.indent()
        self.declarations.get_code_sink().flush_to(code_sink)
        self.before_init.sink.flush_to(code_sink)
        self.after_init.write_cleanup()
        self.after_init.sink.flush_to(code_sink)
        if self.parent is not None:
            code_sink.writeln("return m;")
        code_sink.unindent()
        code_sink.writeln('}')

        ## generate the include directives
        for include in self.includes:
            includes_code_sink.writeln("#include %s" % include)

        ## append the 'header' section to the 'includes' section
        self.header.flush_to(includes_code_sink)
        
