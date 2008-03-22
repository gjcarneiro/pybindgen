"""
Wrap C++ classes and methods
"""

import warnings

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase, Parameter, ReturnValue, \
    join_ctype_and_name, CodeGenerationError, TypeConfigurationError, \
    param_type_matcher, return_type_matcher, CodegenErrorBase

from typehandlers.codesink import NullCodeSink, MemoryCodeSink

from cppmethod import CppMethod, CppConstructor, CppNoConstructor, CppFunctionAsConstructor, \
    CppOverloadedMethod, CppOverloadedConstructor, \
    CppVirtualMethodParentCaller, CppVirtualMethodProxy

from cppattribute import (CppInstanceAttributeGetter, CppInstanceAttributeSetter,
                          CppStaticAttributeGetter, CppStaticAttributeSetter,
                          PyGetSetDef, PyMetaclass)

import settings
import utils


def default_instance_creation_function(cpp_class, code_block, lvalue,
                                       parameters, construct_type_name):
    """
    Default "instance creation function"; it is called whenever a new
    C++ class instance needs to be created; this default
    implementation uses a standard C++ new allocator.

    cpp_class -- the CppClass object whose instance is to be created
    code_block -- CodeBlock object on which the instance creation code should be generated
    lvalue -- lvalue expression that should hold the result in the end
    contruct_type_name -- actual name of type to be constructed (it is
                          not always the class name, sometimes it's
                          the python helper class)
    parameters -- stringified list of parameters
    """
    assert lvalue
    assert not lvalue.startswith('None')
    if cpp_class.incomplete_type:
        raise CodeGenerationError("%s cannot be constructed (incomplete type)"
                                  % cpp_class.full_name)
    code_block.write_code(
        "%s = new %s(%s);" % (lvalue, construct_type_name, parameters))


class CppHelperClass(object):
    """
    Generates code for a C++ proxy subclass that takes care of
    forwarding virtual methods from C++ to Python.
    """

    def __init__(self, class_):
        """
        class_ -- original CppClass wrapper object
        """
        self.class_ = class_
        self.name = class_.pystruct + "__PythonHelper"
        self.virtual_parent_callers = {}
        self.virtual_proxies = []
        self.cannot_be_constructed = False
        self.custom_methods = []
        self.post_generation_code = []
        
    def add_virtual_parent_caller(self, parent_caller):
        """Add a new CppVirtualMethodParentCaller object to this helper class"""
        assert isinstance(parent_caller, CppVirtualMethodParentCaller)

        name = parent_caller.method_name
        try:
            overload = self.virtual_parent_callers[name]
        except KeyError:
            overload = CppOverloadedMethod(name)
            ## implicit conversions + virtual methods disabled
            ## temporarily until I can figure out how to fix the unit
            ## tests.
            overload.enable_implicit_conversions = False
            overload.static_decl = False
            overload.pystruct = self.class_.pystruct
            self.virtual_parent_callers[name] = overload
            assert self.class_ is not None
        parent_caller.class_ = self.class_
        parent_caller.helper_class = self
        overload.add(parent_caller)

    def add_custom_method(self, declaration, body=None):
        """
        Add a custom method to the helper class, given by a
        declaration line and a body.  The body can be None, in case
        the whole method definition is included in the declaration
        itself.
        """
        self.custom_methods.append((declaration, body))

    def add_post_generation_code(self, code):
        """
        Add custom code to be included right after the helper class is generated.
        """
        self.post_generation_code.append(code)

    def add_virtual_proxy(self, virtual_proxy):
        """Add a new CppVirtualMethodProxy object to this class"""
        assert isinstance(virtual_proxy, CppVirtualMethodProxy)
        self.virtual_proxies.append(virtual_proxy)

    def generate_forward_declarations(self, code_sink_param):
        """
        Generate the proxy class (declaration only) to a given code sink
        """
        code_sink = MemoryCodeSink()
        if self._generate_forward_declarations(code_sink):
            code_sink.flush_to(code_sink_param)
        else:
            self.cannot_be_constructed = True

    def _generate_forward_declarations(self, code_sink):
        """
        Generate the proxy class (declaration only) to a given code sink.

        Returns True if all is well, False if a pure virtual method
        was found that could not be generated.
        """
        code_sink.writeln("class %s : public %s\n{\npublic:" %
                          (self.name, self.class_.full_name))

        code_sink.indent()
        code_sink.writeln("PyObject *m_pyself;")

        ## replicate the parent constructors in the helper class
        for cons in self.class_.constructors:
            params = [join_ctype_and_name(param.ctype, param.name)
                      for param in cons.parameters]
            code_sink.writeln("%s(%s)" % (self.name, ', '.join(params)))
            code_sink.indent()
            code_sink.writeln(": %s(%s), m_pyself(NULL)\n{}" %
                              (self.class_.full_name,
                               ', '.join([param.name for param in cons.parameters])))
            code_sink.unindent()
            code_sink.writeln()

        ## add the set_pyobj method
        code_sink.writeln("""
void set_pyobj(PyObject *pyobj)
{
    Py_XDECREF(m_pyself);
    Py_INCREF(pyobj);
    m_pyself = pyobj;
}
""")

        ## write a destructor
        code_sink.writeln("~%s()\n{" % self.name)
        code_sink.indent()
        code_sink.writeln("Py_CLEAR(m_pyself);")
        code_sink.unindent()
        code_sink.writeln("}\n")
            
        ## write the parent callers (_name)
        for parent_caller in self.virtual_parent_callers.itervalues():
            parent_caller.class_ = self.class_
            parent_caller.helper_class = self
            parent_caller.reset_code_generation_state()
            ## test code generation
            try:
                try:
                    utils.call_with_error_handling(parent_caller.generate,
                                                   (NullCodeSink(),), {}, parent_caller)
                except utils.SkipWrapper:
                    continue
            finally:
                parent_caller.reset_code_generation_state()

            code_sink.writeln()
            parent_caller.generate_declaration(code_sink)

            for parent_caller_wrapper in parent_caller.wrappers:
                parent_caller_wrapper.generate_parent_caller_method(code_sink)


        ## write the virtual proxies
        for virtual_proxy in self.virtual_proxies:
            virtual_proxy.class_ = self.class_
            virtual_proxy.helper_class = self
            ## test code generation
            virtual_proxy.class_ = self.class_
            virtual_proxy.helper_class = self
            virtual_proxy.reset_code_generation_state()
            try:
                try:
                    utils.call_with_error_handling(virtual_proxy.generate,
                                                   (NullCodeSink(),), {}, virtual_proxy)
                except utils.SkipWrapper:
                    if virtual_proxy.method.is_pure_virtual:
                        return False
                    continue
            finally:
                virtual_proxy.reset_code_generation_state()
                
            code_sink.writeln()
            virtual_proxy.generate_declaration(code_sink)

        for custom_declaration, dummy in self.custom_methods:
            code_sink.writeln(custom_declaration)

        code_sink.unindent()
        code_sink.writeln("};\n")
        for code in self.post_generation_code:
            code_sink.writeln(code)
            code_sink.writeln()
        return True

    def generate(self, code_sink):
        """
        Generate the proxy class (virtual method bodies only) to a given code sink.
        returns pymethodef list of parent callers
        """
        ## write the parent callers (_name)
        method_defs = []
        for name, parent_caller in self.virtual_parent_callers.iteritems():
            parent_caller.class_ = self.class_
            parent_caller.helper_class = self
            code_sink.writeln()

            ## parent_caller.generate(code_sink)
            try:
                utils.call_with_error_handling(parent_caller.generate,
                                               (code_sink,), {}, parent_caller)
            except utils.SkipWrapper:
                continue
            method_defs.append(parent_caller.get_py_method_def(name))
                
        ## write the virtual proxies
        for virtual_proxy in self.virtual_proxies:
            virtual_proxy.class_ = self.class_
            virtual_proxy.helper_class = self
            code_sink.writeln()

            ## virtual_proxy.generate(code_sink)
            try:
                utils.call_with_error_handling(virtual_proxy.generate,
                                               (code_sink,), {}, virtual_proxy)
            except utils.SkipWrapper:
                continue

        for dummy, custom_body in self.custom_methods:
            if custom_body:
                code_sink.writeln(custom_body)
        
        return method_defs



