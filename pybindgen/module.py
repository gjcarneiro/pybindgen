"""
Objects that represent -- and generate code for -- C/C++ Python extension modules.

Modules and Sub-modules
=======================

A L{Module} object takes care of generating the code for a Python
module.  The way a Python module is organized is as follows.  There is
one "root" L{Module} object. There can be any number of
L{SubModule}s. Sub-modules themselves can have additional sub-modules.
Calling L{Module.generate} on the root module will trigger code
generation for the whole module, not only functions and types, but
also all its sub-modules.

In Python, a sub-module will appear as a I{built-in} Python module
that is available as an attribute of its parent module.  For instance,
a module I{foo} having a sub-module I{xpto} appears like this::

    >>> import foo
    >>> foo.xpto
    <module 'foo.xpto' (built-in)>

Modules and C++ namespaces
==========================

Modules can be associated with specific C++ namespaces.  This means,
for instance, that any C++ class wrapped inside that module must
belong to that C++ namespace.  Example::

    >>> from cppclass import *
    >>> mod = Module("foo", cpp_namespace="::foo")
    >>> mod.add_class("Bar")
    <pybindgen.CppClass 'foo::Bar'>

When we have a toplevel C++ namespace which contains another nested
namespace, we want to wrap the nested namespace as a Python
sub-module.  The method L{ModuleBase.add_cpp_namespace} makes it easy
to create sub-modules for wrapping nested namespaces.  For instance::

    >>> from cppclass import *
    >>> mod = Module("foo", cpp_namespace="::foo")
    >>> submod = mod.add_cpp_namespace('xpto')
    >>> submod.add_class("Bar")
    <pybindgen.CppClass 'foo::xpto::Bar'>

"""

from function import Function, OverloadedFunction, CustomFunctionWrapper
from typehandlers.base import CodeBlock, DeclarationsScope
from typehandlers.codesink import MemoryCodeSink
from cppclass import CppClass
from enum import Enum
import utils
import warnings


