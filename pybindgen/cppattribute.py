"""
Wraps C++ class instance/static attributes.
"""

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase
from typehandlers import codesink
import settings



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
            value_type, [], "return NULL;", "return NULL;", no_c_retval=True)
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__get_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
        value_type.value = "self->obj->%s" % self.attribute_name

    def generate_call(self):
        "virtual method implementation; do not call"
        pass

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
            value_type, [], "return NULL;", "return NULL;", no_c_retval=True)
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__get_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
        value_type.value = "%s::%s" % (self.class_.name, self.attribute_name)

    def generate_call(self):
        "virtual method implementation; do not call"
        pass

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


class CppInstanceAttributeSetter(ReverseWrapperBase):
    '''
    A setter for a C++ instance attribute.
    '''
    def __init__(self, value_type, class_, attribute_name):
        """
        value_type -- a ReturnValue object handling the value type;
        class_ -- the class (CppClass object)
        attribute_name -- name of attribute
        """
        super(CppInstanceAttributeSetter, self).__init__(
            value_type, [], "return -1;")
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__set_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
        value_type.value = "self->obj->%s" % self.attribute_name

    def generate(self, code_sink):
        """
        code_sink -- a CodeSink instance that will receive the generated code
        """

        self.declarations.declare_variable('PyObject*', 'py_retval')
        self.before_call.write_code(
            'py_retval = Py_BuildValue("(O)", value);')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')
        self.return_value.convert_python_to_c(self)
        parse_tuple_params = ['py_retval']
        parse_tuple_params.extend(self.parse_params.get_parameters())
        self.before_call.write_error_check('!PyArg_ParseTuple(%s)' %
                                           (', '.join(parse_tuple_params),))
        ## cleanup and return
        self.after_call.write_cleanup()
        self.after_call.write_code('return 0;')

        ## now generate the function itself
        code_sink.writeln("static int %s(%s *self, PyObject *value)"
                          % (self.c_function_name, self.class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()

        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

        code_sink.unindent()
        code_sink.writeln('}')


class CppStaticAttributeSetter(ReverseWrapperBase):
    '''
    A setter for a C++ class static attribute.
    '''
    def __init__(self, value_type, class_, attribute_name):
        """
        value_type -- a ReturnValue object handling the value type;
        class_ -- the class (CppClass object)
        attribute_name -- name of attribute
        """
        super(CppStaticAttributeSetter, self).__init__(
            value_type, [], "return -1;")
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__set_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
        value_type.value =  "%s::%s" % (self.class_.name, self.attribute_name)

    def generate(self, code_sink):
        """
        code_sink -- a CodeSink instance that will receive the generated code
        """

        self.declarations.declare_variable('PyObject*', 'py_retval')
        self.before_call.write_code(
            'py_retval = Py_BuildValue("(O)", value);')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')
        self.return_value.convert_python_to_c(self)
        parse_tuple_params = ['py_retval']
        parse_tuple_params.extend(self.parse_params.get_parameters())
        self.before_call.write_error_check('!PyArg_ParseTuple(%s)' %
                                           (', '.join(parse_tuple_params),))
        ## cleanup and return
        self.after_call.write_cleanup()
        self.after_call.write_code('return 0;')

        ## now generate the function itself
        code_sink.writeln(("static int %s(%s *self PYBINDGEN_UNUSED, "
                           "PyObject *obj PYBINDGEN_UNUSED, PyObject *value)")
                          % (self.c_function_name, self.class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()

        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

        code_sink.unindent()
        code_sink.writeln('}')


class PyDescrGenerator(object):
    """
    Class that generates a Python descriptor type.
    """
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

