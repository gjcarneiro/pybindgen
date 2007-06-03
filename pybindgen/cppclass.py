"""
Wrap C++ classes and methods
"""

from typehandlers.base import ForwardWrapperBase, Parameter, ReturnValue
from typehandlers import codesink


class CppClassParameter(Parameter):
    CTYPES = []
    cpp_class = None # CppClass instance
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


class CppMethod(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C++ class method
    """

    def __init__(self, return_value, method_name, parameters):
        """
        return_value -- the method return value
        method_name -- name of the method
        parameters -- the method parameters
        """
        super(CppMethod, self).__init__(
            return_value, parameters,
            "return NULL;", "return NULL;")
        self.method_name = method_name

    
    def generate_call(self, class_):
        "virtual method implementation; do not call"
        assert isinstance(class_, CppClass)
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                'self->obj->%s(%s);' %
                (self.method_name, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = self->obj->%s(%s);' %
                (self.method_name, ", ".join(self.call_params)))


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

        code_sink.writeln("static PyObject *")
        code_sink.writeln(
            "%s(%s *self, PyObject *args, PyObject *kwargs)"
            % (wrapper_function_name, class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')

        flags = self.get_py_method_def_flags()
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
            "return -1;", "return -1;")
    
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


class CppClass(object):
    """
    A CppClass object takes care of generating the code for wrapping a C++ class
    """

    TYPE_TMPL = (
        'PyTypeObject Py%(typename)s_Type = {\n'
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
        '    (inquiry)%(tp_is_gc)s              /* tp_is_gc */\n'
        '};\n'
        )

    def __init__(self, name, parent=None):
        """Constructor
        name -- class name
        """
        self.name = name
        self.methods = [] # (name, wrapper) pairs
        self.constructors = [] # (name, wrapper) pairs
        self.slots = dict()
        self.pystruct = "Py%s" % (self.name,)
        self.pytypestruct = "Py%s_Type" % (self.name,)
        self.parent = parent
        assert parent is None or isinstance(parent, CppClass)

        ## register type handlers
        class ThisClassParameter(CppClassParameter):
            CTYPES = [name]
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

    def generate_forward_declarations(self, code_sink):
        """Generates forward declarations for the instance and type structures"""

        code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *obj;
} %s;
''' % (self.name, self.pystruct))

        code_sink.writeln()
        code_sink.writeln('extern PyTypeObject %s;' % (self.pytypestruct,))
        code_sink.writeln()
        

    def generate(self, code_sink, docstring=None):
        """Generates the class to a code sink"""

        ## generate the constructor, if any
        if self.constructors:
            code_sink.writeln()
            constructor = self.constructors[0].generate(code_sink, self)
            code_sink.writeln()
        else:
            constructor = None

        ## generate the method wrappers
        method_defs = []
        for meth_name, meth_wrapper in self.methods:
            code_sink.writeln()
            method_defs.append(meth_wrapper.generate(code_sink, self, meth_name))
            code_sink.writeln()

        ## generate the method table
        code_sink.writeln("static PyMethodDef %s_methods[] = {" % (self.name,))
        code_sink.indent()
        for methdef in method_defs:
            code_sink.writeln(methdef)
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")

        self.slots.setdefault("tp_basicsize",
                              "sizeof(%s)" % (self.pystruct,))
        self.slots.setdefault("tp_dealloc",
                              "_wrap_%s__tp_dealloc" % (self.name,))
        self.slots.setdefault("tp_getattr", "NULL")
        self.slots.setdefault("tp_setattr", "NULL")
        self.slots.setdefault("tp_compare", "NULL")
        self.slots.setdefault("tp_repr", "NULL")
        self.slots.setdefault("tp_as_number", "NULL")
        self.slots.setdefault("tp_as_sequence", "NULL")
        self.slots.setdefault("tp_as_mapping", "NULL")
        self.slots.setdefault("tp_hash", "NULL")
        self.slots.setdefault("tp_call", "NULL")
        self.slots.setdefault("tp_str", "NULL")
        self.slots.setdefault("tp_getattro", "NULL")
        self.slots.setdefault("tp_setattro", "NULL")
        self.slots.setdefault("tp_as_buffer", "NULL")
        self.slots.setdefault("tp_flags", "Py_TPFLAGS_DEFAULT")
        self.slots.setdefault("tp_doc", (docstring is None and 'NULL'
                                         or "\"%s\"" % (docstring,)))
        self.slots.setdefault("tp_traverse", "NULL")
        self.slots.setdefault("tp_clear", "NULL")
        self.slots.setdefault("tp_richcompare", "NULL")
        self.slots.setdefault("tp_weaklistoffset", "0")
        self.slots.setdefault("tp_iter", "NULL")
        self.slots.setdefault("tp_iternext", "NULL")
        self.slots.setdefault("tp_methods", "%s_methods" % (self.name,))
        self.slots.setdefault("tp_getset", "NULL")
        self.slots.setdefault("tp_descr_get", "NULL")
        self.slots.setdefault("tp_descr_set", "NULL")
        self.slots.setdefault("tp_dictoffset", "0")
        self.slots.setdefault("tp_init", (constructor is None and "NULL"
                                          or constructor))
        self.slots.setdefault("tp_alloc", "PyType_GenericAlloc")
        self.slots.setdefault("tp_new", "PyType_GenericNew")
        self.slots.setdefault("tp_free", "_PyObject_Del")
        self.slots.setdefault("tp_is_gc", "NULL")

        dict_ = dict(self.slots)
        dict_.setdefault("typename", self.name)
        dict_.setdefault("classname", self.name)

        code_sink.writeln('''
static void
%s(%s *self)
{
    delete self->obj;
    PyObject_DEL(self);
}
''' % (dict_['tp_dealloc'], self.pystruct))

        code_sink.writeln()
        code_sink.writeln(self.TYPE_TMPL % dict_)

