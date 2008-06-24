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
from typehandlers.codesink import MemoryCodeSink, CodeSink, FileCodeSink, NullCodeSink
from cppclass import CppClass
from enum import Enum
import utils
import warnings
import traceback


class MultiSectionFactory(object):
    """
    Abstract base class for objects providing support for
    multi-section code generation, i.e., splitting the generated C/C++
    code into multiple files.  The generated code will generally have
    the following structure:

       1. For each section there is one source file specific to that section;

       2. There is a I{main} source file, e.g. C{foomodule.cc}.  Code
       that does not belong to any section will be included in this
       main file;

       3. Finally, there is a common header file, (e.g. foomodule.h),
       which is included by the main file and section files alike.
       Typically this header file contains function prototypes and
       type definitions.

    @see: L{Module.enable_multi_section}

    """
    def get_section_code_sink(self, section_name):
        """
        Create and/or return a code sink for a given section.
        @param section_name: name of the section
        @returns: a L{CodeSink} object that will receive generated code belonging to the section C{section_name}
        """
        raise NotImplementedError
    def get_main_code_sink(self):
        """
        Create and/or return a code sink for the main file.
        """
        raise NotImplementedError
    def get_common_header_code_sink(self):
        """
        Create and/or return a code sink for the common header.
        """
        raise NotImplementedError
    def get_common_header_include(self):
        """
        Return the argument for an #include directive to include the common header.

        @returns: a string with the header name, including surrounding
        "" or <>.  For example, '"foomodule.h"'.
        """
        raise NotImplementedError


class _SinkManager(object):
    """
    Internal abstract base class for bridging differences between
    multi-file and single-file code generation.
    """
    def get_code_sink_for_wrapper(self, wrapper):
        """
        @param wrapper: wrapper object
        @returns: (body_code_sink, header_code_sink) 
        """
        raise NotImplementedError
    def get_includes_code_sink(self):
        raise NotImplementedError
    def get_main_code_sink(self):
        raise NotImplementedError
    def close(self):
        raise NotImplementedError

class _MultiSectionSinkManager(_SinkManager):
    """
    Sink manager that deals with multi-section code generation.
    """
    def __init__(self, multi_section_factory):
        super(_MultiSectionSinkManager, self).__init__()
        self.multi_section_factory = multi_section_factory
        utils.write_preamble(self.multi_section_factory.get_common_header_code_sink())
        self.multi_section_factory.get_main_code_sink().writeln(
            "#include %s" % self.multi_section_factory.get_common_header_include())
        self._already_initialized_sections = {}

    def get_code_sink_for_wrapper(self, wrapper):
        header_sink = self.multi_section_factory.get_common_header_code_sink()
        section = getattr(wrapper, "section", None)
        if section is None:
            return self.multi_section_factory.get_main_code_sink(), header_sink
        else:
            section_sink = self.multi_section_factory.get_section_code_sink(section)
            if section not in self._already_initialized_sections:
                self._already_initialized_sections[section] = True
                section_sink.writeln("#include %s" % self.multi_section_factory.get_common_header_include())
            return section_sink, header_sink
    def get_includes_code_sink(self):
        return self.multi_section_factory.get_common_header_code_sink()
    def get_main_code_sink(self):
        return self.multi_section_factory.get_main_code_sink()
    def close(self):
        pass

