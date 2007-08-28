"""
Wrap C++ classes and methods
"""

import warnings

from typehandlers.base import ForwardWrapperBase, Parameter, ReturnValue, \
    join_ctype_and_name

from cppmethod import CppMethod, CppConstructor, CppNoConstructor, \
    CppOverloadedMethod, CppOverloadedConstructor, \
    CppVirtualMethodParentCaller, CppVirtualMethodProxy

from cppattribute import (CppInstanceAttributeGetter, CppInstanceAttributeSetter,
                          CppStaticAttributeGetter, CppStaticAttributeSetter,
                          PyGetSetDef, PyMetaclass)
import settings

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
        self.name = class_.name + "_PythonProxy"
        ## TODO: inheritance of virtual methods
        self.virtual_parent_callers = []
        self.virtual_proxies = []
        
    def add_virtual_parent_caller(self, parent_caller):
        """Add a new CppVirtualMethodParentCaller object to this helper class"""
        assert isinstance(parent_caller, CppVirtualMethodParentCaller)
        self.virtual_parent_callers.append(parent_caller)

    def add_virtual_proxy(self, virtual_proxy):
        """Add a new CppVirtualMethodProxy object to this class"""
        assert isinstance(virtual_proxy, CppVirtualMethodProxy)
        self.virtual_proxies.append(virtual_proxy)

    def generate(self, code_sink):
        """
        Generate the proxy class to a given code sink
        """
        code_sink.writeln("class %s : public %s\n{\npublic:" %
                          (self.name, self.class_.name))

        code_sink.indent()
        code_sink.writeln("PyObject *m_pyself;")

        ## write the constructors
        for cons in self.class_.constructors:
            params = ['PyObject *pyself']
            params.extend([join_ctype_and_name(param.ctype, param.name)
                           for param in cons.parameters])
            code_sink.writeln("%s(%s)" % (self.name, ', '.join(params)))
            code_sink.indent()
            code_sink.writeln(": %s(%s), m_pyself((Py_INCREF(pyself), pyself))\n{}" %
                              (self.class_.name,
                               ', '.join([param.name for param in cons.parameters])))
            code_sink.unindent()
            code_sink.writeln()

        ## write a destructor
        code_sink.writeln("~%s()\n{" % self.name)
        code_sink.indent()
        code_sink.writeln("Py_CLEAR(m_pyself);")
        code_sink.unindent()
        code_sink.writeln("}\n")
            
        ## write the parent callers (_name)
        for parent_caller in self.virtual_parent_callers:
            parent_caller.class_ = self.class_
            parent_caller.helper_class = self
            code_sink.writeln()
            parent_caller.generate(code_sink)

        ## write the virtual proxies
        for virtual_proxy in self.virtual_proxies:
            virtual_proxy.class_ = self.class_
            virtual_proxy.helper_class = self
            code_sink.writeln()
            virtual_proxy.generate(code_sink)

        code_sink.unindent()
        code_sink.writeln("};\n")


