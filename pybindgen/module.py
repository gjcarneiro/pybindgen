"""
Code to generate code for a C/C++ Python extension module.
"""

from function import Function, OverloadedFunction
from typehandlers.base import CodeBlock, DeclarationsScope
from typehandlers.codesink import MemoryCodeSink
from cppclass import CppClass
from enum import Enum
import utils


class Module(dict):
    """
    A Module object takes care of generating the code for a Python module.

    Module objects can be indexed dictionary style to access contained types.  Example::

      >>> from enum import Enum
      >>> from cppclass import CppClass
      >>> m = Module("foo", cpp_namespace="foo")
      >>> subm = m.add_cpp_namespace("subm")
      >>> c1 = CppClass("Bar")
      >>> m.add_class(c1)
      >>> c2 = CppClass("Zbr")
      >>> subm.add_class(c2)
      >>> e1 = Enum("En1", ["XX"])
      >>> m.add_enum(e1)
      >>> e2 = Enum("En2", ["XX"])
      >>> subm.add_enum(e2)
      >>> m["Bar"] is c1
      True
      >>> m["foo::Bar"] is c1
      True
      >>> m["En1"] is e1
      True
      >>> m["foo::En1"] is e1
      True
      >>> m["badname"]
      Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
      KeyError: 'badname'
      >>> m["foo::subm::Zbr"] is c2
      True
      >>> m["foo::subm::En2"] is e2
      True

    """

    def __init__(self, name, parent=None, docstring=None, cpp_namespace=None):
        """
        @param name: module name
        @param parent: parent L{module<Module>} (i.e. the one that contains this submodule) or None if this is a root module
        @param docstring: docstring to use for this module
        @param cpp_namespace: C++ namespace prefix associated with this module
        """
        super(Module, self).__init__()
        self.name = name
        self.parent = parent
        self.docstring = docstring
        self.submodules = []
        self.enums = []
        self._forward_declarations_declared = False

        if parent is None:
            self.prefix = self.name
            error_return = 'return;'
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
        "get a submodule by its name"
        for submodule in self.submodules:
            if submodule.name == submodule_name:
                return submodule
        raise ValueError("submodule %s not found" % submodule_name)
        
    def get_root(self):
        "returns the root module (even it is self)"
        root = self
        while root.parent is not None:
            root = root.parent
        return root

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
        is called like this::

          python_name = transformer(c_name)
        """
        self.c_function_name_transformer = transformer

    def add_include(self, include):
        """
        Adds an additional include directive, needed to compile this python module

        @param include: the name of the header file to include, including
                   surrounding "" or <>.
        """
        include = utils.ascii(include)
        assert include.startswith('"') or include.startswith('<')
        assert include.endswith('"') or include.endswith('>')
        if include not in self.includes:
            self.includes.append(include)

    def add_function(self, wrapper, name=None):
        """
        Add a function to the module.

        @param wrapper: a Function instance that can generate the wrapper
        @param name: name of the module function as it will appear from
                Python side; if not given, the
                c_function_name_transformer callback, or strip_prefix,
                will be used to guess the Python name.
        """
        name = utils.ascii(name)
        assert isinstance(wrapper, Function)
        if name is None:
            name = self.c_function_name_transformer(wrapper.function_name)
        mangled_name = utils.get_mangled_name(name, wrapper.template_parameters)
        try:
            overload = self.functions[mangled_name]
        except KeyError:
            overload = OverloadedFunction(mangled_name)
            self.functions[mangled_name] = overload
        wrapper.module = self
        overload.add(wrapper)


    def add_class(self, class_):
        """
        Add a class to the module.

        @param class_: a CppClass object
        """
        assert isinstance(class_, CppClass)
        class_.module = self
        self.classes.append(class_)
        module = self
        self[class_.name] = class_
        while module is not None:
            module[class_.full_name] = class_
            module = module.parent

    def add_cpp_namespace(self, name):
        """
        Add a nested module namespace corresponding to a C++ namespace.
        Returns a Module object that maps to this namespace.
        """
        name = utils.ascii(name)
        return Module(name, parent=self, cpp_namespace=name)

    def add_enum(self, enum):
        """
        Add an enumeration.
        """
        assert isinstance(enum, Enum)
        self.enums.append(enum)
        enum.module = self
        self[enum.name] = enum
        module = self
        while module is not None:
            module[enum.full_name] = enum
            module = module.parent

    def declare_one_time_definition(self, definition_name):
        """
        Internal helper method for code geneneration to coordinate
        generation of code that can only be defined once per compilation unit

        (note: assuming here one-to-one mapping between 'module' and
        'compilation unit').

        @param definition_name: a string that uniquely identifies the code
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
        definition_name = utils.ascii(definition_name)
        if definition_name in self.one_time_definitions:
            raise KeyError
        self.one_time_definitions[definition_name] = None

    def generate_forward_declarations(self, code_sink):
        """generate forward declarations for types"""
        assert not self._forward_declarations_declared
        if self.classes:
            code_sink.writeln('/* --- forward declarations --- */')
            code_sink.writeln()
            for class_ in self.classes:
                class_.generate_forward_declarations(code_sink, self)
        ## recurse to submodules
        for submodule in self.submodules:
            submodule.generate_forward_declarations(code_sink)
        self._forward_declarations_declared = True

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
        if not self.cpp_namespace:
            names = []
        else:
            if self.cpp_namespace == '::':
                names = []
            else:
                names = self.cpp_namespace.split('::')
                if not names[0]:
                    del names[0]
        parent = self.parent
        while parent is not None:
            if parent.cpp_namespace and parent.cpp_namespace != '::':
                parent_names = parent.cpp_namespace.split('::')
                if not parent_names[0]:
                    del parent_names[0]
                names = parent_names + names
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
            if not self._forward_declarations_declared:
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
        py_method_defs = []
        if self.functions:
            code_sink.writeln('/* --- module functions --- */')
            code_sink.writeln()
            for func_name, overload in self.functions.iteritems():
                code_sink.writeln()
                #overload.generate(code_sink)
                try:
                    utils.call_with_error_handling(overload.generate, (code_sink,), {}, overload)
                except utils.SkipWrapper:
                    continue
                code_sink.writeln()
                py_method_defs.append(overload.get_py_method_def(func_name))

        ## generate the function table
        code_sink.writeln("static PyMethodDef %s_functions[] = {"
                          % (self.prefix,))
        code_sink.indent()
        for py_method_def in py_method_defs:
            code_sink.writeln(py_method_def)
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
        