class CppClass(object):
    """
    A CppClass object takes care of generating the code for wrapping a C++ class
    """

    TYPE_TMPL = (
        'PyTypeObject %(typestruct)s = {\n'
        '    PyObject_HEAD_INIT(NULL)\n'
        '    0,                                 /* ob_size */\n'
        '    "%(tp_name)s",                   /* tp_name */\n'
        '    %(tp_basicsize)s,                  /* tp_basicsize */\n'
        '    0,                                 /* tp_itemsize */\n'
        '    /* methods */\n'
        '    (destructor)%(tp_dealloc)s,        /* tp_dealloc */\n'
        '    (printfunc)0,                      /* tp_print */\n'
        '    (getattrfunc)%(tp_getattr)s,       /* tp_getattr */\n'
        '    (setattrfunc)%(tp_setattr)s,       /* tp_setattr */\n'
        '    (cmpfunc)%(tp_compare)s,           /* tp_compare */\n'
        '    (reprfunc)%(tp_repr)s,             /* tp_repr */\n'
        '    (PyNumberMethods*)%(tp_as_number)s,     /* tp_as_number */\n'
        '    (PySequenceMethods*)%(tp_as_sequence)s, /* tp_as_sequence */\n'
        '    (PyMappingMethods*)%(tp_as_mapping)s,   /* tp_as_mapping */\n'
        '    (hashfunc)%(tp_hash)s,             /* tp_hash */\n'
        '    (ternaryfunc)%(tp_call)s,          /* tp_call */\n'
        '    (reprfunc)%(tp_str)s,              /* tp_str */\n'
        '    (getattrofunc)%(tp_getattro)s,     /* tp_getattro */\n'
        '    (setattrofunc)%(tp_setattro)s,     /* tp_setattro */\n'
        '    (PyBufferProcs*)%(tp_as_buffer)s,  /* tp_as_buffer */\n'
        '    %(tp_flags)s,                      /* tp_flags */\n'
        '    %(tp_doc)s,                        /* Documentation string */\n'
        '    (traverseproc)%(tp_traverse)s,     /* tp_traverse */\n'
        '    (inquiry)%(tp_clear)s,             /* tp_clear */\n'
        '    (richcmpfunc)%(tp_richcompare)s,   /* tp_richcompare */\n'
        '    %(tp_weaklistoffset)s,             /* tp_weaklistoffset */\n'
        '    (getiterfunc)%(tp_iter)s,          /* tp_iter */\n'
        '    (iternextfunc)%(tp_iternext)s,     /* tp_iternext */\n'
        '    (struct PyMethodDef*)%(tp_methods)s, /* tp_methods */\n'
        '    (struct PyMemberDef*)0,              /* tp_members */\n'
        '    %(tp_getset)s,                     /* tp_getset */\n'
        '    NULL,                              /* tp_base */\n'
        '    NULL,                              /* tp_dict */\n'
        '    (descrgetfunc)%(tp_descr_get)s,    /* tp_descr_get */\n'
        '    (descrsetfunc)%(tp_descr_set)s,    /* tp_descr_set */\n'
        '    %(tp_dictoffset)s,                 /* tp_dictoffset */\n'
        '    (initproc)%(tp_init)s,             /* tp_init */\n'
        '    (allocfunc)%(tp_alloc)s,           /* tp_alloc */\n'
        '    (newfunc)%(tp_new)s,               /* tp_new */\n'
        '    (freefunc)%(tp_free)s,             /* tp_free */\n'
        '    (inquiry)%(tp_is_gc)s,             /* tp_is_gc */\n'
        '    NULL,                              /* tp_bases */\n'
        '    NULL,                              /* tp_mro */\n'
        '    NULL,                              /* tp_cache */\n'
        '    NULL,                              /* tp_subclasses */\n'
        '    NULL,                              /* tp_weaklist */\n'
        '    (destructor) NULL                  /* tp_del */\n'
        '};\n'
        )

    def __init__(self, name, parent=None, incref_method=None, decref_method=None,
                 automatic_type_narrowing=None, allow_subclassing=None,
                 is_singleton=False, outer_class=None,
                 peekref_method=None,
                 template_parameters=(), custom_template_class_name=None,
                 incomplete_type=False, free_function=None,
                 incref_function=None, decref_function=None,
                 python_name=None):
        """Constructor
        name -- class name
        parent -- optional parent class wrapper
        incref_method -- if the class supports reference counting, the
                         name of the method that increments the
                         reference count (may be inherited from parent
                         if not given)
        decref_method -- if the class supports reference counting, the
                         name of the method that decrements the
                         reference count (may be inherited from parent
                         if not given)
        automatic_type_narrowing -- if True, automatic return type
                                    narrowing will be done on objects
                                    of this class and its descendants
                                    when returned by pointer from a
                                    function or method.
        allow_subclassing -- if True, generated class wrappers will
                             allow subclassing in Python.
        is_singleton -- if True, the class is considered a singleton,
                        and so the python wrapper will never call the
                        C++ class destructor to free the value.
        peekref_method -- if the class supports reference counting, the
                          name of the method that returns the current reference count.
        free_function -- name of C function used to deallocate class instances
        incref_function -- same as incref_method, but as a function instead of method
        decref_method -- same as decref_method, but as a function instead of method
        python_name -- name of the class as it will appear from Python side
        """
        assert outer_class is None or isinstance(outer_class, CppClass)
        self.incomplete_type = incomplete_type
        self.outer_class = outer_class
        self._module = None
        self.name = name
        self.python_name = python_name
        self.mangled_name = None
        self.template_parameters = template_parameters
        self.custom_template_class_name = custom_template_class_name
        self.is_singleton = is_singleton
        self.full_name = None # full name with C++ namespaces attached and template parameters
        self.methods = {} # name => OverloadedMethod
        self.constructors = [] # (name, wrapper) pairs
        self.slots = dict()
        self.helper_class = None
        self.instance_creation_function = None
        ## set to True when we become aware generating the helper
        ## class is not going to be possible
        self.helper_class_disabled = False
        self.cannot_be_constructed = False
        self.has_trivial_constructor = False
        self.have_pure_virtual_methods = False
        ## list of CppClasses from which a value of this class can be
        ## implicitly generated; corresponds to a
        ## operator ThisClass(); in the other class.
        self.implicitly_converts_from = []

        ## list of hook functions to call just prior to helper class
        ## code generation.
        self.helper_class_hooks = []

        self._pystruct = None #"***GIVE ME A NAME***"
        self.metaclass_name = "***GIVE ME A NAME***"
        self.pytypestruct = "***GIVE ME A NAME***"

        self.instance_attributes = PyGetSetDef("%s__getsets" % self._pystruct)
        self.static_attributes = PyGetSetDef("%s__getsets" % self.metaclass_name)

        self.parent = parent
        assert parent is None or isinstance(parent, CppClass)

        assert (incref_method is None and decref_method is None) \
               or (incref_method is not None and decref_method is not None)
        if incref_method is None and parent is not None:
            self.incref_method = parent.incref_method
            self.decref_method = parent.decref_method
            self.peekref_method = parent.peekref_method
        else:
            self.incref_method = incref_method
            self.decref_method = decref_method
            self.peekref_method = peekref_method

        self.free_function = free_function

        assert (incref_function is None and decref_function is None) \
               or (incref_function is not None and decref_function is not None)
        if incref_function is None and parent is not None:
            self.incref_function = parent.incref_function
            self.decref_function = parent.decref_function
        else:
            self.incref_function = incref_function
            self.decref_function = decref_function

        self.has_reference_counting = (self.incref_function is not None
                                       or self.incref_method is not None)
            
        if automatic_type_narrowing is None:
            if parent is None:
                self.automatic_type_narrowing = settings.automatic_type_narrowing
            else:
                self.automatic_type_narrowing = parent.automatic_type_narrowing
        else:
            self.automatic_type_narrowing = automatic_type_narrowing

        if allow_subclassing is None:
            if parent is None:
                self.allow_subclassing = settings.allow_subclassing
            else:
                self.allow_subclassing = parent.allow_subclassing
        else:
            assert allow_subclassing or (self.parent is None or
                                         not self.parent.allow_subclassing), \
                "Cannot disable subclassing if the parent class allows it"
            self.allow_subclassing = allow_subclassing

        self.typeid_map_name = None

        if name != 'dummy':
            ## register type handlers

            class ThisClassParameter(CppClassParameter):
                """Register this C++ class as pass-by-value parameter"""
                CTYPES = []
                cpp_class = self
            self.ThisClassParameter = ThisClassParameter
            try:
                param_type_matcher.register(name, self.ThisClassParameter)
            except ValueError:
                pass


            class ThisClassRefParameter(CppClassRefParameter):
                """Register this C++ class as pass-by-reference parameter"""
                CTYPES = []
                cpp_class = self
            self.ThisClassRefParameter = ThisClassRefParameter
            try:
                param_type_matcher.register(name+'&', self.ThisClassRefParameter)
            except ValueError:
                pass

            class ThisClassReturn(CppClassReturnValue):
                """Register this C++ class as value return"""
                CTYPES = []
                cpp_class = self
            self.ThisClassReturn = ThisClassReturn
            self.ThisClassRefReturn = ThisClassReturn
            try:
                return_type_matcher.register(name, self.ThisClassReturn)
                return_type_matcher.register(name, self.ThisClassRefReturn)
            except ValueError:
                pass

            class ThisClassPtrParameter(CppClassPtrParameter):
                """Register this C++ class as pass-by-pointer parameter"""
                CTYPES = []
                cpp_class = self
            self.ThisClassPtrParameter = ThisClassPtrParameter
            try:
                param_type_matcher.register(name+'*', self.ThisClassPtrParameter)
            except ValueError:
                pass

            class ThisClassPtrReturn(CppClassPtrReturnValue):
                """Register this C++ class as pointer return"""
                CTYPES = []
                cpp_class = self
            self.ThisClassPtrReturn = ThisClassPtrReturn
            try:
                return_type_matcher.register(name+'*', self.ThisClassPtrReturn)
            except ValueError:
                pass

    def __repr__(self):
        return "<pybindgen.CppClass '%s'>" % self.full_name

    def write_incref(self, code_block, obj_expr):
        """
        Write code to increase the reference code of an object of this
        class (the real C++ class, not the wrapper).  Should only be
        called if the class supports reference counting, as reported
        by the attribute `has_reference_counting'.
        """
        if self.incref_method is not None:
            assert self.incref_function is None
            code_block.write_code('%s->%s();' % (obj_expr, self.incref_method))
        elif self.incref_function is not None:
            assert self.incref_method is None
            code_block.write_code('%s(%s);' % (self.incref_function, obj_expr))
        else:
            raise AssertionError

    def write_decref(self, code_block, obj_expr):
        """
        Write code to decrease the reference code of an object of this
        class (the real C++ class, not the wrapper).  Should only be
        called if the class supports reference counting, as reported
        by the attribute `has_reference_counting'.
        """
        if self.decref_method is not None:
            assert self.decref_function is None
            code_block.write_code('%s->%s();' % (obj_expr, self.decref_method))
        elif self.decref_function is not None:
            assert self.decref_method is None
            code_block.write_code('%s(%s);' % (self.decref_function, obj_expr))
        else:
            raise AssertionError

    def add_helper_class_hook(self, hook):
        """
        Add a hook function to be called just prior to a helper class
        being generated.  The hook function applies to this class and
        all subclasses.  The hook function is called like this:

           hook_function(helper_class)
        """
        if not callable(hook):
            raise TypeError("hook function must be callable")
        self.helper_class_hooks.append(hook)
        
    def _get_all_helper_class_hooks(self):
        """
        Returns a list of all helper class hook functions, including
        the ones registered with parent classes.  Parent hooks will
        appear first in the list.
        """
        cls = self
        l = []
        while cls is not None:
            l = cls.helper_class_hooks + l
            cls = cls.parent
        return l

    def set_instance_creation_function(self, instance_creation_function):
        """Set a custom function to be called to create instances of this
        class and its subclasses.

        instance_creation_function -- instance creation function; see
                                      default_instance_creation_function()
                                      for signature and example.
        """
        self.instance_creation_function = instance_creation_function

    def get_instance_creation_function(self):
        if self.instance_creation_function is None:
            if self.parent is None:
                return default_instance_creation_function
            else:
                return self.parent.get_instance_creation_function()
        else:
            return self.instance_creation_function

    def write_create_instance(self, code_block, lvalue, parameters, construct_type_name=None):
        instance_creation_func = self.get_instance_creation_function()
        if construct_type_name is None:
            construct_type_name = self.get_construct_name()
        instance_creation_func(self, code_block, lvalue, parameters, construct_type_name)

    def get_pystruct(self):
        if self._pystruct is None:
            raise ValueError
        return self._pystruct
    pystruct = property(get_pystruct)

    def get_construct_name(self):
        """Get a name usable for new %s construction, or raise
        CodeGenerationError if none found"""
        if self.cannot_be_constructed:
            raise CodeGenerationError("%s cannot be constructed" % self.full_name)
        have_pure_virtual_methods = False
        cls = self
        while cls is not None:
            have_pure_virtual_methods = (have_pure_virtual_methods or cls.have_pure_virtual_methods)
            cls = cls.parent
        if have_pure_virtual_methods:
            raise CodeGenerationError("%s cannot be constructed" % self.full_name)
        else:
            return self.full_name
        

    def implicitly_converts_to(self, other):
        """
        Declares that values of this class can be implicitly converted
        to another class; corresponds to a operator AnotherClass();
        special method.
        """
        assert isinstance(other, CppClass)
        other.implicitly_converts_from.append(self)

    def get_all_implicit_conversions(self):
        """
        Gets a new list of all other classes whose value can be implicitly
        converted to a value of this class.

        >>> Foo = CppClass("Foo")
        >>> Bar = CppClass("Bar")
        >>> Zbr = CppClass("Zbr")
        >>> Bar.implicitly_converts_to(Foo)
        >>> Zbr.implicitly_converts_to(Bar)
        >>> l = Foo.get_all_implicit_conversions()
        >>> l.sort(lambda cls1, cls2: cmp(cls1.name, cls2.name))
        >>> [cls.name for cls in l]
        ['Bar']
        """
        return list(self.implicitly_converts_from)
