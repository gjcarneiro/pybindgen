"""
Wrap C++ classes and methods
"""

from typehandlers.base import ForwardWrapperBase, Parameter, ReturnValue
from typehandlers import codesink
import settings



class CppMethod(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C++ class method
    """

    def __init__(self, return_value, method_name, parameters, is_static=False):
        """
        return_value -- the method return value
        method_name -- name of the method
        parameters -- the method parameters
        is_static -- whether it is a static method
        """
        super(CppMethod, self).__init__(
            return_value, parameters,
            "return NULL;", "return NULL;")
        self.method_name = method_name
        self.is_static = is_static

    
    def generate_call(self, class_):
        "virtual method implementation; do not call"
        assert isinstance(class_, CppClass)
        if self.is_static:
            method = '%s::%s' % (class_.name, self.method_name)
        else:
            method = 'self->obj->%s' % self.method_name
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' %
                (method, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = %s(%s);' %
                (method, ", ".join(self.call_params)))


    def generate(self, code_sink, class_, method_name, docstring=None):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        class_ -- the c++ class wrapper the method belongs to
        method_name -- actual name the method will get
        docstring -- optional documentation string

        Returns the corresponding PyMethodDef entry string.
        """
        assert isinstance(class_, CppClass)
        tmp_sink = codesink.MemoryCodeSink()

        self.generate_body(tmp_sink, gen_call_params=[class_])

        wrapper_function_name = "_wrap_%s_%s" % (
            class_.name, self.method_name)

        flags = self.get_py_method_def_flags()
        if self.is_static:
            flags.append('METH_STATIC')

        code_sink.writeln("static PyObject *")
        if 'METH_STATIC' in flags:
            _self_name = 'dummy PYBINDGEN_UNUSED'
        else:
            _self_name = 'self'

        if 'METH_VARARGS' in flags:
            if 'METH_KEYWORDS' in flags:
                code_sink.writeln(
                    "%s(%s *%s, PyObject *args, PyObject *kwargs)"
                    % (wrapper_function_name, class_.pystruct, _self_name))
            else:
                code_sink.writeln(
                    "%s(%s *%s, PyObject *args)"
                    % (wrapper_function_name, class_.pystruct, _self_name))
        else:
            if 'METH_STATIC' in flags:
                code_sink.writeln("%s(void)" % (wrapper_function_name,))
            else:
                code_sink.writeln(
                    "%s(%s *%s)"
                    % (wrapper_function_name, class_.pystruct, _self_name))
                
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')

        return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
               (method_name, wrapper_function_name, '|'.join(flags),
                (docstring is None and "NULL" or ('"'+docstring+'"')))


class CppConstructor(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C++ class constructor.  Such
    wrapper is used as the python class __init__ method.
    """

    def __init__(self, parameters):
        """
        parameters -- the constructor parameters
        """
        super(CppConstructor, self).__init__(
            None, parameters,
            "return -1;", "return -1;",
            force_parse=ForwardWrapperBase.PARSE_TUPLE_AND_KEYWORDS)
    
    def generate_call(self, class_):
        "virtual method implementation; do not call"
        assert isinstance(class_, CppClass)
        self.before_call.write_code(
            'self->obj = new %s(%s);' %
            (class_.name, ", ".join(self.call_params)))

    def generate(self, code_sink, class_):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        class_ -- the c++ class wrapper the method belongs to

        Returns the wrapper function name.
        """
        assert isinstance(class_, CppClass)
        tmp_sink = codesink.MemoryCodeSink()

        self.generate_body(tmp_sink, gen_call_params=[class_])

        assert ((self.parse_params.get_parameters() == ['""'])
                or self.parse_params.get_keywords() is not None), \
               ("something went wrong with the type handlers;"
                " constructors need parameter names, "
                "yet no names were given for the class %s constructor"
                % class_.name)

        wrapper_function_name = "_wrap_%s__tp_init" % (
            class_.name,)
        code_sink.writeln("static int")
        code_sink.writeln(
            "%s(%s *self, PyObject *args, PyObject *kwargs)"
            % (wrapper_function_name, class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.writeln('return 0;')
        code_sink.unindent()
        code_sink.writeln('}')

        return wrapper_function_name


class CppNoConstructor(ForwardWrapperBase):
    """

    Class that generates a constructor that raises an exception saying
    that the class has no constructor.

    """

    def __init__(self):
        """
        """
        super(CppNoConstructor, self).__init__(
            None, [],
            "return -1;", "return -1;")

    def generate_call(self, code_sink):
        "dummy method, not really called"
        pass
    
    def generate(self, code_sink, class_):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        class_ -- the c++ class wrapper the method belongs to

        Returns the wrapper function name.
        """
        assert isinstance(class_, CppClass)

        wrapper_function_name = "_wrap_%s__tp_init" % (
            class_.name,)
        code_sink.writeln("static int")
        code_sink.writeln("%s(void)" % wrapper_function_name)
        code_sink.writeln('{')
        code_sink.indent()
        code_sink.writeln('PyErr_SetString(PyExc_TypeError, "class \'%s\' '
                          'cannot be constructed");' % class_.name)
        code_sink.writeln('return -1;')
        code_sink.unindent()
        code_sink.writeln('}')

        return wrapper_function_name

class CppInstanceAttributeGetter(ForwardWrapperBase):
    '''
    A getter for a C++ instance attribute.
    '''
    def __init__(self, value_type, class_, attribute_name):
        """
        value_type -- a ReturnValue object handling the value type;
        class_ -- the class (CppClass object)
        attribute_name -- name of attribute
        """
        super(CppInstanceAttributeGetter, self).__init__(
            value_type, [], "return NULL;", "return NULL;")
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__get_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
    def generate_call(self):
        "virtual method implementation; do not call"
        self.before_call.write_code(
            "retval = self->obj->%s;" % (self.attribute_name))
    def generate(self, code_sink):
        """
        code_sink -- a CodeSink instance that will receive the generated code
        """
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject* %s(%s *self)" % (self.c_function_name,
                                                             self.class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')

class CppStaticAttributeGetter(ForwardWrapperBase):
    '''
    A getter for a C++ class static attribute.
    '''
    def __init__(self, value_type, class_, attribute_name):
        """
        value_type -- a ReturnValue object handling the value type;
        c_value_expression -- C value expression
        """
        super(CppStaticAttributeGetter, self).__init__(
            value_type, [], "return NULL;", "return NULL;")
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__get_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
    def generate_call(self):
        "virtual method implementation; do not call"
        self.before_call.write_code(
            "retval = %s::%s;" % (self.class_.name, self.attribute_name))
    def generate(self, code_sink):
        """
        code_sink -- a CodeSink instance that will receive the generated code
        """
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject* %s(void)" % self.c_function_name)
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')


class PyDescrGenerator(object):
    def __init__(self, name, descr_get, descr_set):
        self.name = name
        self.descr_get = descr_get
        self.descr_set = descr_set
        prefix = settings.name_prefix.capitalize()
        self.pytypestruct = "Py%s%s_Type" % (prefix, self.name)

    def generate(self, code_sink):
        code_sink.writeln('''
PyTypeObject %(pytypestruct)s = {
	PyObject_HEAD_INIT(NULL)
	0,					/* ob_size */
	"%(name)s",			        /* tp_name */
	0,					/* tp_basicsize */
	0,					/* tp_itemsize */
	0,	 				/* tp_dealloc */
	0,					/* tp_print */
	0,					/* tp_getattr */
	0,					/* tp_setattr */
	0,					/* tp_compare */
	0,					/* tp_repr */
	0,					/* tp_as_number */
	0,					/* tp_as_sequence */
	0,		       			/* tp_as_mapping */
	0,					/* tp_hash */
	0,					/* tp_call */
	0,					/* tp_str */
	0,					/* tp_getattro */
	0,					/* tp_setattro */
	0,					/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,			/* tp_flags */
 	0,					/* tp_doc */
	0,					/* tp_traverse */
 	0,					/* tp_clear */
	0,					/* tp_richcompare */
	0,					/* tp_weaklistoffset */
	0,					/* tp_iter */
	0,					/* tp_iternext */
	0,					/* tp_methods */
	0,					/* tp_members */
	0,					/* tp_getset */
	0,					/* tp_base */
	0,					/* tp_dict */
	(descrgetfunc) %(descr_get)s,	        /* tp_descr_get */
	(descrsetfunc) %(descr_set)s,  		/* tp_descr_set */
	0,					/* tp_dictoffset */
	0,					/* tp_init */
	0,					/* tp_alloc */
	0,					/* tp_new */
	0,               			/* tp_free */
        0,                                      /* tp_is_gc */
        0,                                      /* tp_bases */
        0,                                      /* tp_mro */
        0,                                      /* tp_cache */
        0,                                      /* tp_subclasses */
        0,                                      /* tp_weaklist */
        0                                       /* tp_del */
};
''' % dict(pytypestruct=self.pytypestruct, name=self.name,
           descr_get=(self.descr_get or '0'),
           descr_set=(self.descr_set or '0')))
        


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
        '    (struct PyGetSetDef*)%(tp_getset)s,  /* tp_getset */\n'
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

    def __init__(self, name, parent=None, incref_method=None, decref_method=None):
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
        """
        self.name = name
        self.methods = [] # (name, wrapper) pairs
        self.constructors = [] # (name, wrapper) pairs
        self.attributes = [] # (name, getter, setter) pairs
        self.slots = dict()
        prefix = settings.name_prefix.capitalize()
        self.pystruct = "Py%s%s" % (prefix, self.name)
        self.pytypestruct = "Py%s%s_Type" % (prefix, self.name)
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

        if name != 'dummy':
            ## register type handlers
            class ThisClassParameter(CppClassParameter):
                CTYPES = [name]
                cpp_class = self
            class ThisClassRefParameter(CppClassRefParameter):
                CTYPES = [name+'&']
                cpp_class = self
            class ThisClassReturn(CppClassReturnValue):
                CTYPES = [name]
                cpp_class = self
            class ThisClassPtrParameter(CppClassPtrParameter):
                CTYPES = [name+'*']
                cpp_class = self
            class ThisClassPtrReturn(CppClassPtrReturnValue):
                CTYPES = [name+'*']
                cpp_class = self


    def add_method(self, wrapper, name=None):
        """
        Add a method to the class.

        wrapper -- a CppMethod instance that can generate the wrapper
        name -- optional name of the class method as it will appear
                from Python side
        """
        assert name is None or isinstance(name, str)
        assert isinstance(wrapper, CppMethod)
        if name is None:
            name = wrapper.method_name
        self.methods.append((name, wrapper))


    def add_constructor(self, wrapper):
        """
        Add a constructor to the class.

        Caveat: multiple constructors not yet supported

        wrapper -- a CppConstructor instance
        """
        assert isinstance(wrapper, CppConstructor)
        if self.constructors:
            raise NotImplementedError(
                'multiple constructors not yet supported')
        self.constructors.append(wrapper)

    def add_static_attribute(self, value_type, name):
        """
        XXX: not working correctly: 1. getter only works from
        instances, not classes. 2. setter not yet implemented.

        value_type -- a ReturnValue object
        """
        assert isinstance(value_type, ReturnValue)
        getter = CppStaticAttributeGetter(value_type, self, name)
        self.attributes.append((name, getter, None))

    def add_instance_attribute(self, value_type, name):
        """
        XXX: not working correctly: setter not yet implemented.

        value_type -- a ReturnValue object
        """
        assert isinstance(value_type, ReturnValue)
        getter = CppInstanceAttributeGetter(value_type, self, name)
        self.attributes.append((name, getter, None))

    def generate_forward_declarations(self, code_sink):
        """Generates forward declarations for the instance and type
        structures"""

        code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *obj;
} %s;
''' % (self.name, self.pystruct))

        code_sink.writeln()
        code_sink.writeln('extern PyTypeObject %s;' % (self.pytypestruct,))
        code_sink.writeln()
        

    def generate(self, code_sink, module, docstring=None):
        """Generates the class to a code sink"""

        ## --- register the class type in the module ---
        module.after_init.write_code("/* Register the '%s' class */" % self.name)
        if self.parent is not None:
            assert isinstance(self.parent, CppClass)
            module.after_init.write_code('%s.tp_base = &%s;' %
                                         (self.pytypestruct, self.parent.pytypestruct))
        module.after_init.write_error_check('PyType_Ready(&%s)'
                                          % (self.pytypestruct,))
        module.after_init.write_code(
            'PyModule_AddObject(m, \"%s\", (PyObject *) &%s);' % (
            self.name, self.pytypestruct))


        ## generate the constructor, if any
        if self.constructors:
            code_sink.writeln()
            constructor = self.constructors[0].generate(code_sink, self)
            code_sink.writeln()
        else:
            ## if there is a parent constructor with no arguments,
            ## a similar constructor should be added to this class
            if (self.parent is not None and self.parent.constructors
                and not self.parent.constructors[0].parameters):
                cons = CppConstructor([])
                code_sink.writeln()
                constructor = cons.generate(code_sink, self)
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
                code_sink.writeln()


        ## generate the method wrappers
        method_defs = []
        for meth_name, meth_wrapper in self.methods:
            code_sink.writeln()
            method_defs.append(meth_wrapper.generate(
                code_sink, self, meth_name))
            code_sink.writeln()
        ## generate the method table
        code_sink.writeln("static PyMethodDef %s_methods[] = {" % (self.name,))
        code_sink.indent()
        for methdef in method_defs:
            code_sink.writeln(methdef)
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")


        ## generate descriptor table for instance attributes
        if self.attributes:
            have_instance_attributes = False
            for name, getter, setter in self.attributes:

                if isinstance(getter, CppInstanceAttributeGetter):
                    have_instance_attributes = True
                    getter.generate(code_sink)
                    ## getter.c_function_name is then added to the
                    ## tp_getset table, further below.

                elif isinstance(getter, CppStaticAttributeGetter):
                    ## static attributes are a bit more tricky.. :-/
                    ## mainly because PyDecr_NewGetSet generates a
                    ## descriptor that disables itself when called
                    ## from a class; it only handles instances.
                    getter.generate(code_sink)
                    descriptor = PyDescrGenerator(
                        '%s_%sDescr' % (self.pystruct, name),
                        getter.c_function_name, None)
                    descriptor.generate(code_sink)
                    module.after_init.write_error_check(
                        'PyType_Ready(&%s)' % (descriptor.pytypestruct))
                    module.after_init.write_code(
                        'PyDict_SetItemString(%s.tp_dict, "%s", PyObject_New(PyObject, &%s));'
                        % (self.pytypestruct, name, descriptor.pytypestruct))
                    
            if have_instance_attributes:
                getset_table_name = "_%s__getsets" % self.pystruct
                self.slots.setdefault("tp_getset", getset_table_name)
                code_sink.writeln("static PyGetSetDef %s[] = {" % getset_table_name)
                code_sink.indent()
                for name, getter, setter in self.attributes:
                    if isinstance(getter, CppStaticAttributeGetter) \
                       or isinstance(setter, CppStaticAttributeGetter):
                        continue # static attributes do not use tp_getset
                    code_sink.writeln('{')
                    code_sink.indent()
                    code_sink.writeln('"%s", /* attribute name */' % name)
                    if isinstance(getter, CppInstanceAttributeGetter):
                        getter_c_name = getter.c_function_name
                    else:
                        getter_c_name = "NULL"
                    code_sink.writeln(
                        '(getter) %s, /* C function to get the attribute */'
                        % getter_c_name)
                    setter_c_name = "NULL"
                    code_sink.writeln(
                        '(setter) %s, /* C function to set the attribute */'
                        % setter_c_name)
                    code_sink.writeln('NULL, /* optional doc string */')
                    code_sink.writeln('NULL /* optional additional data '
                                      'for getter and setter */')
                    code_sink.unindent()
                    code_sink.writeln('},')
                code_sink.writeln('{ NULL, NULL, NULL, NULL, NULL }')
                code_sink.unindent()
                code_sink.writeln('};')
            else:
                self.slots.setdefault("tp_getset", 'NULL')
        else:
            self.slots.setdefault("tp_getset", 'NULL')


        ## generate the destructor
        tp_dealloc_function_name = "_wrap_%s__tp_dealloc" % (self.pystruct,)
        if self.decref_method is None:
            delete_code = "delete tmp;"
        else:
            delete_code = ("if (tmp)\n        tmp->%s()"
                           % (self.decref_method,))
        code_sink.writeln('''
static void
%s(%s *self)
{
    %s *tmp = self->obj;
    self->obj = NULL;
    %s;
    PyObject_DEL(self);
}
''' % (tp_dealloc_function_name, self.pystruct, self.name, delete_code))
        code_sink.writeln()


        ## generate the type structure
        self.slots.setdefault("tp_basicsize",
                              "sizeof(%s)" % (self.pystruct,))
        self.slots.setdefault("tp_dealloc", tp_dealloc_function_name )
        for slot in ["tp_getattr", "tp_setattr", "tp_compare", "tp_repr",
                     "tp_as_number", "tp_as_sequence", "tp_as_mapping",
                     "tp_hash", "tp_call", "tp_str", "tp_getattro", "tp_setattro",
                     "tp_as_buffer", "tp_traverse", "tp_clear", "tp_richcompare",
                     "tp_iter", "tp_iternext", "tp_descr_get",
                     "tp_descr_set", "tp_is_gc"]:
            self.slots.setdefault(slot, "NULL")

        self.slots.setdefault("tp_dictoffset", "0")
        self.slots.setdefault("tp_init", (constructor is None and "NULL"
                                          or constructor))
        self.slots.setdefault("tp_alloc", "PyType_GenericAlloc")
        self.slots.setdefault("tp_new", "PyType_GenericNew")
        self.slots.setdefault("tp_free", "_PyObject_Del")
        self.slots.setdefault("tp_methods", "%s_methods" % (self.name,))
        self.slots.setdefault("tp_weaklistoffset", "0")
        self.slots.setdefault("tp_flags", "Py_TPFLAGS_DEFAULT")
        self.slots.setdefault("tp_doc", (docstring is None and 'NULL'
                                         or "\"%s\"" % (docstring,)))
        dict_ = dict(self.slots)
        dict_.setdefault("typestruct", self.pytypestruct)
        dict_.setdefault("classname", self.name)
        
        code_sink.writeln(self.TYPE_TMPL % dict_)



class CppClassParameter(Parameter):
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
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name], self.name)
        wrapper.call_params.append(
            '*((%s *) %s)->obj' % (self.cpp_class.pystruct, name))


class CppClassRefParameter(Parameter):
    "Class& handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_INOUT]
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, CppClass)

        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', self.name)

        if self.direction == Parameter.DIRECTION_IN:
            wrapper.parse_params.add_parameter(
                'O!', ['&'+self.cpp_class.pytypestruct, '&'+name], self.name)
            wrapper.call_params.append('*%s->obj' % (name,))

        elif self.direction == Parameter.DIRECTION_OUT:
            wrapper.before_call.write_code(
                "%s = PyObject_New(%s, %s);" %
                (name, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
            wrapper.before_call.write_code(
                "%s->obj = new %s;" % (name, self.cpp_class.name))
            wrapper.call_params.append('*%s->obj' % (name,))
            wrapper.build_params.add_parameter("N", [name])

        ## well, personally I think inout here doesn't make much sense
        ## (it's just plain confusing), but might as well support it..
        elif self.direction == Parameter.DIRECTION_INOUT:
            wrapper.parse_params.add_parameter(
                'O!', ['&'+self.cpp_class.pytypestruct, '&'+name], self.name)
            wrapper.call_params.append(
                '*%s->obj' % (self.cpp_class.pystruct, name))
            wrapper.build_params.add_parameter("O", [name])


class CppClassReturnValue(ReturnValue):
    "Class return handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance

    def get_c_error_return(self): # only used in reverse wrappers
        return "return %s();" % (self.cpp_class.name,)

    def convert_c_to_python(self, wrapper):
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        wrapper.after_call.write_code(
            "%s = PyObject_New(%s, %s);" %
            (py_name, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        wrapper.after_call.write_code(
            "%s->obj = new %s(retval);" % (py_name, self.cpp_class.name))
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)


class CppClassPtrParameter(Parameter):
    "Class* handlers"
    CTYPES = []
    cpp_class = CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    SUPPORTS_TRANSFORMATIONS = True

    def __init__(self, ctype, name, transfer_ownership):
        super(CppClassPtrParameter, self).__init__(
            ctype, name, direction=Parameter.DIRECTION_IN)
        self.transfer_ownership = transfer_ownership
        
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, CppClass)
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', self.name)
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

    def __init__(self, ctype, caller_owns_return):
        super(CppClassPtrReturnValue, self).__init__(ctype)
        self.caller_owns_return = caller_owns_return

    def get_c_error_return(self): # only used in reverse wrappers
        return "return %s();" % (self.cpp_class.name,)

    def convert_c_to_python(self, wrapper):
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        wrapper.after_call.write_code(
            "%s = PyObject_New(%s, %s);" %
            (py_name, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        
        value = self.transformation.untransform(
            self, wrapper.declarations, wrapper.after_call, 'retval')
        
        if self.caller_owns_return:
            wrapper.after_call.write_code("%s->obj = %s;" % (py_name, value))
        else:
            if self.cpp_class.incref_method is None:
                ## The PyObject creates its own copy
                wrapper.after_call.write_code(
                    "%s->obj = new %s(*%s);"
                    % (py_name, self.cpp_class.name, value))
            else:
                ## The PyObject gets a new reference to the same obj
                wrapper.after_call.write_code(
                    "%s->%s();" % (value, self.cpp_class.incref_method))
                wrapper.after_call.write_code("%s->obj = %s;" % (py_name, value))
                
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)