class CppClass(object):
    """
    A CppClass object takes care of generating the code for wrapping a C++ class
    """

    TYPE_TMPL = (
        'PyTypeObject %(typestruct)s = {\n'
        '    PyObject_HEAD_INIT(NULL)\n'
        '    0,                                 /* ob_size */\n'
        '    "%(classname)s",                   /* tp_name */\n'
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
                 automatic_type_narrowing=None, allow_subclassing=None):
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
        """
        self.name = name
        self.full_name = None # full name with C++ namespaces attached
        self.methods = {} # name => OverloadedMethod
        self.constructors = [] # (name, wrapper) pairs
        self.slots = dict()
        self.helper_class = None
        ## list of CppClasses from which a value of this class can be
        ## implicitly generated; corresponds to a
        ## operator ThisClass(); in the other class.
        self.implicitly_converts_from = []

        prefix = settings.name_prefix.capitalize()
        self.pystruct = "Py%s%s" % (prefix, self.name)
        self.metaclass_name = "%sMeta" % self.pystruct
        self.pytypestruct = "Py%s%s_Type" % (prefix, self.name)

        self.instance_attributes = PyGetSetDef("%s__getsets" % self.pystruct)
        self.static_attributes = PyGetSetDef("%s__getsets" % self.metaclass_name)

        self.parent = parent
        assert parent is None or isinstance(parent, CppClass)
        assert (incref_method is None and decref_method is None) \
               or (incref_method is not None and decref_method is not None)
        if incref_method is None and parent is not None:
            self.incref_method = parent.incref_method
            self.decref_method = parent.decref_method
        else:
            self.incref_method = incref_method
            self.decref_method = decref_method

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

        self.typeid_map = None
        self.typeid_map_name = None # name of C++ variable
        if self.automatic_type_narrowing:
            self._register_typeid()

        if name != 'dummy':
            ## register type handlers
            class ThisClassParameter(CppClassParameter):
                """Register this C++ class as pass-by-value parameter"""
                CTYPES = [name]
                cpp_class = self
            self.ThisClassParameter = ThisClassParameter

            class ThisClassRefParameter(CppClassRefParameter):
                """Register this C++ class as pass-by-reference parameter"""
                CTYPES = [name+'&']
                cpp_class = self
            self.ThisClassRefParameter = ThisClassRefParameter

            class ThisClassReturn(CppClassReturnValue):
                """Register this C++ class as value return"""
                CTYPES = [name]
                cpp_class = self
            self.ThisClassReturn = ThisClassReturn

            class ThisClassPtrParameter(CppClassPtrParameter):
                """Register this C++ class as pass-by-pointer parameter"""
                CTYPES = [name+'*']
                cpp_class = self
            self.ThisClassPtrParameter = ThisClassPtrParameter

            class ThisClassPtrReturn(CppClassPtrReturnValue):
                """Register this C++ class as pointer return"""
                CTYPES = [name+'*']
                cpp_class = self
            self.ThisClassPtrReturn = ThisClassPtrReturn

        self._inherit_default_constructors()

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
        ['Bar', 'Zbr']
        """
        classes = []
        to_visit = list(self.implicitly_converts_from)
        while to_visit:
            source = to_visit.pop(0)
            if source in classes or source is self:
                continue
            classes.append(source)
            to_visit.extend(source.implicitly_converts_from)
        return classes

    def get_module(self):
        """Get the Module object this class belongs to"""
        return self._module

    def set_module(self, module):
        """Set the Module object this class belongs to"""
        self._module = module
        if module.cpp_namespace_prefix:
            self.full_name = module.cpp_namespace_prefix + '::' + self.name
        else:
            self.full_name = self.name

    module = property(get_module, set_module)


    def _inherit_default_constructors(self):
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
        if self.helper_class is None:
            self.helper_class = CppHelperClass(self)
        return self.helper_class
    
    def get_type_narrowing_root(self):
        """Find the root CppClass along the subtree of all parent classes that
        have automatic_type_narrowing=True Note: multiple inheritance
        not implemented"""
        root = self
        while (root.parent is not None
               and root.parent.automatic_type_narrowing):
            root = root.parent
        return root

    def _register_typeid(self):
        """register this class with the typeid map root class"""
        root = self.get_type_narrowing_root()
        if root is self:
            ## since we are the root, we are responsible for creating
            ## and managing the typeid table
            self.typeid_map = [self] # list of registered subclasses
            self.typeid_map_name = "%s__typeid_map" % self.pystruct
        else:
            root.typeid_map.append(self)

    def _generate_typeid_map(self, code_sink, module):
        """generate the typeid map and fill it with values"""
        try:
            module.declare_one_time_definition("TypeIDMap")
        except KeyError:
            pass
        else:
            module.header.writeln('''

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
        module.header.writeln("\npybindgen::TypeMap %s;\n" % self.typeid_map_name)
        for subclass in self.typeid_map:
            module.after_init.write_code("%s.register_wrapper(typeid(%s), &%s);"
                                         % (self.typeid_map_name, subclass.full_name,
                                            subclass.pytypestruct))

    def add_method(self, method, name=None):
        """
        Add a method to the class.

        method -- a CppMethod instance that can generate the method wrapper
        name -- optional name of the class method as it will appear
                from Python side
        """
        assert name is None or isinstance(name, str)
        assert isinstance(method, CppMethod)
        if name is None:
            name = method.method_name
            
        try:
            overload = self.methods[name]
        except KeyError:
            overload = CppOverloadedMethod(name)
            overload.pystruct = self.pystruct
            self.methods[name] = overload

        method.class_ = self
        overload.add(method)
        if method.is_virtual:
            if not self.allow_subclassing:
                raise ValueError("Cannot add virtual methods if subclassing "
                                 "support was not enabled for this class")
            helper_class = self.get_helper_class()

            parent_caller = CppVirtualMethodParentCaller(method.return_value,
                                                         method.method_name,
                                                         method.parameters)
            helper_class.add_virtual_parent_caller(parent_caller)

            proxy = CppVirtualMethodProxy(method.return_value,
                                          method.method_name,
                                          method.parameters,
                                          is_const=method.is_const)
            helper_class.add_virtual_proxy(proxy)
            

    def add_constructor(self, wrapper):
        """
        Add a constructor to the class.

        wrapper -- a CppConstructor instance
        """
        assert isinstance(wrapper, CppConstructor)
        wrapper.set_class(self)
        self.constructors.append(wrapper)

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

    def add_instance_attribute(self, value_type, name, is_const=False):
        """
        value_type -- a ReturnValue object
        name -- attribute name (i.e. the name of the class member variable)
        is_const -- True if the attribute is const, i.e. cannot be modified
        """
        assert isinstance(value_type, ReturnValue)
        getter = CppInstanceAttributeGetter(value_type, self, name)
        if is_const:
            setter = None
        else:
            setter = CppInstanceAttributeSetter(value_type, self, name)
        self.instance_attributes.add_attribute(name, getter, setter)

    def generate_forward_declarations(self, code_sink):
        """Generates forward declarations for the instance and type
        structures"""

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

        if self.helper_class is not None:
            self.helper_class.generate(code_sink)       


    def generate(self, code_sink, module, docstring=None):
        """Generates the class to a code sink"""

        ## generate getsets
        instance_getsets = self.instance_attributes.generate(code_sink)
        self.slots.setdefault("tp_getset", instance_getsets)
        static_getsets = self.static_attributes.generate(code_sink)

        ## --- register the class type in the module ---
        module.after_init.write_code("/* Register the '%s' class */" % self.name)

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
        module.after_init.write_code(
            'PyModule_AddObject(m, \"%s\", (PyObject *) &%s);' % (
            self.name, self.pytypestruct))

        have_constructor = self._generate_constructor(code_sink)

        self._generate_methods(code_sink)

        if self.allow_subclassing:
            self._generate_gc_methods(code_sink)

        self._generate_destructor(code_sink, have_constructor)
        self._generate_type_structure(code_sink, docstring)
        if self.typeid_map is not None:
            self._generate_typeid_map(code_sink, module)

        
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
        dict_ = dict(self.slots)
        dict_.setdefault("typestruct", self.pytypestruct)
        dict_.setdefault("classname", self.name)
        
        code_sink.writeln(self.TYPE_TMPL % dict_)


    def _generate_constructor(self, code_sink):
        """generate the constructor, if any"""
        have_constructor = True
        if self.constructors:
            code_sink.writeln()
            overload = CppOverloadedConstructor(None)
            self.constructors_overload = overload
            overload.pystruct = self.pystruct
            for constructor in self.constructors:
                overload.add(constructor)
            overload.generate(code_sink)
            constructor = overload.wrapper_function_name
            code_sink.writeln()
        else:
            ## In C++, and unlike Python, constructors with
            ## parameters are not automatically inheritted by
            ## subclasses.  We must generate a 'no constructor'
            ## tp_init to prevent this type from inheriring a
            ## tp_init that will allocate an instance of the
            ## parent class instead of this class.
            code_sink.writeln()
            constructor = CppNoConstructor().generate(code_sink, self)
            have_constructor = False
            code_sink.writeln()

        self.slots.setdefault("tp_init", (constructor is None and "NULL"
                                          or constructor))
        return have_constructor

    def _generate_methods(self, code_sink):
        """generate the method wrappers"""
        method_defs = []
        for meth_name, overload in self.methods.iteritems():
            code_sink.writeln()
            overload.generate(code_sink)
            method_defs.append(overload.get_py_method_def(meth_name))
            code_sink.writeln()
        if self.helper_class is not None:
            for meth in self.helper_class.virtual_parent_callers:
                method_defs.append(meth.get_py_method_def())
        ## generate the method table
        code_sink.writeln("static PyMethodDef %s_methods[] = {" % (self.name,))
        code_sink.indent()
        for methdef in method_defs:
            code_sink.writeln(methdef)
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")
        self.slots.setdefault("tp_methods", "%s_methods" % (self.name,))

    def _generate_gc_methods(self, code_sink):
        """Generate tp_clear and tp_traverse"""

        ## --- tp_clear ---
        tp_clear_function_name = "%s__tp_clear" % (self.pystruct,)
        self.slots.setdefault("tp_clear", tp_clear_function_name )

        if self.decref_method is None:
            delete_code = "delete self->obj;"
        else:
            delete_code = ("if (self->obj)\n        self->obj->%s();"
                           % (self.decref_method,))

        code_sink.writeln(r'''
static void
%s(%s *self)
{
    // fprintf(stderr, "tp_clear >>> %%s at %%p <<<\n", self->ob_type->tp_name, self);
    Py_CLEAR(self->inst_dict);
    %s
    self->obj = 0;
}
''' % (tp_clear_function_name, self.pystruct, delete_code))

        ## --- tp_traverse ---
        tp_traverse_function_name = "%s__tp_traverse" % (self.pystruct,)
        self.slots.setdefault("tp_traverse", tp_traverse_function_name )

        if self.helper_class is None:
            visit_self = ''
        else:
            visit_self = '''
    if (self->obj && typeid(*self->obj) == typeid(%s))
        Py_VISIT(self);
''' % self.helper_class.name

        code_sink.writeln(r'''
static int
%s(%s *self, visitproc visit, void *arg)
{
    // fprintf(stderr, "tp_traverse >>> %%s at %%p <<<\n", self->ob_type->tp_name, self);
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
            if self.decref_method is None:
                delete_code = "delete tmp;"
            else:
                delete_code = ("if (tmp)\n        tmp->%s();"
                               % (self.decref_method,))

        if have_constructor:
            code_sink.writeln(r'''
static void
%s(%s *self)
{
    // fprintf(stderr, "dealloc >>> %%s at %%p <<<\n", self->ob_type->tp_name, self);
    %s
    self->obj = NULL;
    %s
    %s
    self->ob_type->tp_free((PyObject*)self);
}
''' % (tp_dealloc_function_name, self.pystruct,
       (delete_code and ("%s *tmp = self->obj;" % self.full_name) or ''),
       delete_code, clear_code))

        else: # don't have constructor

            code_sink.writeln('''
static void
%s(%s *self)
{
    %s *tmp = self->obj;
    %s
    %s
    self->ob_type->tp_free((PyObject*)self);
}
''' % (tp_dealloc_function_name, self.pystruct, self.full_name, clear_code, delete_code))
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

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassParameterBase, self).__init__(
            ctype, name, direction)

        ## name of the PyFoo * variable used in parameter parsing
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
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', self.name)
        self.py_name = name
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name], self.name)
        wrapper.call_params.append(
            '*((%s *) %s)->obj' % (self.cpp_class.pystruct, name))