class _MonolithicSinkManager(_SinkManager):
    """
    Sink manager that deals with single-section monolithic code generation.
    """
    def __init__(self, code_sink):
        super(_MonolithicSinkManager, self).__init__()
        self.code_sink = code_sink
        self.null_sink = NullCodeSink()
        utils.write_preamble(code_sink)
    def get_code_sink_for_wrapper(self, dummy_wrapper):
        return self.code_sink, self.code_sink
    def get_includes_code_sink(self):
        return self.code_sink
    def get_main_code_sink(self):
        return self.code_sink
    def close(self):
        pass


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
            self.after_forward_declarations = MemoryCodeSink()
        else:
            self.after_forward_declarations = None
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
        self.before_init = CodeBlock(error_return, self.declarations)
        self.after_init = CodeBlock(error_return, self.declarations,
                                    predecessor=self.before_init)
        self.c_function_name_transformer = None
        self.set_strip_prefix(name + '_')
        if parent is None:
            self.header = MemoryCodeSink()
            self.body = MemoryCodeSink()
            self.one_time_definitions = {}
            self.includes = []
        else:
            self.header = parent.header
            self.body = parent.body
            self.one_time_definitions = parent.one_time_definitions
            self.includes = parent.includes

        self._current_section = '__main__'

    def get_current_section(self):
        return self.get_root()._current_section
    current_section = property(get_current_section)

    def begin_section(self, section_name):
        """
        Declare that types and functions registered with the module in
        the future belong to the section given by that section_name
        parameter, until a matching end_section() is called.

        @note: L{begin_section}/L{end_section} are silently ignored
        unless a L{MultiSectionFactory} object is used as code
        generation output.
        """
        if self.current_section != '__main__':
            raise ValueError("begin_section called while current section not ended")
        if section_name == '__main__':
            raise ValueError ("__main__ not allowed as section name")
        assert self.parent is None
        self._current_section = section_name
        
    def end_section(self, section_name):
        """
        Declare the end of a section, i.e. further types and functions
        will belong to the main module.

        @param section_name: name of section; must match the one in
        the previous L{begin_section} call.
        """
        assert self.parent is None
        if self._current_section != section_name:
            raise ValueError("end_section called for wrong section: expected %r, got %r"
                             % (self._current_section, section_name))
        self._current_section = '__main__'

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
        wrapper.section = self.current_section
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
            try:
                func = Function(*args, **kwargs)
            except utils.SkipWrapper:
                return None
        func.stack_where_defined = traceback.extract_stack()
        self._add_function_obj(func)
        return func

    def add_custom_function_wrapper(self, *args, **kwargs):
        """
        Add a function, using custom wrapper code, to the module/namespace. See the documentation for
        L{CustomFunctionWrapper.__init__} for information on accepted parameters.
        """
        try:
            func = CustomFunctionWrapper(*args, **kwargs)
        except utils.SkipWrapper:
            return None
        func.stack_where_defined = traceback.extract_stack()
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
        class_.section = self.current_section
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
        cls.stack_where_defined = traceback.extract_stack()
        self._add_class_obj(cls)
        return cls

    def add_cpp_namespace(self, name):
        """
        Add a nested module namespace corresponding to a C++
        namespace.  If the requested namespace was already added, the
        existing module is returned instead of creating a new one.

        @param name: name of C++ namespace (just the last component,
        not full scoped name); this also becomes the name of the
        submodule.

        @return: a L{SubModule} object that maps to this namespace.
        """
        name = utils.ascii(name)
        try:
            return self.get_submodule(name)
        except ValueError:
            module = SubModule(name, parent=self, cpp_namespace=name)
            module.stack_where_defined = traceback.extract_stack()
            return module

    def _add_enum_obj(self, enum):
        """
        Add an enumeration.
        """
        assert isinstance(enum, Enum)
        self.enums.append(enum)
        enum.module = self
        enum.section = self.current_section
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
        enum.stack_where_defined = traceback.extract_stack()
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

    def do_generate(self, out):
        """(internal) Generates the module."""
        assert isinstance(out, _SinkManager)

        if self.parent is None:
            ## generate the include directives (only the root module)
            if self.parent is None:
                for include in self.includes:
                    out.get_includes_code_sink().writeln("#include %s" % include)

            if not self._forward_declarations_declared:
                self.generate_forward_declarations(out.get_includes_code_sink())
                self.after_forward_declarations.flush_to(out.get_includes_code_sink())

        ## generate the submodules
        for submodule in self.submodules:
            submodule.do_generate(out)

        m = self.declarations.declare_variable('PyObject*', 'm')
        assert m == 'm'
        self.before_init.write_code(
            "m = Py_InitModule3(\"%s\", %s_functions, %s);"
            % ('.'.join(self.get_module_path()), self.prefix,
               self.docstring and '"'+self.docstring+'"' or 'NULL'))
        self.before_init.write_error_check("m == NULL")

        main_sink = out.get_main_code_sink()

        ## generate the function wrappers
        py_method_defs = []
        if self.functions:
            main_sink.writeln('/* --- module functions --- */')
            main_sink.writeln()
            for func_name, overload in self.functions.iteritems():
                sink, header_sink = out.get_code_sink_for_wrapper(overload)
                sink.writeln()
                try:
                    utils.call_with_error_handling(overload.generate, (sink,), {}, overload)
                except utils.SkipWrapper:
                    continue
                try:
                    utils.call_with_error_handling(overload.generate_declaration, (main_sink,), {}, overload)
                except utils.SkipWrapper:
                    continue
                
                sink.writeln()
                py_method_defs.append(overload.get_py_method_def(func_name))
                del sink

        ## generate the function table
        main_sink.writeln("static PyMethodDef %s_functions[] = {"
                          % (self.prefix,))
        main_sink.indent()
        for py_method_def in py_method_defs:
            main_sink.writeln(py_method_def)
        main_sink.writeln("{NULL, NULL, 0, NULL}")
        main_sink.unindent()
        main_sink.writeln("};")

        ## generate the classes
        if self.classes:
            main_sink.writeln('/* --- classes --- */')
            main_sink.writeln()
            for class_ in self.classes:
                sink, header_sink = out.get_code_sink_for_wrapper(class_)
                sink.writeln()
                class_.generate(sink, self)
                sink.writeln()

        ## generate the enums
        if self.enums:
            main_sink.writeln('/* --- enumerations --- */')
            main_sink.writeln()
            for enum in self.enums:
                sink, header_sink = out.get_code_sink_for_wrapper(enum)
                sink.writeln()
                enum.generate(sink)
                enum.generate_declaration(header_sink, self)
                sink.writeln()

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

        ## flush the header section
        self.header.flush_to(out.get_includes_code_sink())

        ## flush the body section
        self.header.flush_to(main_sink)

        ## now generate the module init function itself
        main_sink.writeln()
        if self.parent is None:
            main_sink.writeln("PyMODINIT_FUNC")
        else:
            main_sink.writeln("static PyObject *")
        main_sink.writeln("%s(void)" % (self.init_function_name,))
        main_sink.writeln('{')
        main_sink.indent()
        self.declarations.get_code_sink().flush_to(main_sink)
        self.before_init.sink.flush_to(main_sink)
        self.after_init.write_cleanup()
        self.after_init.sink.flush_to(main_sink)
        if self.parent is not None:
            main_sink.writeln("return m;")
        main_sink.unindent()
        main_sink.writeln('}')


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

    def generate(self, out):
        """Generates the module
        @type out: file, L{FileCodeSink}, or L{MultiSectionFactory}
        """
        if isinstance(out, file):
            out = FileCodeSink(out)
        if isinstance(out, CodeSink):
            sink_manager = _MonolithicSinkManager(out)
        elif isinstance(out, MultiSectionFactory):
            sink_manager = _MultiSectionSinkManager(out)
        else:
            raise TypeError
        self.do_generate(sink_manager)
        sink_manager.close()


class SubModule(ModuleBase):
    def __init__(self, name, parent, docstring=None, cpp_namespace=None):
        """
        @param parent: parent L{module<Module>} (i.e. the one that contains this submodule)
        @param name: name of the submodule
        @param docstring: docstring to use for this module
        @param cpp_namespace: C++ namespace component associated with this module
        """
        super(SubModule, self).__init__(name, parent, docstring=docstring, cpp_namespace=cpp_namespace)

