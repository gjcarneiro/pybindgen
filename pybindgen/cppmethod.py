"""
Wrap C++ class methods and constructods.
"""

import warnings
from copy import copy

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase, \
    join_ctype_and_name, CodeGenerationError, ReturnValue
from typehandlers import codesink
import overloading
import settings
import utils


class CppMethod(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C++ class method
    """

    def __init__(self, method_name, return_value, parameters, is_static=False,
                 template_parameters=(), is_virtual=False, is_const=False,
                 unblock_threads=None, is_pure_virtual=False,
                 custom_template_method_name=None, visibility='public',
                 custom_name=None):
        """
        Create an object the generates code to wrap a C++ class method.

        @param return_value: the method return value
        @type  return_value: L{ReturnValue}

        @param method_name: name of the method

        @param parameters: the method parameters
        @type parameters: list of L{Parameter}

        @param is_static: whether it is a static method

        @param template_parameters: optional list of template parameters needed to invoke the method
        @type template_parameters: list of strings, each element a template parameter expression

        @param is_virtual: whether the method is virtual (pure or not)

        @param is_const: whether the method has a const modifier on it

        @param unblock_threads: whether to release the Python GIL
        around the method call or not.  If None or omitted, use global
        settings.  Releasing the GIL has a small performance penalty,
        but is recommended if the method is expected to take
        considerable time to complete, because otherwise no other
        Python thread is allowed to run until the method completes.

        @param is_pure_virtual: whether the method is defined as "pure
        virtual", i.e. virtual method with no default implementation
        in the class being wrapped.

        @param custom_name: alternate name to give to
        the method, in python side.

        @param visibility: visibility of the method within the C++ class
        @type visibility: a string (allowed values are 'public', 'protected', 'private')
        """

        ## backward compatibility check
        if isinstance(return_value, str) and isinstance(method_name, ReturnValue):
            warnings.warn("CppMethod has changed API; see the API documentation (but trying to correct...)",
                          DeprecationWarning, stacklevel=2)
            method_name, return_value = return_value, method_name

        if return_value is None:
            return_value = ReturnValue.new('void')

        if unblock_threads is None:
            unblock_threads = settings.unblock_threads
        super(CppMethod, self).__init__(
            return_value, parameters,
            "return NULL;", "return NULL;",
            unblock_threads=unblock_threads)
        assert visibility in ['public', 'protected', 'private']
        self.visibility = visibility
        self.method_name = method_name
        self.is_static = is_static
        self.is_virtual = is_virtual
        self.is_pure_virtual = is_pure_virtual
        self.is_const = is_const
        self.template_parameters = template_parameters

        self.custom_name = (custom_name or custom_template_method_name)

        self._class = None
        self.docstring = None
        self.wrapper_base_name = None
        self.wrapper_actual_name = None
        self.static_decl = True

    def set_custom_name(self, custom_name):
        if custom_name is None:
            self.mangled_name = utils.get_mangled_name(self.method_name, self.template_parameters)
        else:
            self.mangled_name = custom_name

    custom_name = property(None, set_custom_name)

    def clone(self):
        """Creates a semi-deep copy of this method wrapper.  The returned
        method wrapper clone contains copies of all parameters, so
        they can be modified at will.
        """
        meth = CppMethod(self.return_value,
                         self.method_name,
                         [copy(param) for param in self.parameters],
                         is_static=self.is_static,
                         template_parameters=self.template_parameters,
                         is_virtual=self.is_virtual,
                         is_const=self.is_const)
        meth._class = self._class
        meth.docstring = self.docstring
        meth.wrapper_base_name = self.wrapper_base_name
        meth.wrapper_actual_name = self.wrapper_actual_name
        return meth

    def set_class(self, class_):
        """set the class object this method belongs to"""
        self._class = class_
        self.wrapper_base_name = "_wrap_%s_%s" % (
            class_.pystruct, self.mangled_name)
    def get_class(self):
        """get the class object this method belongs to"""
        return self._class
    class_ = property(get_class, set_class)

    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
        if class_ is None:
            class_ = self._class
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
            if self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
                self.before_call.write_code(
                    '%s retval = %s(%s);' %
                    (self.return_value.ctype, method, ", ".join(self.call_params)))
            else:
                self.before_call.write_code(
                    'retval = %s(%s);' %
                    (method, ", ".join(self.call_params)))

    def _before_return_hook(self):
        """hook that post-processes parameters and check for custodian=<n>
        CppClass parameters"""
        cppclass.implement_parameter_custodians(self)

    def get_wrapper_signature(self, wrapper_name, extra_wrapper_params=()):
        flags = self.get_py_method_def_flags()

        retline = "PyObject *"
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
                line = ("%s(%s *%s, PyObject *args, PyObject *kwargs%s)"
                            % (wrapper_name, self.class_.pystruct, _self_name, extra))
            else:
                assert not extra_wrapper_params, \
                    "extra_wrapper_params can only be used with"\
                    " full varargs/kwargs wrappers"
                line = (
                    "%s(%s *%s, PyObject *args)"
                    % (wrapper_name, self.class_.pystruct, _self_name))
        else:
            assert not extra_wrapper_params, \
                "extra_wrapper_params can only be used with full varargs/kwargs wrappers"
            if 'METH_STATIC' in flags:
                line = ("%s(void)" % (wrapper_name,))
            else:
                line = ("%s(%s *%s)" % (wrapper_name, self.class_.pystruct, _self_name))
        return retline, line

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

        retline, line = self.get_wrapper_signature(self.wrapper_actual_name, extra_wrapper_params)
        if self.static_decl:
            retline = 'static ' + retline
        code_sink.writeln(retline)
        code_sink.writeln(line)
        
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

    def __init__(self, parameters, unblock_threads=None, visibility='public'):
        """
        parameters -- the constructor parameters
        """
        if unblock_threads is None:
            unblock_threads = settings.unblock_threads
        super(CppConstructor, self).__init__(
            None, parameters,
            "return -1;", "return -1;",
            force_parse=ForwardWrapperBase.PARSE_TUPLE_AND_KEYWORDS,
            unblock_threads=unblock_threads)
        assert visibility in ['public', 'protected', 'private']
        self.visibility = visibility
        self.wrapper_base_name = None
        self.wrapper_actual_name = None
        self._class = None

    def clone(self):
        """Creates a semi-deep copy of this constructor wrapper.  The returned
        constructor wrapper clone contains copies of all parameters, so
        they can be modified at will.
        """
        meth = type(self)([copy(param) for param in self.parameters])
        meth._class = self._class
        meth.wrapper_base_name = self.wrapper_base_name
        meth.wrapper_actual_name = self.wrapper_actual_name
        return meth

    def set_class(self, class_):
        "Set the class wrapper object (CppClass)"
        self._class = class_
        self.wrapper_base_name = "_wrap_%s__tp_init" % (
            class_.pystruct,)
    def get_class(self):
        "Get the class wrapper object (CppClass)"
        return self._class
    class_ = property(get_class, set_class)
    
    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        if class_ is None:
            class_ = self._class
        #assert isinstance(class_, CppClass)
        if class_.helper_class is None:
            class_.write_create_instance(self.before_call, "self->obj", ", ".join(self.call_params))
        else:
            ## We should only create a helper class instance when
            ## being called from a user python subclass.
            self.before_call.write_code("if (self->ob_type != &%s)" % class_.pytypestruct)
            self.before_call.write_code("{")
            self.before_call.indent()

            class_.write_create_instance(self.before_call, "self->obj", ", ".join(self.call_params),
                                         class_.helper_class.name)
            self.before_call.write_code('((%s*) self->obj)->set_pyobj((PyObject *)self);'
                                        % class_.helper_class.name)

            self.before_call.unindent()
            self.before_call.write_code("} else {")
            self.before_call.indent()

            try:
                class_.get_construct_name()
            except CodeGenerationError:
                self.before_call.write_code('PyErr_SetString(PyExc_TypeError, "class \'%s\' '
                                            'cannot be constructed");' % class_.name)
                self.before_call.write_code('return -1;')
            else:
                class_.write_create_instance(self.before_call, "self->obj", ", ".join(self.call_params))

            self.before_call.unindent()
            self.before_call.write_code("}")

    def _before_return_hook(self):
        "hook that post-processes parameters and check for custodian=<n> CppClass parameters"
        cppclass.implement_parameter_custodians(self)

    def generate(self, code_sink, wrapper_name=None, extra_wrapper_params=()):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        class_ -- the c++ class wrapper the method belongs to

        Returns the wrapper function name.
        """
        if self.visibility == 'private':
            raise CodeGenerationError("private constructor")
        elif self.visibility == 'protected':
            if self._class.helper_class is None:
                raise CodeGenerationError("protected constructor and no helper class")

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


class CppFunctionAsConstructor(CppConstructor):
    """
    Class that generates a wrapper to a C/C++ function that appears as a contructor.
    """
    def __init__(self, c_function_name, parameters, unblock_threads=None):
        """
        @param c_function_name: name of the C/C++ function; it is
        implied that this function returns a pointer to the a class
        instance with caller_owns_return semantics.

        @param parameters: the function/constructor parameters
        @type parameters: list of L{Parameter}

        """
        if unblock_threads is None:
            unblock_threads = settings.unblock_threads
        super(CppFunctionAsConstructor, self).__init__(parameters)
        self.c_function_name = c_function_name

    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        if class_ is None:
            class_ = self._class
        #assert isinstance(class_, CppClass)
        assert class_.helper_class is None
        self.before_call.write_code("self->obj = %s(%s);" %
                                    (self.c_function_name, ", ".join(self.call_params)))


class CppOverloadedConstructor(overloading.OverloadedWrapper):
    "Support class for overloaded constructors"
    RETURN_TYPE = 'int'
    ERROR_RETURN = 'return -1;'


class CppNoConstructor(ForwardWrapperBase):
    """

    Class that generates a constructor that raises an exception saying
    that the class has no constructor.

    """

    def __init__(self, reason):
        """
        reason -- string indicating reason why the class cannot be constructed.
        """
        super(CppNoConstructor, self).__init__(
            None, [],
            "return -1;", "return -1;")
        self.reason = reason

    def generate_call(self):
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
            class_.pystruct,)
        code_sink.writeln("static int")
        code_sink.writeln("%s(void)" % wrapper_function_name)
        code_sink.writeln('{')
        code_sink.indent()
        code_sink.writeln('PyErr_SetString(PyExc_TypeError, "class \'%s\' '
                          'cannot be constructed (%s)");' % (class_.name, self.reason))
        code_sink.writeln('return -1;')
        code_sink.unindent()
        code_sink.writeln('}')

        return wrapper_function_name



