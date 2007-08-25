"""
Wrap C++ class methods and constructods.
"""

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase
from typehandlers import codesink
import overloading



class CppMethod(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C++ class method
    """

    def __init__(self, return_value, method_name, parameters, is_static=False,
                 template_parameters=(), is_virtual=False, is_const=False):
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
        self.is_virtual = is_virtual
        self.is_const = is_const
        self.template_parameters = template_parameters

        self._class = None
        self.docstring = None
        self.wrapper_base_name = None
        self.wrapper_actual_name = None


    def set_class(self, class_):
        """set the class object this method belongs to"""
        self._class = class_
        self.wrapper_base_name = "_wrap_%s_%s" % (
            class_.name, self.method_name)
    def get_class(self):
        """get the class object this method belongs to"""
        return self._class
    class_ = property(get_class, set_class)

    
    def generate_call(self, class_):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
        if self.template_parameters:
            template_params = '< %s >' % ', '.join(self.template_parameters)
        else:
            template_params = ''
        if self.is_static:
            method = '%s::%s%s' % (class_.full_name, self.method_name, template_params)
        else:
            method = 'self->obj->%s%s' % (self.method_name, template_params)
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' %
                (method, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = %s(%s);' %
                (method, ", ".join(self.call_params)))


    def generate(self, code_sink, wrapper_name=None, extra_wrapper_params=()):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        method_name -- actual name the method will get
        extra_wrapper_params -- extra parameters the wrapper function should receive

        Returns the corresponding PyMethodDef entry string.
        """
        class_ = self.class_
        #assert isinstance(class_, CppClass)
        tmp_sink = codesink.MemoryCodeSink()

        self.generate_body(tmp_sink, gen_call_params=[class_])

        if wrapper_name is None:
            self.wrapper_actual_name = self.wrapper_base_name
        else:
            self.wrapper_actual_name = wrapper_name

        flags = self.get_py_method_def_flags()

        code_sink.writeln("static PyObject *")
        if 'METH_STATIC' in flags:
            _self_name = 'PYBINDGEN_UNUSED(dummy)'
        else:
            _self_name = 'self'

        if extra_wrapper_params:
            extra = ', '.join([''] + list(extra_wrapper_params))
        else:
            extra = ''
        if 'METH_VARARGS' in flags:
            if 'METH_KEYWORDS' in flags:
                code_sink.writeln(
                    "%s(%s *%s, PyObject *args, PyObject *kwargs%s)"
                    % (self.wrapper_actual_name, class_.pystruct, _self_name, extra))
            else:
                assert not extra_wrapper_params, \
                    "extra_wrapper_params can only be used with"\
                    " full varargs/kwargs wrappers"
                code_sink.writeln(
                    "%s(%s *%s, PyObject *args)"
                    % (self.wrapper_actual_name, class_.pystruct, _self_name))
        else:
            assert not extra_wrapper_params, \
                "extra_wrapper_params can only be used with full varargs/kwargs wrappers"
            if 'METH_STATIC' in flags:
                code_sink.writeln("%s(void)" % (self.wrapper_actual_name,))
            else:
                code_sink.writeln(
                    "%s(%s *%s)"
                    % (self.wrapper_actual_name, class_.pystruct, _self_name))
                
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')

    def get_py_method_def_flags(self):
        "Get the PyMethodDef flags suitable for this method"
        flags = super(CppMethod, self).get_py_method_def_flags()
        if self.is_static:
            flags.append('METH_STATIC')
        return flags

    def get_py_method_def(self, method_name):
        "Get the PyMethodDef entry suitable for this method"
        flags = self.get_py_method_def_flags()
        return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
               (method_name, self.wrapper_actual_name, '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))
    

class CppOverloadedMethod(overloading.OverloadedWrapper):
    "Support class for overloaded methods"
    RETURN_TYPE = 'PyObject *'
    ERROR_RETURN = 'return NULL;'


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
        self.wrapper_base_name = None
        self.wrapper_actual_name = None
        self._class = None


    def set_class(self, class_):
        "Set the class wrapper object (CppClass)"
        self._class = class_
        self.wrapper_base_name = "_wrap_%s__tp_init" % (
            class_.name,)
    def get_class(self):
        "Get the class wrapper object (CppClass)"
        return self._class
    class_ = property(get_class, set_class)
    
    def generate_call(self, class_):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
        if class_.helper_class is None:
            class_name = class_.full_name
            call_params = self.call_params
        else:
            class_name = class_.helper_class.name
            call_params = ['(PyObject *)self'] + self.call_params
        #self.before_call.write_code(r'fprintf(stderr, "creating a %s class instance\n");' % class_name)
        self.before_call.write_code(
            'self->obj = new %s(%s);' %
            (class_name, ", ".join(call_params)))

    def generate(self, code_sink, wrapper_name=None, extra_wrapper_params=()):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        class_ -- the c++ class wrapper the method belongs to

        Returns the wrapper function name.
        """
        #assert isinstance(class_, CppClass)
        tmp_sink = codesink.MemoryCodeSink()

        assert self._class is not None
        self.generate_body(tmp_sink, gen_call_params=[self._class])

        assert ((self.parse_params.get_parameters() == ['""'])
                or self.parse_params.get_keywords() is not None), \
               ("something went wrong with the type handlers;"
                " constructors need parameter names, "
                "yet no names were given for the class %s constructor"
                % self._class.name)

        if wrapper_name is None:
            self.wrapper_actual_name = self.wrapper_base_name
        else:
            self.wrapper_actual_name = wrapper_name

        if extra_wrapper_params:
            extra = ', '.join([''] + list(extra_wrapper_params))
        else:
            extra = ''

        code_sink.writeln("static int")
        code_sink.writeln(
            "%s(%s *self, PyObject *args, PyObject *kwargs%s)"
            % (self.wrapper_actual_name, self._class.pystruct, extra))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.writeln('return 0;')
        code_sink.unindent()
        code_sink.writeln('}')



class CppOverloadedConstructor(overloading.OverloadedWrapper):
    "Support class for overloaded constructors"
    RETURN_TYPE = 'int'
    ERROR_RETURN = 'return -1;'


class CppNoConstructor(ForwardWrapperBase):
    """

    Class that generates a constructor that raises an exception saying
    that the class has no constructor.

    """

    def __init__(self):
        """
        Constructor.
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
        #assert isinstance(class_, CppClass)

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



class CppVirtualMethodParentCaller(CppMethod):
    """
    Class that generates a wrapper that calls a virtual method default
    implementation in a parent base class.
    """

    def __init__(self, return_value, method_name, parameters):
        """
        return_value -- the method return value
        method_name -- name of the method
        parameters -- the method parameters
        """
        super(CppVirtualMethodParentCaller, self).__init__(
            return_value, method_name, parameters)
        self._helper_class = None

    def set_class(self, class_):
        "Set the class wrapper object (CppClass)"
        self._class = class_

    def set_helper_class(self, helper_class):
        "Set the C++ helper class, which is used for overriding virtual methods"
        self._helper_class = helper_class
        self.wrapper_base_name = "_wrap_%s" % self.method_name
    def get_helper_class(self):
        "Get the C++ helper class, which is used for overriding virtual methods"
        return self._helper_class
    helper_class = property(get_helper_class, set_helper_class)

    def generate_call(self, class_):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
        method = 'self->obj->%s::%s' % (class_.full_name, self.method_name)
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' %
                (method, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = %s(%s);' %
                (method, ", ".join(self.call_params)))

    def get_py_method_def(self, method_name=None):
        "Get the PyMethodDef entry suitable for this method"

        assert self.wrapper_actual_name == self.wrapper_base_name
        assert self._helper_class is not None
        if method_name is None:
            method_name = self.method_name
        flags = self.get_py_method_def_flags()
        return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
               ('_'+method_name,
                '::'.join((self._helper_class.name, self.wrapper_actual_name)),
                '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))


class CppVirtualMethodProxy(ReverseWrapperBase):
    """
    Class that generates a proxy virtual method that calls a similarly named python method.
    """

    def __init__(self, return_value, method_name, parameters, is_const=False):
        """
        return_value -- the method return value
        method_name -- name of the virtual method
        parameters -- the method parameters
        """
        super(CppVirtualMethodProxy, self).__init__(return_value, parameters)
        self.method_name = method_name
        self.is_const = is_const

    def generate_python_call(self):
        """code to call the python method"""
        params = ['m_pyself', '"_%s"' % self.method_name]
        params.extend(self.build_params.get_parameters())
        self.before_call.write_code('py_retval = PyObject_CallMethod(%s);'
                                    % (', '.join(params),))
        self.before_call.write_error_check('py_retval == NULL')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')

    def generate(self, code_sink):
        """generates the proxy virtual method"""
        if self.is_const:
            decl_post_modifiers=['const']
        else:
            decl_post_modifiers = []

        ## if the python subclass doesn't define a virtual method,
        ## just chain to parent class and don't do anything else
        call_params = ', '.join([param.name for param in self.parameters])
        self.before_call.write_code(
            r'if (!PyObject_HasAttrString(m_pyself, "_%s"))' % self.method_name)
        if self.return_value.ctype == 'void':
            self.before_call.write_code(r'    %s::%s(%s);'
                                        % (self.class_.full_name, self.method_name, call_params))
            self.before_call.write_code(r'    return;')
        else:
            self.before_call.write_code(r'    return %s::%s(%s);'
                                        % (self.class_.full_name, self.method_name, call_params))

        ## Set "m_pyself->obj = this" around virtual method call invocation
        self_obj_before = self.declarations.declare_variable(
            '%s*' % self.class_.full_name, 'self_obj_before')
        self.before_call.write_code("%s = reinterpret_cast<%s*>(m_pyself)->obj;" %
                                    (self_obj_before, self.class_.pystruct))
        if self.is_const:
            this_expression = ("const_cast<%s*>((const %s*) this)" %
                               (self.class_.full_name, self.class_.full_name))
        else:
            this_expression = "(%s*) this" % (self.class_.full_name)
        self.before_call.write_code("reinterpret_cast<%s*>(m_pyself)->obj = %s;" %
                                    (self.class_.pystruct, this_expression))
        self.before_call.add_cleanup_code("reinterpret_cast<%s*>(m_pyself)->obj = %s;" %
                                          (self.class_.pystruct, self_obj_before))
        
        super(CppVirtualMethodProxy, self).generate(
            code_sink, self.method_name, decl_modifiers=['virtual'],
            decl_post_modifiers=decl_post_modifiers)