class CppClassRefParameter(CppClassParameterBase):
    "Class& handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_INOUT]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassRefParameter, self).__init__(
            ctype, name, direction)
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, CppClass)

        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', self.name)
        self.py_name = name

        if self.direction == Parameter.DIRECTION_IN:
            wrapper.parse_params.add_parameter(
                'O!', ['&'+self.cpp_class.pytypestruct, '&'+name], self.name)
            wrapper.call_params.append('*%s->obj' % (name,))

        elif self.direction == Parameter.DIRECTION_OUT:
            if self.cpp_class.allow_subclassing:
                new_func = 'PyObject_GC_New'
            else:
                new_func = 'PyObject_New'
            wrapper.before_call.write_code(
                "%s = %s(%s, %s);" %
                (name, new_func, self.cpp_class.pystruct,
                 '&'+self.cpp_class.pytypestruct))
            if self.cpp_class.allow_subclassing:
                wrapper.after_call.write_code(
                    "%s->inst_dict = NULL;" % (name,))
            wrapper.before_call.write_code(
                "%s->obj = new %s;" % (name, self.cpp_class.full_name))
            wrapper.call_params.append('*%s->obj' % (name,))
            wrapper.build_params.add_parameter("N", [name])

        ## well, personally I think inout here doesn't make much sense
        ## (it's just plain confusing), but might as well support it..
        elif self.direction == Parameter.DIRECTION_INOUT:
            wrapper.parse_params.add_parameter(
                'O!', ['&'+self.cpp_class.pytypestruct, '&'+name], self.name)
            wrapper.call_params.append(
                '*%s->obj' % (name))
            wrapper.build_params.add_parameter("O", [name])