class ModuleBase(dict):
    """
    ModuleBase objects can be indexed dictionary style to access contained types.  Example::

      >>> from enum import Enum
      >>> from cppclass import CppClass
      >>> m = Module("foo", cpp_namespace="foo")
      >>> subm = m.add_cpp_namespace("subm")
      >>> c1 = m.add_class("Bar")
      >>> c2 = subm.add_class("Zbr")
      >>> e1 = m.add_enum("En1", ["XX"])
      >>> e2 = subm.add_enum("En2", ["XX"])
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
        Note: this is an abstract base class, see L{Module}
        @param name: module name
        @param parent: parent L{module<Module>} (i.e. the one that contains this submodule) or None if this is a root module
        @param docstring: docstring to use for this module
        @param cpp_namespace: C++ namespace prefix associated with this module
        @return: a new module object
        """
        super(ModuleBase, self).__init__()
        self.parent = parent
        self.docstring = docstring
        self.submodules = []
        self.enums = []
        self._forward_declarations_declared = False

        self.cpp_namespace = cpp_namespace
        if self.parent is None:
            error_return = 'return;'
        else:
            self.parent.submodules.append(self)
            error_return = 'return NULL;'

        self.prefix = None
        self.init_function_name = None
        self._name = None
        self.name = name

        path = self.get_namespace_path()
        if path and path[0] == '::':
            del path[0]
        self.cpp_namespace_prefix = '::'.join(path)

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

    def get_name(self):
        return self._name

    def set_name(self, name):
        self._name = name

        if self.parent is None:
            self.prefix = self.name
        else:
            self.prefix = self.parent.prefix + "_" + self.name

        self.init_function_name = "init%s" % self.prefix

    
    name = property(get_name, set_name)

    def get_submodule(self, submodule_name):
        "get a submodule by its name"
        for submodule in self.submodules:
            if submodule.name == submodule_name:
                return submodule
        raise ValueError("submodule %s not found" % submodule_name)
        
    def get_root(self):
        "@return: the root L{Module} (even if it is self)"
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

    def _add_function_obj(self, wrapper):
        assert isinstance(wrapper, Function)
        name = utils.ascii(wrapper.custom_name)
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

    def add_function(self, *args, **kwargs):
        """
        Add a function to the module/namespace. See the documentation for
        L{Function.__init__} for information on accepted parameters.
        """
        if len(args) >= 1 and isinstance(args[0], Function):
            func = args[0]
            warnings.warn("add_function has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
            if len(args) == 2:
                func.custom_name = args[1]
            elif 'name' in kwargs:
                assert len(args) == 1
                func.custom_name = kwargs['name']
            else:
                assert len(args) == 1
                assert len(kwargs) == 0
        else:
            func = Function(*args, **kwargs)
        self._add_function_obj(func)
        return func

    def add_custom_function_wrapper(self, *args, **kwargs):
        """
        Add a function, using custom wrapper code, to the module/namespace. See the documentation for
        L{CustomFunctionWrapper.__init__} for information on accepted parameters.
        """
        func = CustomFunctionWrapper(*args, **kwargs)
        self._add_function_obj(func)
        return func

    def register_type(self, name, full_name, type_wrapper):
        """
        Register a type wrapper with the module, for easy access in
        the future.  Normally should not be called by the programmer,
        as it is meant for internal pybindgen use and called automatically.
        
        @param name: type name without any C++ namespace prefix, or None
        @param full_name: type name with a C++ namespace prefix, or None
        @param type_wrapper: the wrapper object for the type (e.g. L{CppClass} or L{Enum})
        """
        module = self
        if name:
            module[name] = type_wrapper
        if full_name:
            while module is not None:
                module[full_name] = type_wrapper
                module = module.parent

    def _add_class_obj(self, class_):
        """
        Add a class to the module.

        @param class_: a CppClass object
        """
        assert isinstance(class_, CppClass)
        class_.module = self
        self.classes.append(class_)
        self.register_type(class_.name, class_.full_name, class_)

    def add_class(self, *args, **kwargs):
        """
        Add a class to the module. See the documentation for
        L{CppClass.__init__} for information on accepted parameters.
        """
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], CppClass):
            cls = args[0]
            warnings.warn("add_class has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
        else:
            cls = CppClass(*args, **kwargs)
        self._add_class_obj(cls)
        return cls

    def add_cpp_namespace(self, name):
        """
        Add a nested module namespace corresponding to a C++ namespace.

        @param name: name of C++ namespace (just the last component,
        not full scoped name); this also becomes the name of the
        submodule.

        @return: a L{SubModule} object that maps to this namespace.
        """
        name = utils.ascii(name)
        return SubModule(name, parent=self, cpp_namespace=name)

    def _add_enum_obj(self, enum):
        """
        Add an enumeration.
        """
        assert isinstance(enum, Enum)
        self.enums.append(enum)
        enum.module = self
        self.register_type(enum.name, enum.full_name, enum)

    def add_enum(self, *args, **kwargs):
        """
        Add an enumeration to the module. See the documentation for
        L{Enum.__init__} for information on accepted parameters.
        """
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], Enum):
            enum = args[0]
            warnings.warn("add_enum has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
        else:
            enum = Enum(*args, **kwargs)
        self._add_enum_obj(enum)
        return enum

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
        """(internal) generate forward declarations for types"""
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
        """Get the full [root_namespace, namespace, namespace,...] path (C++)"""
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

    def do_generate(self, code_sink, includes_code_sink):
        """(internal) Generates the module."""
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

        ## generate the include directives (only the root module)
        if self.parent is None:
            for include in self.includes:
                includes_code_sink.writeln("#include %s" % include)

        ## append the 'header' section to the 'includes' section
        self.header.flush_to(includes_code_sink)
    
    def __repr__(self):
        return "<pybindgen.module.Module %r>" % self.name
        

class Module(ModuleBase):
    def __init__(self, name, docstring=None, cpp_namespace=None):
        """
        @param name: module name
        @param docstring: docstring to use for this module
        @param cpp_namespace: C++ namespace prefix associated with this module
        """
        super(Module, self).__init__(name, docstring=docstring, cpp_namespace=cpp_namespace)

    def generate(self, code_sink):
        """Generates the module to a code sink"""
        includes_code_sink = code_sink
        main_code_sink = MemoryCodeSink()
        self.do_generate(main_code_sink, includes_code_sink)
        main_code_sink.flush_to(code_sink)



class SubModule(ModuleBase):
    def __init__(self, name, parent, docstring=None, cpp_namespace=None):
        """
        @param parent: parent L{module<Module>} (i.e. the one that contains this submodule)
        @param name: name of the submodule
        @param docstring: docstring to use for this module
        @param cpp_namespace: C++ namespace component associated with this module
        """
        super(SubModule, self).__init__(name, parent, docstring=docstring, cpp_namespace=cpp_namespace)