#         classes = []
#         to_visit = list(self.implicitly_converts_from)
#         while to_visit:
#             source = to_visit.pop(0)
#             if source in classes or source is self:
#                 continue
#             classes.append(source)
#             to_visit.extend(source.implicitly_converts_from)
#         return classes

    def _update_names(self):
        
        prefix = settings.name_prefix.capitalize()

        if self.outer_class is None:
            if self._module.cpp_namespace_prefix:
                if self._module.cpp_namespace_prefix == '::':
                    self.full_name = '::' + self.name
                else:
                    self.full_name = self._module.cpp_namespace_prefix + '::' + self.name
            else:
                self.full_name = self.name
        else:
            self.full_name = '::'.join([self.outer_class.full_name, self.name])

        def make_upper(s):
            if s and s[0].islower():
                return s[0].upper()+s[1:]
            else:
                return s

        def mangle(s):
            "make a name Like<This,and,That> look Like__lt__This_and_That__gt__"
            s = s.replace('<', '__lt__').replace('>', '__gt__').replace(',', '_')
            s = s.replace(' ', '_').replace('&', '__amp__').replace('*', '__star__')
            return s
        
        def flatten(name):
            "make a name like::This look LikeThis"
            return ''.join([make_upper(mangle(s)) for s in name.split('::')])

        flat_name = flatten(self.full_name)
        self.mangled_name = flatten(self.name)

        if self.template_parameters:
            self.full_name += "< %s >" % (', '.join(self.template_parameters))
            flat_name += '__' + '_'.join([flatten(s) for s in self.template_parameters])
            self.mangled_name += '__' + '_'.join([flatten(s) for s in self.template_parameters])

        self._pystruct = "Py%s%s" % (prefix, flat_name)
        self.metaclass_name = "%sMeta" % flat_name
        self.pytypestruct = "Py%s%s_Type" % (prefix, flat_name)

        self.instance_attributes.cname = "%s__getsets" % self._pystruct
        self.static_attributes.cname = "%s__getsets" % self.metaclass_name

        ## re-register the class type handlers, now with class full name
        self.register_alias(self.full_name)

        if self.get_type_narrowing_root() is self:
            self.typeid_map_name = "%s__typeid_map" % self.pystruct
        else:
            self.typeid_map_name = None

    def register_alias(self, alias):
        """Re-register the class with another base name, in addition to any
        registrations that might have already been done."""
        self.ThisClassParameter.CTYPES.append(alias)
        try:
            param_type_matcher.register(alias, self.ThisClassParameter)
        except ValueError: pass
        
        self.ThisClassRefParameter.CTYPES.append(alias+'&')
        try:
            param_type_matcher.register(alias+'&', self.ThisClassRefParameter)
        except ValueError: pass
        
        self.ThisClassReturn.CTYPES.append(alias)
        try:
            return_type_matcher.register(alias, self.ThisClassReturn)
        except ValueError: pass
        
        self.ThisClassPtrParameter.CTYPES.append(alias+'*')
        try:
            param_type_matcher.register(alias+'*', self.ThisClassPtrParameter)
        except ValueError: pass
        
        self.ThisClassPtrReturn.CTYPES.append(alias+'*')
        try:
            return_type_matcher.register(alias+'*', self.ThisClassPtrReturn)
        except ValueError: pass
        
    def get_module(self):
        """Get the Module object this class belongs to"""
        return self._module

    def set_module(self, module):
        """Set the Module object this class belongs to"""
        self._module = module
        self._update_names()

    module = property(get_module, set_module)


    def inherit_default_constructors(self):
        """inherit the default constructors from the parentclass according to C++
        language rules"""
        if self.parent is None:
            return
        for cons in self.parent.constructors:
            if len(cons.parameters) == 0:
                self.add_constructor(CppConstructor([]))
            elif (len(cons.parameters) == 1
                  and isinstance(cons.parameters[0], self.parent.ThisClassRefParameter)):
                self.add_constructor(CppConstructor([self.ThisClassRefParameter()]))

    def get_helper_class(self):
        """gets the "helper class" for this class wrapper, creating it if necessary"""
        if self.helper_class_disabled:
            return None
        if self.helper_class is None:
            if not self.is_singleton:
                self.helper_class = CppHelperClass(self)
        return self.helper_class
    
    def get_type_narrowing_root(self):
        """Find the root CppClass along the subtree of all parent classes that
        have automatic_type_narrowing=True Note: multiple inheritance
        not implemented"""
        if not self.automatic_type_narrowing:
            return None
        root = self
        while (root.parent is not None
               and root.parent.automatic_type_narrowing):
            root = root.parent
        return root

    def _register_typeid(self, module):
        """register this class with the typeid map root class"""
        root = self.get_type_narrowing_root()
        module.after_init.write_code("%s.register_wrapper(typeid(%s), &%s);"
                                     % (root.typeid_map_name, self.full_name, self.pytypestruct))

    def _generate_typeid_map(self, code_sink, module):
        """generate the typeid map and fill it with values"""
        try:
            module.declare_one_time_definition("TypeIDMap")
        except KeyError:
            pass
        else:
            code_sink.writeln('''

#include <map>
#include <typeinfo>
#if defined(__GNUC__) && __GNUC__ >= 3
# include <cxxabi.h>
#endif

namespace pybindgen {

class TypeMap
{
   std::map<const char *, PyTypeObject *> m_map;

public:

   TypeMap() {}

   void register_wrapper(const std::type_info &cpp_type_info, PyTypeObject *python_wrapper)
   {
       m_map[cpp_type_info.name()] = python_wrapper;
   }

   PyTypeObject * lookup_wrapper(const std::type_info &cpp_type_info, PyTypeObject *fallback_wrapper)
   {
       PyTypeObject *python_wrapper = m_map[cpp_type_info.name()];
       if (python_wrapper)
           return python_wrapper;
       else {
#if defined(__GNUC__) && __GNUC__ >= 3

           // Get closest (in the single inheritance tree provided by cxxabi.h)
           // registered python wrapper.
           const abi::__si_class_type_info *_typeinfo =
               dynamic_cast<const abi::__si_class_type_info*> (&cpp_type_info);
           while (_typeinfo && (python_wrapper = m_map[_typeinfo->name()]) == 0)
               _typeinfo = dynamic_cast<const abi::__si_class_type_info*> (_typeinfo->__base_type);

           return python_wrapper? python_wrapper : fallback_wrapper;

#else // non gcc 3+ compilers can only match against explicitly registered classes, not hidden subclasses
           return fallback_wrapper;
#endif
       }
   }
};

}
''')
        code_sink.writeln("\npybindgen::TypeMap %s;\n" % self.typeid_map_name)

    def add_method(self, method, name=None):
        """
        Add a method to the class.

        method -- a CppMethod instance that can generate the method wrapper
        name -- optional name of the class method as it will appear
                from Python side
        """
        assert name is None or isinstance(name, str)
        if isinstance(method, CppMethod):
            if name is None:
                name = method.mangled_name
        elif isinstance(method, function.Function):
            assert name is not None
            assert isinstance(method.parameters[0], CppClassParameterBase)
            assert method.parameters[0].cpp_class is self, \
                "expected first parameter to be of class %s, but it is of class %s" % \
                (self.full_name, method.parameters[0].cpp_class.full_name)
            method.parameters[0].take_value_from_python_self = True
            method.module = self.module
            method.is_virtual = False
            method.is_pure_virtual = False
            method.self_parameter_pystruct = self.pystruct
            method.visibility = 'public'
            method.force_parse = method.PARSE_TUPLE_AND_KEYWORDS
        else:
            raise TypeError
        
        if method.visibility == 'public':
            try:
                overload = self.methods[name]
            except KeyError:
                overload = CppOverloadedMethod(name)
                overload.pystruct = self.pystruct
                self.methods[name] = overload

            method.class_ = self
            overload.add(method)
        if method.is_pure_virtual:
            self.have_pure_virtual_methods = True
        if method.is_virtual:
            if not self.allow_subclassing:
                raise ValueError("Cannot add virtual methods if subclassing "
                                 "support was not enabled for this class")
            helper_class = self.get_helper_class()
            if helper_class is not None:
                if not method.is_pure_virtual:
                    if method.visibility in ['public', 'protected']:
                        parent_caller = CppVirtualMethodParentCaller(method)
                        parent_caller.main_wrapper = method
                        helper_class.add_virtual_parent_caller(parent_caller)
                        
                proxy = CppVirtualMethodProxy(method)
                proxy.main_wrapper = method
                helper_class.add_virtual_proxy(proxy)
        if self.have_pure_virtual_methods and self.helper_class is None:
            self.cannot_be_constructed = True

    def set_helper_class_disabled(self, flag=True):
        self.helper_class_disabled = flag
        if flag:
            self.helper_class = None

    def set_cannot_be_constructed(self, flag=True):
        self.cannot_be_constructed = flag

    def add_constructor(self, wrapper):
        """
        Add a constructor to the class.

        wrapper -- a CppConstructor instance
        """
        if isinstance(wrapper, function.Function):
            wrapper = CppFunctionAsConstructor(wrapper.parameters, wrapper.function_name)
            wrapper.module = self.module
        else:
            assert isinstance(wrapper, CppConstructor)
        wrapper.set_class(self)
        self.constructors.append(wrapper)
        if not wrapper.parameters:
            self.has_trivial_constructor = True

    def add_static_attribute(self, value_type, name, is_const=False):
        """
        Caveat: static attributes cannot be changed from Python; not implemented.
        value_type -- a ReturnValue object
        name -- attribute name (i.e. the name of the class member variable)
        is_const -- True if the attribute is const, i.e. cannot be modified
        """
        assert isinstance(value_type, ReturnValue)
        getter = CppStaticAttributeGetter(value_type, self, name)
        if is_const:
            setter = None
        else:
            setter = CppStaticAttributeSetter(value_type, self, name)
        self.static_attributes.add_attribute(name, getter, setter)

    def add_instance_attribute(self, value_type, name, is_const=False,
                               getter=None, setter=None):
        """
        value_type -- a ReturnValue object
        name -- attribute name (i.e. the name of the class member variable)
        is_const -- True if the attribute is const, i.e. cannot be modified
        getter -- None, or name of a method of this class used to get the value
        setter -- None, or name of a method of this class used to set the value
        """
        assert isinstance(value_type, ReturnValue)
        getter_wrapper = CppInstanceAttributeGetter(value_type, self, name, getter=getter)
        if is_const:
            setter_wrapper = None
            assert setter is None
        else:
            setter_wrapper = CppInstanceAttributeSetter(value_type, self, name, setter=setter)
        self.instance_attributes.add_attribute(name, getter_wrapper, setter_wrapper)

    def generate_forward_declarations(self, code_sink, module):
        """
        Generates forward declarations for the instance and type
        structures.
        """

        if self.allow_subclassing:
            code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *obj;
    PyObject *inst_dict;
} %s;
    ''' % (self.full_name, self.pystruct))

        else:

            code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *obj;
} %s;
    ''' % (self.full_name, self.pystruct))

        code_sink.writeln()
        code_sink.writeln('extern PyTypeObject %s;' % (self.pytypestruct,))
        code_sink.writeln()

        if self.automatic_type_narrowing:
            self._register_typeid(module)

        if self.helper_class is not None:
            for hook in self._get_all_helper_class_hooks():
                hook(self.helper_class)
            self.helper_class.generate_forward_declarations(code_sink)
            if self.helper_class.cannot_be_constructed:
                self.helper_class = None
                self.helper_class_disabled = True
        if self.have_pure_virtual_methods and self.helper_class is None:
            self.cannot_be_constructed = True

        if self.typeid_map_name is not None:
            self._generate_typeid_map(code_sink, module)


    def generate(self, code_sink, module, docstring=None):
        """Generates the class to a code sink"""

        if self.helper_class is not None:
            parent_caller_methods = self.helper_class.generate(code_sink)       
        else:
            parent_caller_methods = []

        ## generate getsets
        instance_getsets = self.instance_attributes.generate(code_sink)
        self.slots.setdefault("tp_getset", instance_getsets)
        static_getsets = self.static_attributes.generate(code_sink)

        ## --- register the class type in the module ---
        module.after_init.write_code("/* Register the '%s' class */" % self.full_name)

        ## generate a metaclass if needed
        if static_getsets == '0':
            metaclass = None
        else:
            if self.parent is None:
                parent_typestruct = 'PyBaseObject_Type'
            else:
                parent_typestruct = self.parent.pytypestruct
            metaclass = PyMetaclass(self.metaclass_name,
                                    "%s.ob_type" % parent_typestruct,
                                    self.static_attributes)
            metaclass.generate(code_sink, module)

        if self.parent is not None:
            assert isinstance(self.parent, CppClass)
            module.after_init.write_code('%s.tp_base = &%s;' %
                                         (self.pytypestruct, self.parent.pytypestruct))

        if metaclass is not None:
            module.after_init.write_code('%s.ob_type = &%s;' %
                                         (self.pytypestruct, metaclass.pytypestruct))

        module.after_init.write_error_check('PyType_Ready(&%s)'
                                          % (self.pytypestruct,))

        if self.template_parameters:
            if self.custom_template_class_name is None:
                class_python_name = self.mangled_name
            else:
                class_python_name = self.custom_template_class_name
        else:
            if self.python_name is None:
                class_python_name = self.name
            else:
                class_python_name = self.python_name

        if self.outer_class is None:
            module.after_init.write_code(
                'PyModule_AddObject(m, \"%s\", (PyObject *) &%s);' % (
                class_python_name, self.pytypestruct))
        else:
            module.after_init.write_code(
                'PyDict_SetItemString((PyObject*) %s.tp_dict, \"%s\", (PyObject *) &%s);' % (
                self.outer_class.pytypestruct, class_python_name, self.pytypestruct))

        have_constructor = self._generate_constructor(code_sink)

        self._generate_methods(code_sink, parent_caller_methods)

        if self.allow_subclassing:
            self._generate_gc_methods(code_sink)

        self._generate_destructor(code_sink, have_constructor)
        self._generate_type_structure(code_sink, docstring)
        
    def _generate_type_structure(self, code_sink, docstring):
        """generate the type structure"""
        self.slots.setdefault("tp_basicsize",
                              "sizeof(%s)" % (self.pystruct,))
        for slot in ["tp_getattr", "tp_setattr", "tp_compare", "tp_repr",
                     "tp_as_number", "tp_as_sequence", "tp_as_mapping",
                     "tp_hash", "tp_call", "tp_str", "tp_getattro", "tp_setattro",
                     "tp_as_buffer", "tp_traverse", "tp_clear", "tp_richcompare",
                     "tp_iter", "tp_iternext", "tp_descr_get",
                     "tp_descr_set", "tp_is_gc"]:
            self.slots.setdefault(slot, "NULL")

        self.slots.setdefault("tp_alloc", "PyType_GenericAlloc")
        self.slots.setdefault("tp_new", "PyType_GenericNew")
        #self.slots.setdefault("tp_free", "_PyObject_Del")
        self.slots.setdefault("tp_free", "0")
        self.slots.setdefault("tp_weaklistoffset", "0")
        if self.allow_subclassing:
            self.slots.setdefault("tp_flags", ("Py_TPFLAGS_DEFAULT|"
                                               "Py_TPFLAGS_HAVE_GC|"
                                               "Py_TPFLAGS_BASETYPE"))
            self.slots.setdefault("tp_dictoffset",
                                  "offsetof(%s, inst_dict)" % self.pystruct)
        else:
            self.slots.setdefault("tp_flags", "Py_TPFLAGS_DEFAULT")
            self.slots.setdefault("tp_dictoffset", "0")
        self.slots.setdefault("tp_doc", (docstring is None and 'NULL'
                                         or "\"%s\"" % (docstring,)))
        dict_ = self.slots
        dict_.setdefault("typestruct", self.pytypestruct)

        if self.outer_class is None:
            mod_path = self._module.get_module_path()
            mod_path.append(self.mangled_name)
            dict_.setdefault("tp_name", '.'.join(mod_path))
        else:
            dict_.setdefault("tp_name", '%s.%s' % (self.outer_class.slots['tp_name'], self.name))
            
        code_sink.writeln(self.TYPE_TMPL % dict_)


    def _generate_constructor(self, code_sink):
        """generate the constructor, if any"""
        have_constructor = True
        if self.constructors and ((not self.cannot_be_constructed) or self.helper_class is not None
                                  and not self.helper_class.cannot_be_constructed):
            code_sink.writeln()
            overload = CppOverloadedConstructor(None)
            self.constructors_overload = overload
            overload.pystruct = self.pystruct
            for constructor in self.constructors:
                try:
                    overload.add(constructor)
                except CodegenErrorBase:
                    continue
            if overload.wrappers:
                try:
                    overload.generate(code_sink)
                except utils.SkipWrapper:
                    constructor = None
                    have_constructor = False
                else:
                    constructor = overload.wrapper_function_name
                    code_sink.writeln()
            else:
                constructor = None
                have_constructor = False
        else:
            ## In C++, and unlike Python, constructors with
            ## parameters are not automatically inheritted by
            ## subclasses.  We must generate a 'no constructor'
            ## tp_init to prevent this type from inheriting a
            ## tp_init that will allocate an instance of the
            ## parent class instead of this class.
            code_sink.writeln()
            constructor = CppNoConstructor().generate(code_sink, self)
            have_constructor = False
            code_sink.writeln()

        self.slots.setdefault("tp_init", (constructor is None and "NULL"
                                          or constructor))
        return have_constructor

    def _generate_methods(self, code_sink, parent_caller_methods):
        """generate the method wrappers"""
        method_defs = []
        for meth_name, overload in self.methods.iteritems():
            code_sink.writeln()
            #overload.generate(code_sink)
            try:
                utils.call_with_error_handling(overload.generate, (code_sink,), {}, overload)
            except utils.SkipWrapper:
                continue
            method_defs.append(overload.get_py_method_def(meth_name))
            code_sink.writeln()
        method_defs.extend(parent_caller_methods)
        ## generate the method table
        code_sink.writeln("static PyMethodDef %s_methods[] = {" % (self.pystruct,))
        code_sink.indent()
        for methdef in method_defs:
            code_sink.writeln(methdef)
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")
        self.slots.setdefault("tp_methods", "%s_methods" % (self.pystruct,))

    def _get_delete_code(self):
        if self.is_singleton:
            delete_code = ''
        else:
            if self.decref_method is not None:
                delete_code = ("if (self->obj) {\n"
                               "    %s *tmp = self->obj;\n"
                               "    self->obj = NULL;\n"
                               "    tmp->%s();\n"
                               "}"
                               % (self.full_name, self.decref_method,))
            elif self.decref_function is not None:
                delete_code = ("if (self->obj) {\n"
                               "    %s *tmp = self->obj;\n"
                               "    self->obj = NULL;\n"
                               "    %s(tmp);\n"
                               "}"
                               % (self.full_name, self.decref_function,))
            elif self.free_function is not None:
                delete_code = ("if (self->obj) {\n"
                               "    %s *tmp = self->obj;\n"
                               "    self->obj = NULL;\n"
                               "    %s(tmp);\n"
                               "}"
                               % (self.full_name, self.free_function,))
            else:
                if self.incomplete_type:
                    raise CodeGenerationError("Cannot finish generating class %s: "
                                              "type is incomplete, but no free/unref_function defined"
                                              % self.full_name)
                delete_code = ("    %s *tmp = self->obj;\n"
                               "    self->obj = NULL;\n"
                               "    delete tmp;"
                               % (self.full_name,))
        return delete_code

    def _generate_gc_methods(self, code_sink):
        """Generate tp_clear and tp_traverse"""

        ## --- tp_clear ---
        tp_clear_function_name = "%s__tp_clear" % (self.pystruct,)
        self.slots.setdefault("tp_clear", tp_clear_function_name )
        delete_code = self._get_delete_code()
        code_sink.writeln(r'''
static void
%s(%s *self)
{
    Py_CLEAR(self->inst_dict);
    %s
}
''' % (tp_clear_function_name, self.pystruct, delete_code))

        ## --- tp_traverse ---
        tp_traverse_function_name = "%s__tp_traverse" % (self.pystruct,)
        self.slots.setdefault("tp_traverse", tp_traverse_function_name )

        if self.helper_class is None:
            visit_self = ''
        else:
            if self.peekref_method is None:
                peekref_code = ''
            else:
                peekref_code = " && self->obj->%s() == 1" % self.peekref_method
            visit_self = '''
    if (self->obj && typeid(*self->obj) == typeid(%s)%s)
        Py_VISIT((PyObject *) self);
''' % (self.helper_class.name, peekref_code)

        code_sink.writeln(r'''
static int
%s(%s *self, visitproc visit, void *arg)
{
    Py_VISIT(self->inst_dict);
    %s
    return 0;
}
''' % (tp_traverse_function_name, self.pystruct, visit_self))


    def _generate_destructor(self, code_sink, have_constructor):
        """Generate a tp_dealloc function and register it in the type"""

        ## don't generate destructor if overridden by user
        if "tp_dealloc" in self.slots:
            return

        tp_dealloc_function_name = "_wrap_%s__tp_dealloc" % (self.pystruct,)

        if self.allow_subclassing:
            clear_code = "%s(self);" % self.slots["tp_clear"]
            delete_code = ""
        else:
            clear_code = ""
            delete_code = self._get_delete_code()

        if have_constructor:
            code_sink.writeln(r'''
static void
%s(%s *self)
{
    %s
    %s
    self->ob_type->tp_free((PyObject*)self);
}
''' % (tp_dealloc_function_name, self.pystruct,
       delete_code, clear_code))

        else: # don't have constructor

            code_sink.writeln('''
static void
%s(%s *self)
{
    %s
    %s
    self->ob_type->tp_free((PyObject*)self);
}
''' % (tp_dealloc_function_name, self.pystruct,
       clear_code, delete_code))
        code_sink.writeln()
        self.slots.setdefault("tp_dealloc", tp_dealloc_function_name )