class CppClassReturnValue(ReturnValue):
    "Class return handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance

    def __init__(self, ctype):
        """override to fix the ctype parameter with namespace information"""
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassReturnValue, self).__init__(ctype)

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
        wrapper.after_call.write_code(
            "%s->obj = new %s(%s);" % (py_name, self.cpp_class.full_name, self.value))
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)

    def convert_python_to_c(self, wrapper):
        """see ReturnValue.convert_python_to_c"""
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', "tmp_%s" % self.cpp_class.full_name)
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name])
        wrapper.after_call.write_code('%s = *%s->obj;' % (self.value, name))
    


class CppClassPtrParameter(CppClassParameterBase):
    "Class* handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    SUPPORTS_TRANSFORMATIONS = True

    def __init__(self, ctype, name, transfer_ownership):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name
        transfer_ownership -- this parameter transfer the ownership of
                              the pointed-to object to the called function
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassPtrParameter, self).__init__(
            ctype, name, direction=Parameter.DIRECTION_IN)
        self.transfer_ownership = transfer_ownership
        
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, CppClass)
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', self.name)
        self.py_name = name
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name], self.name)

        value = self.transformation.transform(
            self, wrapper.declarations, wrapper.before_call, '%s->obj' % name)
        wrapper.call_params.append(value)
        
        if self.transfer_ownership:
            if self.cpp_class.incref_method is None:
                wrapper.after_call.write_code('%s->obj = NULL;' % (name,))
            else:
                wrapper.before_call.write_code('%s->obj->%s();' % (
                    name, self.cpp_class.incref_method,))