class CppVirtualMethodParentCaller(CppMethod):
    """
    Class that generates a wrapper that calls a virtual method default
    implementation in a parent base class.
    """

    def __init__(self, method, unblock_threads=None):
        """
        """
        super(CppVirtualMethodParentCaller, self).__init__(
            method.method_name, method.return_value, method.parameters, unblock_threads=unblock_threads)
        self._helper_class = None
        self.static_decl = False
        self.method = method

    def set_class(self, class_):
        "Set the class wrapper object (CppClass)"
        self._class = class_

    def set_helper_class(self, helper_class):
        "Set the C++ helper class, which is used for overriding virtual methods"
        self._helper_class = helper_class
        self.wrapper_base_name = "%s::_wrap_%s" % (self._helper_class.name, self.method_name)
    def get_helper_class(self):
        "Get the C++ helper class, which is used for overriding virtual methods"
        return self._helper_class
    helper_class = property(get_helper_class, set_helper_class)

    def generate_declaration(self, code_sink, extra_wrapper_parameters=()):
        ## We need to fake generate the code (and throw away the
        ## result) only in order to obtain correct method signature.
        tmp_sink = codesink.NullCodeSink()
        self.generate_body(tmp_sink, gen_call_params=[self.class_])

        if self.overload_index is None:
            overload_str = ''
        else:
            overload_str = '__%i' % self.overload_index

        retline, line = self.get_wrapper_signature(
            '_wrap_'+self.method_name+overload_str, extra_wrapper_parameters)
        code_sink.writeln(' '.join(['static', retline, line]) + ';')
        self.reset_code_generation_state()

    def generate_parent_caller_method(self, code_sink):
        ## generate a '%s__parent_caller' method (static methods
        ## cannot "conquer" 'protected' access type, only regular
        ## instance methods).
        code_sink.writeln('inline %s %s__parent_caller(%s)' % (
                self.return_value.ctype,
                self.method_name,
                ', '.join([join_ctype_and_name(param.ctype, param.name) for param in self.parameters])
                ))
        if self.return_value.ctype == 'void':
            code_sink.writeln('{ %s::%s(%s); }' % (self._class.full_name, self.method_name,
                                                   ', '.join([param.name for param in self.parameters])))
        else:
            code_sink.writeln('{ return %s::%s(%s); }' % (self._class.full_name, self.method_name,
                                                          ', '.join([param.name for param in self.parameters])))        


    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
        if class_ is None:
            class_ = self._class
        method = 'reinterpret_cast< %s* >(self->obj)->%s__parent_caller' % (self._helper_class.name, self.method_name)
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' %
                (method, ", ".join(self.call_params)))
        else:
            if self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
                self.before_call.write_code(
                    '%s retval = %s(%s);' %
                    (self.return_value.ctype, method, ", ".join(self.call_params)))
            else:
                self.before_call.write_code(
                    'retval = %s(%s);' %
                    (method, ", ".join(self.call_params)))

    def get_py_method_def(self, method_name=None):
        "Get the PyMethodDef entry suitable for this method"

        assert self.wrapper_actual_name == self.wrapper_base_name, \
            "wrapper_actual_name=%r but wrapper_base_name=%r" % \
            (self.wrapper_actual_name, self.wrapper_base_name)
        assert self._helper_class is not None
        if method_name is None:
            method_name = self.method_name
        flags = self.get_py_method_def_flags()
        return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
               ('_'+method_name,
                self.wrapper_actual_name,#'::'.join((self._helper_class.name, self.wrapper_actual_name)),
                '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))

    def clone(self):
        """
        Creates a semi-deep copy of this method wrapper.  The returned
        method wrapper clone contains copies of all parameters, so
        they can be modified at will.
        """
        meth = CppVirtualMethodParentCaller(
            self.return_value,
            self.method_name,
            [copy(param) for param in self.parameters])
        meth._class = self._class
        meth._helper_class = self._helper_class
        meth.docstring = self.docstring
        meth.wrapper_base_name = self.wrapper_base_name
        meth.wrapper_actual_name = self.wrapper_actual_name
        return meth


class CppVirtualMethodProxy(ReverseWrapperBase):
    """
    Class that generates a proxy virtual method that calls a similarly named python method.
    """

    def __init__(self, method):
        """
        xxx
        """
        super(CppVirtualMethodProxy, self).__init__(method.return_value, method.parameters)
        self.method_name = method.method_name
        self.method = method
        self._class = None
        self._helper_class = None


    def set_class(self, class_):
        "Set the class wrapper object (CppClass)"
        assert isinstance(class_, cppclass.CppClass)
        self._class = class_
    def get_class(self):
        "Get the class wrapper object (CppClass)"
        return self._class
    class_ = property(get_class, set_class)


    def set_helper_class(self, helper_class):
        "Set the C++ helper class, which is used for overriding virtual methods"
        self._helper_class = helper_class
        self.wrapper_base_name = "_wrap_%s" % self.method_name
    def get_helper_class(self):
        "Get the C++ helper class, which is used for overriding virtual methods"
        return self._helper_class
    helper_class = property(get_helper_class, set_helper_class)


    def generate_python_call(self):
        """code to call the python method"""
        params = ['m_pyself', '(char *) "_%s"' % self.method_name]
        build_params = self.build_params.get_parameters()
        if build_params[0][0] == '"':
            build_params[0] = '(char *) ' + build_params[0]
        params.extend(build_params)
        self.before_call.write_code('py_retval = PyObject_CallMethod(%s);'
                                    % (', '.join(params),))
        self.before_call.write_error_check('py_retval == NULL')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')

    def generate_declaration(self, code_sink):
        if self.method.is_const:
            decl_post_modifiers = ' const'
        else:
            decl_post_modifiers = ''

        params_list = ', '.join([join_ctype_and_name(param.ctype, param.name)
                                 for param in self.parameters])
        code_sink.writeln("virtual %s %s(%s)%s;" %
                          (self.return_value.ctype, self.method_name, params_list,
                           decl_post_modifiers))


    def generate(self, code_sink):
        """generates the proxy virtual method"""
        if self.method.is_const:
            decl_post_modifiers = ['const']
        else:
            decl_post_modifiers = []

        ## if the python subclass doesn't define a virtual method,
        ## just chain to parent class and don't do anything else
        call_params = ', '.join([param.name for param in self.parameters])
        self.before_call.write_code(
            r'if (!PyObject_HasAttrString(m_pyself, "_%s")) {' % self.method_name)
        if self.return_value.ctype == 'void':
            if not (self.method.is_pure_virtual or self.method.visibility == 'private'):
                self.before_call.write_code(r'    %s::%s(%s);'
                                            % (self._class.full_name, self.method_name, call_params))
            self.before_call.write_code(r'    return;')
        else:
            if self.method.is_pure_virtual or self.method.visibility == 'private':
                if isinstance(self.return_value, cppclass.CppClassReturnValue) \
                        and self.return_value.cpp_class.has_trivial_constructor:
                    pass
                else:
                    self.set_error_return('''
PyErr_Print();
Py_FatalError("Error detected, but parent virtual is pure virtual or private virtual, "
              "and return is a class without trival constructor");''')
            else:
                self.set_error_return("PyErr_Print();\nreturn %s::%s(%s);"
                                      % (self._class.full_name, self.method_name, call_params))
            self.before_call.indent()
            self.before_call.write_code(self.error_return)
            self.before_call.unindent()
        self.before_call.write_code('}')

        ## Set "m_pyself->obj = this" around virtual method call invocation
        self_obj_before = self.declarations.declare_variable(
            '%s*' % self._class.full_name, 'self_obj_before')
        self.before_call.write_code("%s = reinterpret_cast< %s* >(m_pyself)->obj;" %
                                    (self_obj_before, self._class.pystruct))
        if self.method.is_const:
            this_expression = ("const_cast< %s* >((const %s*) this)" %
                               (self._class.full_name, self._class.full_name))
        else:
            this_expression = "(%s*) this" % (self._class.full_name)
        self.before_call.write_code("reinterpret_cast< %s* >(m_pyself)->obj = %s;" %
                                    (self._class.pystruct, this_expression))
        self.before_call.add_cleanup_code("reinterpret_cast< %s* >(m_pyself)->obj = %s;" %
                                          (self._class.pystruct, self_obj_before))
        
        super(CppVirtualMethodProxy, self).generate(
            code_sink, '::'.join((self._helper_class.name, self.method_name)),
            decl_modifiers=[],
            decl_post_modifiers=decl_post_modifiers)



class CustomCppMethodWrapper(CppMethod):
    """
    Adds a custom method wrapper.  The custom wrapper must be
    prepared to support overloading, i.e. it must have an additional
    "PyObject **return_exception" parameter, and raised exceptions
    must be returned by this parameter.
    """

    NEEDS_OVERLOADING_INTERFACE = True

    def __init__(self, method_name, wrapper_name, wrapper_body,
                 flags=('METH_VARARGS', 'METH_KEYWORDS')):
        super(CustomCppMethodWrapper, self).__init__(method_name, ReturnValue.new('void'), [])
        self.wrapper_base_name = wrapper_name
        self.wrapper_actual_name = wrapper_name
        self.meth_flags = list(flags)
        self.wrapper_body = wrapper_body

    def generate(self, code_sink, dummy_wrapper_name=None, extra_wrapper_params=()):
        assert extra_wrapper_params == ["PyObject **return_exception"]
        code_sink.writeln(self.wrapper_body)

    def generate_call(self, *args, **kwargs):
        pass



class CustomCppConstructorWrapper(CppConstructor):
    """
    Adds a custom constructor wrapper.  The custom wrapper must be
    prepared to support overloading, i.e. it must have an additional
    "PyObject **return_exception" parameter, and raised exceptions
    must be returned by this parameter.
    """

    NEEDS_OVERLOADING_INTERFACE = True

    def __init__(self, wrapper_name, wrapper_body):
        super(CustomCppConstructorWrapper, self).__init__([])
        self.wrapper_base_name = wrapper_name
        self.wrapper_actual_name = wrapper_name
        self.wrapper_body = wrapper_body

    def generate(self, code_sink, dummy_wrapper_name=None, extra_wrapper_params=()):
        assert extra_wrapper_params == ["PyObject **return_exception"]
        code_sink.writeln(self.wrapper_body)

    def generate_call(self, *args, **kwargs):
        pass


import cppclass