###
### ------------ C++ class parameter type handlers ------------
###
class CppClassParameterBase(Parameter):
    "Base class for all C++ Class parameter handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassParameterBase, self).__init__(
            ctype, name, direction, is_const)

        ## name of the PyFoo * variable used in parameter parsing
        self.py_name = None

        ## it True, this parameter is 'fake', and instead of being
        ## passed a parameter from python it is assumed to be the
        ## 'self' parameter of a method wrapper
        self.take_value_from_python_self = False


class CppClassReturnValueBase(ReturnValue):
    "Class return handlers -- base class"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance

    def __init__(self, ctype):
        super(CppClassReturnValueBase, self).__init__(ctype)
        ## name of the PyFoo * variable used in return value building
        self.py_name = None


class CppClassParameter(CppClassParameterBase):
    "Class handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, CppClass)

        if self.take_value_from_python_self:
            self.py_name = 'self'
            wrapper.call_params.append(
                '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
        else:
            implicit_conversion_sources = self.cpp_class.get_all_implicit_conversions()
            if not implicit_conversion_sources:
                self.py_name = wrapper.declarations.declare_variable(
                    self.cpp_class.pystruct+'*', self.name)
                wrapper.parse_params.add_parameter(
                    'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
                wrapper.call_params.append(
                    '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
            else:
                self.py_name = wrapper.declarations.declare_variable(
                    'PyObject*', self.name)
                tmp_value_variable = wrapper.declarations.declare_variable(
                    self.cpp_class.full_name, self.name)
                wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name)

                wrapper.before_call.write_code("if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                               "    %s = *((%s *) %s)->obj;" %
                                               (self.py_name, self.cpp_class.pytypestruct,
                                                tmp_value_variable,
                                                self.cpp_class.pystruct, self.py_name))
                for conversion_source in implicit_conversion_sources:
                    wrapper.before_call.write_code("} else if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                   "    %s = *((%s *) %s)->obj;" %
                                                   (self.py_name, conversion_source.pytypestruct,
                                                    tmp_value_variable,
                                                    conversion_source.pystruct, self.py_name))
                wrapper.before_call.write_code("} else {\n")
                wrapper.before_call.indent()
                possible_type_names = ", ".join([cls.name for cls in [self.cpp_class] + implicit_conversion_sources])
                wrapper.before_call.write_code("PyErr_Format(PyExc_TypeError, \"parameter must an instance of one of the types (%s), not %%s\", %s->ob_type->tp_name);" % (possible_type_names, self.py_name))
                wrapper.before_call.write_error_return()
                wrapper.before_call.unindent()
                wrapper.before_call.write_code("}")

                wrapper.call_params.append(tmp_value_variable)

    def convert_c_to_python(self, wrapper):
        '''Write some code before calling the Python method.'''
        assert isinstance(wrapper, ReverseWrapperBase)

        self.py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        if self.cpp_class.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'
        wrapper.before_call.write_code(
            "%s = %s(%s, %s);" %
            (self.py_name, new_func, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        if self.cpp_class.allow_subclassing:
            wrapper.before_call.write_code(
                "%s->inst_dict = NULL;" % (self.py_name,))

        self.cpp_class.write_create_instance(wrapper.before_call,
                                             "%s->obj" % self.py_name,
                                             self.value)

        wrapper.build_params.add_parameter("N", [self.py_name])


class CppClassRefParameter(CppClassParameterBase):
    "Class& handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_INOUT]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassRefParameter, self).__init__(
            ctype, name, direction, is_const)
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, CppClass)


        if self.direction == Parameter.DIRECTION_IN:
            if self.take_value_from_python_self:
                self.py_name = 'self'
                wrapper.call_params.append(
                    '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
            else:
                implicit_conversion_sources = self.cpp_class.get_all_implicit_conversions()
                if not (implicit_conversion_sources and self.is_const):
                    self.py_name = wrapper.declarations.declare_variable(
                        self.cpp_class.pystruct+'*', self.name)
                    wrapper.parse_params.add_parameter(
                        'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
                    wrapper.call_params.append(
                        '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
                else:
                    self.py_name = wrapper.declarations.declare_variable(
                        'PyObject*', self.name)
                    tmp_value_variable = wrapper.declarations.declare_variable(
                        self.cpp_class.full_name, self.name)
                    wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name)

                    wrapper.before_call.write_code("if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                   "    %s = *((%s *) %s)->obj;" %
                                                   (self.py_name, self.cpp_class.pytypestruct,
                                                    tmp_value_variable,
                                                    self.cpp_class.pystruct, self.py_name))
                    for conversion_source in implicit_conversion_sources:
                        wrapper.before_call.write_code("} else if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                       "    %s = *((%s *) %s)->obj;" %
                                                       (self.py_name, conversion_source.pytypestruct,
                                                        tmp_value_variable,
                                                        conversion_source.pystruct, self.py_name))
                    wrapper.before_call.write_code("} else {\n")
                    wrapper.before_call.indent()
                    possible_type_names = ", ".join([cls.name for cls in [self.cpp_class] + implicit_conversion_sources])
                    wrapper.before_call.write_code("PyErr_Format(PyExc_TypeError, \"parameter must an instance of one of the types (%s), not %%s\", %s->ob_type->tp_name);" % (possible_type_names, self.py_name))
                    wrapper.before_call.write_error_return()
                    wrapper.before_call.unindent()
                    wrapper.before_call.write_code("}")

                    wrapper.call_params.append(tmp_value_variable)

        elif self.direction == Parameter.DIRECTION_OUT:
            assert not self.take_value_from_python_self

            self.py_name = wrapper.declarations.declare_variable(
                self.cpp_class.pystruct+'*', self.name)

            if self.cpp_class.allow_subclassing:
                new_func = 'PyObject_GC_New'
            else:
                new_func = 'PyObject_New'
            wrapper.before_call.write_code(
                "%s = %s(%s, %s);" %
                (self.py_name, new_func, self.cpp_class.pystruct,
                 '&'+self.cpp_class.pytypestruct))
            if self.cpp_class.allow_subclassing:
                wrapper.after_call.write_code(
                    "%s->inst_dict = NULL;" % (self.py_name,))

            self.cpp_class.write_create_instance(wrapper.before_call,
                                                 "%s->obj" % self.py_name,
                                                 '')
            wrapper.call_params.append('*%s->obj' % (self.py_name,))
            wrapper.build_params.add_parameter("N", [self.py_name])

        ## well, personally I think inout here doesn't make much sense
        ## (it's just plain confusing), but might as well support it..

        ## C++ class reference inout parameters allow "inplace"
        ## modifications, i.e. the object is not explicitly returned
        ## but is instead modified by the callee.
        elif self.direction == Parameter.DIRECTION_INOUT:
            assert not self.take_value_from_python_self

            self.py_name = wrapper.declarations.declare_variable(
                self.cpp_class.pystruct+'*', self.name)

            wrapper.parse_params.add_parameter(
                'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
            wrapper.call_params.append(
                '*%s->obj' % (self.py_name))

    def convert_c_to_python(self, wrapper):
        '''Write some code before calling the Python method.'''
        assert isinstance(wrapper, ReverseWrapperBase)

        self.py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        if self.cpp_class.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'
        wrapper.before_call.write_code(
            "%s = %s(%s, %s);" %
            (self.py_name, new_func, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        if self.cpp_class.allow_subclassing:
            wrapper.before_call.write_code(
                "%s->inst_dict = NULL;" % (self.py_name,))

        if self.direction == Parameter.DIRECTION_IN:
            self.cpp_class.write_create_instance(wrapper.before_call,
                                                 "%s->obj" % self.py_name,
                                                 self.value)
            wrapper.build_params.add_parameter("N", [self.py_name])
        else:
            ## out/inout case:
            ## the callee receives a "temporary wrapper", which loses
            ## the ->obj pointer after the python call; this is so
            ## that the python code directly manipulates the object
            ## received as parameter, instead of a copy.
            if self.is_const:
                value = "const_cast< %s* >(&(%s))" % (self.cpp_class.full_name, self.value)
            else:
                value = "&(%s)" % self.value
            wrapper.before_call.write_code(
                "%s->obj = %s;" % (self.py_name, value))
            wrapper.build_params.add_parameter("O", [self.py_name])
            wrapper.before_call.add_cleanup_code("Py_DECREF(%s);" % self.py_name)

            ## if after the call we notice the callee kept a reference
            ## to the pyobject, we then swap pywrapper->obj for a copy
            ## of the original object.  Else the ->obj pointer is
            ## simply erased (we never owned this object in the first
            ## place).
            wrapper.after_call.write_code(
                "if (%s->ob_refcnt == 1)\n"
                "    %s->obj = NULL;\n"
                "else{\n" % (self.py_name, self.py_name))
            wrapper.after_call.indent()
            self.cpp_class.write_create_instance(wrapper.after_call,
                                                 "%s->obj" % self.py_name,
                                                 self.value)
            wrapper.after_call.unindent()
            wrapper.after_call.write_code('}')


class CppClassReturnValue(CppClassReturnValueBase):
    "Class return handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    REQUIRES_ASSIGNMENT_CONSTRUCTOR = True

    def __init__(self, ctype, is_const=False):
        """override to fix the ctype parameter with namespace information"""
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassReturnValue, self).__init__(ctype)
        self.is_const = is_const

    def get_c_error_return(self): # only used in reverse wrappers
        """See ReturnValue.get_c_error_return"""
        return "return %s();" % (self.cpp_class.full_name,)

    def convert_c_to_python(self, wrapper):
        """see ReturnValue.convert_c_to_python"""
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        self.py_name = py_name
        if self.cpp_class.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'
        wrapper.after_call.write_code(
            "%s = %s(%s, %s);" %
            (py_name, new_func, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        if self.cpp_class.allow_subclassing:
            wrapper.after_call.write_code(
                "%s->inst_dict = NULL;" % (py_name,))

        self.cpp_class.write_create_instance(wrapper.after_call,
                                             "%s->obj" % py_name,
                                             self.value)

        wrapper.build_params.add_parameter("N", [py_name], prepend=True)

    def convert_python_to_c(self, wrapper):
        """see ReturnValue.convert_python_to_c"""
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', "tmp_%s" % self.cpp_class.name)
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name])
        if self.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
            wrapper.after_call.write_code('%s %s = *%s->obj;' %
                                          (self.cpp_class.full_name, self.value, name))
        else:
            wrapper.after_call.write_code('%s = *%s->obj;' % (self.value, name))
    

class CppClassPtrParameter(CppClassParameterBase):
    "Class* handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    SUPPORTS_TRANSFORMATIONS = True

    def __init__(self, ctype, name, transfer_ownership=None, custodian=None, is_const=False):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name

        transfer_ownership -- this parameter transfer the ownership of
                              the pointed-to object to the called
                              function; should be omitted if custodian
                              is given.
        custodian -- the object (custodian) that is responsible for
                     managing the life cycle of the parameter.
                     Possible values are: None: no object is
                     custodian; the integer -1: the return value; the
                     integer 0: the instance of the method in which
                     the ReturnValue is being used will become the
                     custodian; integer > 0: parameter number,
                     starting at 1, whose object will be used as
                     custodian.  Note: only C++ class parameters can
                     be used as custodians, not parameters of builtin
                     Python types.
        is_const -- if true, the parameter has a const attached to the leftmost
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassPtrParameter, self).__init__(
            ctype, name, direction=Parameter.DIRECTION_IN, is_const=is_const)

        if custodian is None:
            if transfer_ownership is None:
                raise TypeConfigurationError("transfer_ownership parameter missing")
            self.transfer_ownership = transfer_ownership
        else:
            if transfer_ownership is not None:
                raise TypeConfigurationError("the transfer_ownership parameter should "
                                             "not be given when there is a custodian")
            self.transfer_ownership = False
        self.custodian = custodian

    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, CppClass)

        if self.take_value_from_python_self:
            self.py_name = 'self'
        else:
            self.py_name = wrapper.declarations.declare_variable(
                self.cpp_class.pystruct+'*', self.name)
            wrapper.parse_params.add_parameter(
                'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)

        value = self.transformation.transform(
            self, wrapper.declarations, wrapper.before_call, '%s->obj' % self.py_name)
        wrapper.call_params.append(value)
        
        if self.transfer_ownership:
            if not self.cpp_class.has_reference_counting:
                wrapper.after_call.write_code('%s->obj = NULL;' % (self.py_name,))
            else:
                self.cpp_class.write_incref(wrapper.before_call, "%s->obj" % self.py_name)


    def convert_c_to_python(self, wrapper):
        """foo"""

        ## Value transformations
        value = self.transformation.untransform(
            self, wrapper.declarations, wrapper.after_call, self.value)

        ## declare wrapper variable
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        self.py_name = py_name

        def write_create_new_wrapper():
            """Code path that creates a new wrapper for the parameter"""

            ## Find out what Python wrapper to use, in case
            ## automatic_type_narrowing is active and we are not forced to
            ## make a copy of the object
            if (self.cpp_class.automatic_type_narrowing
                and (self.transfer_ownership or self.cpp_class.has_reference_counting)):

                typeid_map_name = self.cpp_class.get_type_narrowing_root().typeid_map_name
                wrapper_type = wrapper.declarations.declare_variable(
                    'PyTypeObject*', 'wrapper_type', '0')
                wrapper.before_call.write_code(
                    '%s = %s.lookup_wrapper(typeid(*%s), &%s);'
                    % (wrapper_type, typeid_map_name, value, self.cpp_class.pytypestruct))
            else:
                wrapper_type = '&'+self.cpp_class.pytypestruct

            ## Create the Python wrapper object
            if self.cpp_class.allow_subclassing:
                new_func = 'PyObject_GC_New'
            else:
                new_func = 'PyObject_New'
            wrapper.before_call.write_code(
                "%s = %s(%s, %s);" %
                (py_name, new_func, self.cpp_class.pystruct, wrapper_type))
            self.py_name = py_name

            if self.cpp_class.allow_subclassing:
                wrapper.before_call.write_code(
                    "%s->inst_dict = NULL;" % (py_name,))

            ## Assign the C++ value to the Python wrapper
            if self.transfer_ownership:
                wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
                wrapper.build_params.add_parameter("N", [py_name])
            else:
                if not self.cpp_class.has_reference_counting:
                    ## The PyObject gets a temporary pointer to the
                    ## original value; the pointer is converted to a
                    ## copy in case the callee retains a reference to
                    ## the object after the call.

                    if self.direction == Parameter.DIRECTION_IN:
                        self.cpp_class.write_create_instance(wrapper.before_call,
                                                             "%s->obj" % self.py_name,
                                                             '*'+self.value)
                        wrapper.build_params.add_parameter("N", [self.py_name])
                    else:
                        ## out/inout case:
                        ## the callee receives a "temporary wrapper", which loses
                        ## the ->obj pointer after the python call; this is so
                        ## that the python code directly manipulates the object
                        ## received as parameter, instead of a copy.
                        if self.is_const:
                            unconst_value = "const_cast< %s* >(%s)" % (self.cpp_class.full_name, value)
                        else:
                            unconst_value = value
                        wrapper.before_call.write_code(
                            "%s->obj = %s;" % (self.py_name, unconst_value))
                        wrapper.build_params.add_parameter("O", [self.py_name])
                        wrapper.before_call.add_cleanup_code("Py_DECREF(%s);" % self.py_name)

                        ## if after the call we notice the callee kept a reference
                        ## to the pyobject, we then swap pywrapper->obj for a copy
                        ## of the original object.  Else the ->obj pointer is
                        ## simply erased (we never owned this object in the first
                        ## place).
                        wrapper.after_call.write_code(
                            "if (%s->ob_refcnt == 1)\n"
                            "    %s->obj = NULL;\n"
                            "else {\n" % (self.py_name, self.py_name))
                        wrapper.after_call.indent()
                        self.cpp_class.write_create_instance(wrapper.after_call,
                                                             "%s->obj" % self.py_name,
                                                             '*'+value)
                        wrapper.after_call.unindent()
                        wrapper.after_call.write_code('}')
                else:
                    ## The PyObject gets a new reference to the same obj
                    self.cpp_class.write_incref(wrapper.before_call, value)
                    if self.is_const:
                        wrapper.before_call.write_code("%s->obj = const_cast< %s*>(%s);" %
                                                       (py_name, self.cpp_class.full_name, value))
                    else:
                        wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
                    wrapper.build_params.add_parameter("N", [py_name])
        ## closes def write_create_new_wrapper():

        if self.cpp_class.helper_class is None:
            write_create_new_wrapper()
        else:
            wrapper.before_call.write_code("if (typeid(*(%s)) == typeid(%s))\n{"
                                          % (value, self.cpp_class.helper_class.name))
            wrapper.before_call.indent()

            if self.is_const:
                wrapper.before_call.write_code(
                    "%s = reinterpret_cast< %s* >(reinterpret_cast< %s* >(const_cast< %s* > (%s))->m_pyself);"
                    % (py_name, self.cpp_class.pystruct,
                       self.cpp_class.helper_class.name, self.cpp_class.full_name, value))
                wrapper.before_call.write_code("%s->obj = const_cast< %s* > (%s);" %
                                               (py_name, self.cpp_class.full_name, value))
            else:
                wrapper.before_call.write_code(
                    "%s = reinterpret_cast< %s* >(reinterpret_cast< %s* >(%s)->m_pyself);"
                    % (py_name, self.cpp_class.pystruct,
                       self.cpp_class.helper_class.name, value))
                wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
            wrapper.before_call.write_code("Py_INCREF(%s);" % py_name)
            wrapper.before_call.unindent()
            wrapper.before_call.write_code("} else {")
            wrapper.before_call.indent()
            write_create_new_wrapper()
            wrapper.before_call.unindent()
            wrapper.before_call.write_code("}")
                



def _add_ward(wrapper, custodian, ward):
    wards = wrapper.declarations.declare_variable(
        'PyObject*', 'wards')
    wrapper.after_call.write_code(
        "%(wards)s = PyObject_GetAttrString(%(custodian)s, \"__wards__\");"
        % vars())
    wrapper.after_call.write_code(
        "if (%(wards)s == NULL) {\n"
        "    PyErr_Clear();\n"
        "    %(wards)s = PyList_New(0);\n"
        "    PyObject_SetAttrString(%(custodian)s, \"__wards__\", %(wards)s);\n"
        "}" % vars())
    wrapper.after_call.write_code("PyList_Append(%s, %s);" % (wards, ward))
    wrapper.after_call.add_cleanup_code("Py_DECREF(%s);" % wards)



class CppClassPtrReturnValue(CppClassReturnValueBase):
    "Class* return handler"
    CTYPES = []
    SUPPORTS_TRANSFORMATIONS = True
    cpp_class = CppClass('dummy') # CppClass instance

    def __init__(self, ctype, caller_owns_return=None, custodian=None, is_const=False):
        """
        ctype -- C type, normally 'MyClass*'
        caller_owns_return -- if true, ownership of the object pointer
                              is transferred to the caller; should be
                              omitted when custodian is given.
        custodian -- the object (custodian) that is responsible for
                     managing the life cycle of the return value.
                     Possible values are: None: no object is
                     custodian; the integer 0: the instance of the
                     method in which the ReturnValue is being used
                     will become the custodian; integer > 0: parameter
                     number, starting at 1, whose object will be used
                     as custodian.  Note: only C++ class parameters
                     can be used as custodians, not parameters of
                     builtin Python types.
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassPtrReturnValue, self).__init__(ctype)
        self.is_const = is_const
        if custodian is None and caller_owns_return is None:
            raise TypeConfigurationError("caller_owns_return not given")
        self.custodian = custodian
        if custodian is None:
            self.caller_owns_return = caller_owns_return
        else:
            assert caller_owns_return is None
            self.caller_owns_return = True

    def get_c_error_return(self): # only used in reverse wrappers
        """See ReturnValue.get_c_error_return"""
        return "return NULL;"

    def convert_c_to_python(self, wrapper):
        """See ReturnValue.convert_c_to_python"""

        ## Value transformations
        value = self.transformation.untransform(
            self, wrapper.declarations, wrapper.after_call, self.value)
        
        wrapper.after_call.write_code("if (!(%s)) {\n"
                                      "    Py_INCREF(Py_None);\n"
                                      "    return Py_None;\n"
                                      "}" % value)

        ## declare wrapper variable
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        self.py_name = py_name

        def write_create_new_wrapper():
            """Code path that creates a new wrapper for the returned object"""

            ## Find out what Python wrapper to use, in case
            ## automatic_type_narrowing is active and we are not forced to
            ## make a copy of the object
            if (self.cpp_class.automatic_type_narrowing
                and (self.caller_owns_return or self.cpp_class.has_reference_counting)):

                typeid_map_name = self.cpp_class.get_type_narrowing_root().typeid_map_name
                wrapper_type = wrapper.declarations.declare_variable(
                    'PyTypeObject*', 'wrapper_type', '0')
                wrapper.after_call.write_code(
                    '%s = %s.lookup_wrapper(typeid(*%s), &%s);'
                    % (wrapper_type, typeid_map_name, value, self.cpp_class.pytypestruct))

            else:

                wrapper_type = '&'+self.cpp_class.pytypestruct

            ## Create the Python wrapper object
            if self.cpp_class.allow_subclassing:
                new_func = 'PyObject_GC_New'
            else:
                new_func = 'PyObject_New'
            wrapper.after_call.write_code(
                "%s = %s(%s, %s);" %
                (py_name, new_func, self.cpp_class.pystruct, wrapper_type))
            self.py_name = py_name

            if self.cpp_class.allow_subclassing:
                wrapper.after_call.write_code(
                    "%s->inst_dict = NULL;" % (py_name,))

            ## Assign the C++ value to the Python wrapper
            if self.caller_owns_return:
                wrapper.after_call.write_code("%s->obj = %s;" % (py_name, value))
            else:
                if not self.cpp_class.has_reference_counting:
                    ## The PyObject creates its own copy
                    self.cpp_class.write_create_instance(wrapper.after_call,
                                                         "%s->obj" % py_name,
                                                         '*'+value)
                else:
                    ## The PyObject gets a new reference to the same obj
                    self.cpp_class.write_incref(wrapper.after_call, value)
                    if self.is_const:
                        wrapper.after_call.write_code("%s->obj = const_cast< %s* >(%s);" %
                                                      (py_name, self.cpp_class.full_name, value))
                    else:
                        wrapper.after_call.write_code("%s->obj = %s;" % (py_name, value))
        ## closes def write_create_new_wrapper():

        if self.cpp_class.helper_class is None:
            write_create_new_wrapper()
        else:
            wrapper.after_call.write_code("if (typeid(*(%s)) == typeid(%s))\n{"
                                          % (value, self.cpp_class.helper_class.name))
            wrapper.after_call.indent()

            wrapper.after_call.write_code(
                "%s = reinterpret_cast< %s* >(reinterpret_cast< %s* >(%s)->m_pyself);"
                % (py_name, self.cpp_class.pystruct,
                   self.cpp_class.helper_class.name, value))

            wrapper.after_call.write_code("%s->obj = %s;" % (py_name, value))
            wrapper.after_call.write_code("Py_INCREF(%s);" % py_name)
            wrapper.after_call.unindent()
            wrapper.after_call.write_code("} else {")
            wrapper.after_call.indent()
            write_create_new_wrapper()
            wrapper.after_call.unindent()
            wrapper.after_call.write_code("}")
                
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)
        
        if self.custodian is None:
            pass
        elif self.custodian == 0:
            assert wrapper.class_.allow_subclassing
            _add_ward(wrapper, '((PyObject *) self)', "((PyObject *) %s)" % py_name)
        else:
            assert self.custodian > 0
            param = wrapper.parameters[self.custodian - 1]
            assert param.cpp_class.allow_subclassing
            assert isinstance(param, CppClassParameterBase)
            _add_ward(wrapper, "((PyObject *) %s)" % param.py_name, "((PyObject *) %s)" % py_name)
    

    def convert_python_to_c(self, wrapper):
        """See ReturnValue.convert_python_to_c"""
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', "tmp_%s" % self.cpp_class.name)
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name])

        value = self.transformation.transform(
            self, wrapper.declarations, wrapper.after_call, "%s->obj" % name)

        ## now the hairy part :)
        if self.caller_owns_return:
            if not self.cpp_class.has_reference_counting:
                ## the caller receives a copy
                self.cpp_class.write_create_instance(wrapper.after_call,
                                                     "%s" % self.value,
                                                     '*'+value)
            else:
                ## the caller gets a new reference to the same obj
                self.cpp_class.write_incref(wrapper.after_call, value)
                if self.is_const:
                    wrapper.after_call.write_code(
                        "%s = const_cass< %s* >(%s);" %
                        (self.value, self.cpp_class.full_name, value))
                else:
                    wrapper.after_call.write_code(
                        "%s = %s;" % (self.value, value))
        else:
            ## caller gets a shared pointer
            ## but this is dangerous, avoid at all cost!!!
            wrapper.after_call.write_code(
                "// dangerous!\n%s = %s;" % (self.value, value))
            warnings.warn("Returning shared pointers is dangerous!"
                          "  The C++ API should be redesigned "
                          "to avoid this situation.")
            

def implement_parameter_custodians(wrapper):
    """
    Generate the necessary code to implement the custodian=<N> option
    of C++ class parameters.  It accepts a Forward Wrapper as argument.
    """
    assert isinstance(wrapper, ForwardWrapperBase)
    for param in wrapper.parameters:
        if not isinstance(param, CppClassPtrParameter):
            continue
        if param.custodian is None:
            continue
        if param.custodian == -1: # the custodian is the return value
            assert wrapper.return_value.cpp_class.allow_subclassing
            _add_ward(wrapper, "((PyObject *) %s)" % wrapper.return_value.py_name,
                       "((PyObject *) %s)" % param.py_name)
        elif param.custodian == 0: # the custodian is the method self
            assert wrapper.class_.allow_subclassing
            _add_ward(wrapper, "((PyObject *) self)",
                       "((PyObject *) %s)" % param.py_name)
        else: # the custodian is another parameter
            assert param.custodian > 0
            custodian_param = wrapper.parameters[param.custodian - 1]
            assert custodian_param.cpp_class.allow_subclassing
            _add_ward(wrapper, "((PyObject *) %s)" % custodian_param.py_name,
                       "((PyObject *) %s)" % param.py_name)


import function