class CppClassPtrReturnValue(ReturnValue):
    "Class* return handler"
    CTYPES = []
    SUPPORTS_TRANSFORMATIONS = True
    cpp_class = CppClass('dummy') # CppClass instance

    def __init__(self, ctype, caller_owns_return=None, custodian=None):
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
        if custodian is None and caller_owns_return is None:
            raise TypeError("caller_owns_return not given")
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
                and (self.caller_owns_return or self.cpp_class.incref_method is not None)):

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
                if self.cpp_class.incref_method is None:
                    ## The PyObject creates its own copy
                    wrapper.after_call.write_code(
                        "%s->obj = new %s(*%s);"
                        % (py_name, self.cpp_class.full_name, value))
                else:
                    ## The PyObject gets a new reference to the same obj
                    wrapper.after_call.write_code(
                        "%s->%s();" % (value, self.cpp_class.incref_method))
                    wrapper.after_call.write_code("%s->obj = %s;" % (py_name, value))

        if self.cpp_class.helper_class is None:
            write_create_new_wrapper()
        else:
            wrapper.after_call.write_code("if (typeid(*(%s)) == typeid(%s))\n{"
                                          % (value, self.cpp_class.helper_class.name))
            wrapper.after_call.indent()

            wrapper.after_call.write_code(
                "%s = reinterpret_cast<%s*>(reinterpret_cast<%s*>(%s)->m_pyself);"
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
        
        def add_ward(custodian, ward):
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
            
        if self.custodian is None:
            pass
        elif self.custodian == 0:
            add_ward('((PyObject *) self)', "((PyObject *) %s)" % py_name)
        else:
            assert self.custodian > 0
            param = wrapper.parameters[self.custodian - 1]
            assert isinstance(param, CppClassParameterBase)
            add_ward("((PyObject *) %s)" % param.py_name, "((PyObject *) %s)" % py_name)
    

    def convert_python_to_c(self, wrapper):
        """See ReturnValue.convert_python_to_c"""
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', "tmp_%s" % self.cpp_class.name)
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name])

        value = self.transformation.untransform(
            self, wrapper.declarations, wrapper.after_call, "%s->obj" % name)

        ## now the hairy part :)
        if self.caller_owns_return:
            if self.cpp_class.incref_method is None:
                ## the caller receives a copy
                wrapper.after_call.write_code(
                    "%s = new %s(*%s);"
                    % (self.value, self.cpp_class.full_name, value))
            else:
                ## the caller gets a new reference to the same obj
                wrapper.after_call.write_code(
                    "%s->%s();" % (value, self.cpp_class.incref_method))
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
            

