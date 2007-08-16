"""
Wrap C++ class methods and constructods.
"""

from typehandlers.base import ForwardWrapperBase
from typehandlers import codesink
import overloading



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
        self._class = None
        self.docstring = None
        self.wrapper_base_name = None
        self.wrapper_actual_name = None


    def set_class(self, class_):
        self._class = class_
        self.wrapper_base_name = "_wrap_%s_%s" % (
            class_.name, self.method_name)
    def get_class(self):
        return self._class
    class_ = property(get_class, set_class)

    
    def generate_call(self, class_):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
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
            _self_name = 'dummy PYBINDGEN_UNUSED'
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
                    "extra_wrapper_params can only be used with full varargs/kwargs wrappers"
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
        flags = super(CppMethod, self).get_py_method_def_flags()
        if self.is_static:
            flags.append('METH_STATIC')
        return flags

    def get_py_method_def(self, method_name):
        flags = self.get_py_method_def_flags()
        return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
               (method_name, self.wrapper_actual_name, '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))
    

class CppOverloadedMethod(overloading.OverloadedWrapper):
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
        self._class = class_
        self.wrapper_base_name = "_wrap_%s__tp_init" % (
            class_.name,)
    def get_class(self):
        return self._class
    class_ = property(get_class, set_class)
    
    def generate_call(self, class_):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
        self.before_call.write_code(
            'self->obj = new %s(%s);' %
            (class_.name, ", ".join(self.call_params)))

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

