import warnings

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase, \
    Parameter, ReturnValue, TypeConfigurationError, NotSupportedError

import cppclass


###
### ------------ C++ class parameter type handlers ------------
###
class CppClassParameterBase(Parameter):
    "Base class for all C++ Class parameter handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False, default_value=None):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassParameterBase, self).__init__(
            ctype, name, direction, is_const, default_value)

        ## name of the PyFoo * variable used in parameter parsing
        self.py_name = None

        ## it True, this parameter is 'fake', and instead of being
        ## passed a parameter from python it is assumed to be the
        ## 'self' parameter of a method wrapper
        self.take_value_from_python_self = False


class CppClassReturnValueBase(ReturnValue):
    "Class return handlers -- base class"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance

    def __init__(self, ctype, is_const=False):
        super(CppClassReturnValueBase, self).__init__(ctype, is_const=is_const)
        ## name of the PyFoo * variable used in return value building
        self.py_name = None


class CppClassParameter(CppClassParameterBase):
    "Class handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, cppclass.CppClass)

        if self.take_value_from_python_self:
            self.py_name = 'self'
            wrapper.call_params.append(
                '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
        else:
            implicit_conversion_sources = self.cpp_class.get_all_implicit_conversions()
            if not implicit_conversion_sources:
                if self.default_value is not None:
                    self.cpp_class.get_construct_name() # raises an exception if the class cannot be constructed
                    self.py_name = wrapper.declarations.declare_variable(
                        self.cpp_class.pystruct+'*', self.name, 'NULL')
                    wrapper.parse_params.add_parameter(
                        'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name, optional=True)
                    wrapper.call_params.append(
                        '(%s ? (*((%s *) %s)->obj) : %s)' % (self.py_name, self.cpp_class.pystruct, self.py_name, self.default_value))
                else:
                    self.py_name = wrapper.declarations.declare_variable(
                        self.cpp_class.pystruct+'*', self.name)
                    wrapper.parse_params.add_parameter(
                        'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
                    wrapper.call_params.append(
                        '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
            else:
                if self.default_value is None:
                    self.py_name = wrapper.declarations.declare_variable(
                        'PyObject*', self.name)
                    tmp_value_variable = wrapper.declarations.declare_variable(
                        self.cpp_class.full_name, self.name)
                    wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name)
                else:
                    self.py_name = wrapper.declarations.declare_variable(
                        'PyObject*', self.name, 'NULL')
                    tmp_value_variable = wrapper.declarations.declare_variable(
                        self.cpp_class.full_name, self.name)
                    wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name, optional=True)

                if self.default_value is None:
                    wrapper.before_call.write_code("if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                   "    %s = *((%s *) %s)->obj;" %
                                                   (self.py_name, self.cpp_class.pytypestruct,
                                                    tmp_value_variable,
                                                    self.cpp_class.pystruct, self.py_name))
                else:
                    wrapper.before_call.write_code(
                        "if (%s == NULL) {\n"
                        "    %s = %s;" %
                        (self.py_name, tmp_value_variable, self.default_value))
                    wrapper.before_call.write_code(
                        "} else if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
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
        self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, self.py_name,
                                                                   "%s->obj" % self.py_name)

        wrapper.build_params.add_parameter("N", [self.py_name])


class CppClassRefParameter(CppClassParameterBase):
    "Class& handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_INOUT]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False,
                 default_value=None, default_value_type=None):
        """
        @param ctype: C type, normally 'MyClass*'
        @param name: parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassRefParameter, self).__init__(
            ctype, name, direction, is_const, default_value)
        self.default_value_type = default_value_type
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, cppclass.CppClass)

        if self.direction == Parameter.DIRECTION_IN:
            if self.take_value_from_python_self:
                self.py_name = 'self'
                wrapper.call_params.append(
                    '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
            else:
                implicit_conversion_sources = self.cpp_class.get_all_implicit_conversions()
                if not (implicit_conversion_sources and self.type_traits.target_is_const):
                    if self.default_value is not None:
                        self.py_name = wrapper.declarations.declare_variable(
                            self.cpp_class.pystruct+'*', self.name, 'NULL')

                        wrapper.parse_params.add_parameter(
                            'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name, optional=True)

                        if self.default_value_type is not None:
                            default_value_name = wrapper.declarations.declare_variable(
                                self.default_value_type, "%s_default" % self.name,
                                self.default_value)
                            wrapper.call_params.append(
                                '(%s ? (*((%s *) %s)->obj) : %s)' % (self.py_name, self.cpp_class.pystruct,
                                                                     self.py_name, default_value_name))
                        else:
                            self.cpp_class.get_construct_name() # raises an exception if the class cannot be constructed
                            wrapper.call_params.append(
                                '(%s ? (*((%s *) %s)->obj) : %s)' % (self.py_name, self.cpp_class.pystruct,
                                                                     self.py_name, self.default_value))
                    else:
                        self.py_name = wrapper.declarations.declare_variable(
                            self.cpp_class.pystruct+'*', self.name)
                        wrapper.parse_params.add_parameter(
                            'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
                        wrapper.call_params.append(
                            '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
                else:
                    if self.default_value is not None:
                        warnings.warn("with implicit conversions, default value "
                                      "in C++ class reference parameters is ignored.")
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
            self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, self.py_name,
                                                                       "%s->obj" % self.py_name)
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
            self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, self.py_name,
                                                                       "%s->obj" % self.py_name)
            wrapper.build_params.add_parameter("N", [self.py_name])
        else:
            ## out/inout case:
            ## the callee receives a "temporary wrapper", which loses
            ## the ->obj pointer after the python call; this is so
            ## that the python code directly manipulates the object
            ## received as parameter, instead of a copy.
            if self.type_traits.target_is_const:
                value = "(%s*) (&(%s))" % (self.cpp_class.full_name, self.value)
            else:
                value = "&(%s)" % self.value
            wrapper.before_call.write_code(
                "%s->obj = %s;" % (self.py_name, value))
            wrapper.build_params.add_parameter("O", [self.py_name])
            wrapper.before_call.add_cleanup_code("Py_DECREF(%s);" % self.py_name)

            if self.cpp_class.has_copy_constructor:
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
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.after_call, self.py_name,
                                                                           "%s->obj" % self.py_name)
                wrapper.after_call.unindent()
                wrapper.after_call.write_code('}')
            else:
                ## it's not safe for the python wrapper to keep a
                ## pointer to the object anymore; just set it to NULL.
                wrapper.after_call.write_code("%s->obj = NULL;" % (self.py_name,))


class CppClassReturnValue(CppClassReturnValueBase):
    "Class return handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    REQUIRES_ASSIGNMENT_CONSTRUCTOR = True

    def __init__(self, ctype, is_const=False):
        """override to fix the ctype parameter with namespace information"""
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassReturnValue, self).__init__(ctype, is_const=is_const)

    def get_c_error_return(self): # only used in reverse wrappers
        """See ReturnValue.get_c_error_return"""
        if self.type_traits.type_is_reference:
            raise NotSupportedError
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
        self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.after_call, py_name,
                                                                   "%s->obj" % py_name)
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)

    def convert_python_to_c(self, wrapper):
        """see ReturnValue.convert_python_to_c"""
        if self.type_traits.type_is_reference:
            raise NotSupportedError
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
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    SUPPORTS_TRANSFORMATIONS = True

    def __init__(self, ctype, name, transfer_ownership=None, custodian=None, is_const=False,
                 null_ok=False, default_value=None):
        """
        @param ctype: C type, normally 'MyClass*'
        @param name: parameter name

        @param transfer_ownership: this parameter transfer the ownership of
                              the pointed-to object to the called
                              function; should be omitted if custodian
                              is given.
        @param custodian: the object (custodian) that is responsible for
                     managing the life cycle of the parameter.
                     Possible values are:
                       - None: no object is custodian;
                       - -1: the return value object;
                       - 0: the instance of the method in which
                     the ReturnValue is being used will become the
                     custodian;
                       - integer > 0: parameter number, starting at 1
                     (i.e. not counting the self/this parameter),
                     whose object will be used as custodian.

        @param is_const: if true, the parameter has a const attached to the leftmost

        @param null_ok: if true, None is accepted and mapped into a C NULL pointer

        @param default_value: default parameter value (as C expression
        string); probably, the only default value that makes sense
        here is probably 'NULL'.

        @note: only arguments which are instances of C++ classes
        wrapped by PyBindGen can be used as custodians.
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassPtrParameter, self).__init__(
            ctype, name, direction=Parameter.DIRECTION_IN, is_const=is_const)

        if custodian is None:
            if transfer_ownership is None:
                if self.type_traits.target_is_const:
                    transfer_ownership = False
                else:
                    raise TypeConfigurationError("transfer_ownership parameter missing")
            self.transfer_ownership = transfer_ownership
        else:
            if transfer_ownership is not None:
                raise TypeConfigurationError("the transfer_ownership parameter should "
                                             "not be given when there is a custodian")
            self.transfer_ownership = False
        self.custodian = custodian
        self.null_ok = null_ok
        self.default_value = default_value

    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, cppclass.CppClass)

        if self.take_value_from_python_self:
            self.py_name = 'self'
            value_ptr = 'self->obj'
        else:
            self.py_name = wrapper.declarations.declare_variable(
                self.cpp_class.pystruct+'*', self.name,
                initializer=(self.default_value and 'NULL' or None))

            value_ptr = wrapper.declarations.declare_variable("%s*" % self.cpp_class.full_name,
                                                              "%s_ptr" % self.name)

            if self.null_ok:
                num = wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name, optional=bool(self.default_value))

                wrapper.before_call.write_error_check(

                    "%s && ((PyObject *) %s != Py_None) && !PyObject_IsInstance((PyObject *) %s, (PyObject *) &%s)"
                    % (self.py_name, self.py_name, self.py_name, self.cpp_class.pytypestruct),

                    'PyErr_SetString(PyExc_TypeError, "Parameter %i must be %s");' % (num, self.cpp_class.name))

                wrapper.before_call.write_code("if (%(PYNAME)s) {\n"
                                               "    if ((PyObject *) %(PYNAME)s == Py_None)\n"
                                               "        %(VALUE)s = NULL;\n"
                                               "    else\n"
                                               "        %(VALUE)s = %(PYNAME)s->obj;\n"
                                               "} else {\n"
                                               "    %(VALUE)s = NULL;\n"
                                               "}" % dict(PYNAME=self.py_name, VALUE=value_ptr))

            else:

                wrapper.parse_params.add_parameter(
                    'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name, optional=bool(self.default_value))
                wrapper.before_call.write_code("%s = (%s ? %s->obj : NULL);" % (value_ptr, self.py_name, self.py_name))

        value = self.transformation.transform(self, wrapper.declarations, wrapper.before_call, value_ptr)
        wrapper.call_params.append(value)
        
        if self.transfer_ownership:
            if not isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                # if we transfer ownership, in the end we no longer own the object, so clear our pointer
                wrapper.after_call.write_code('if (%s)\n    %s->obj = NULL;' % (self.py_name, self.py_name,))
            else:
                wrapper.before_call.write_code("if (%s) {" % self.py_name)
                wrapper.before_call.indent()
                self.cpp_class.memory_policy.write_incref(wrapper.before_call, "%s->obj" % self.py_name)
                wrapper.before_call.unindent()
                wrapper.before_call.write_code("}")


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
                and (self.transfer_ownership or isinstance(self.cpp_class.memory_policy,
                                                           cppclass.ReferenceCountingPolicy))):

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
            else:
                if not isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                    ## The PyObject gets a temporary pointer to the
                    ## original value; the pointer is converted to a
                    ## copy in case the callee retains a reference to
                    ## the object after the call.

                    if self.direction == Parameter.DIRECTION_IN:
                        self.cpp_class.write_create_instance(wrapper.before_call,
                                                             "%s->obj" % self.py_name,
                                                             '*'+self.value)
                    else:
                        ## out/inout case:
                        ## the callee receives a "temporary wrapper", which loses
                        ## the ->obj pointer after the python call; this is so
                        ## that the python code directly manipulates the object
                        ## received as parameter, instead of a copy.
                        if self.type_traits.target_is_const:
                            unconst_value = "(%s*) (%s)" % (self.cpp_class.full_name, value)
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
                    self.cpp_class.memory_policy.write_incref(wrapper.before_call, value)
                    if self.type_traits.target_is_const:
                        wrapper.before_call.write_code("%s->obj = (%s*) (%s);" %
                                                       (py_name, self.cpp_class.full_name, value))
                    else:
                        wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
        ## closes def write_create_new_wrapper():

        if self.cpp_class.helper_class is None:
            try:
                self.cpp_class.wrapper_registry.write_lookup_wrapper(
                    wrapper.before_call, self.cpp_class.pystruct, py_name, value)
            except NotSupportedError:
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, py_name,
                                                                           "%s->obj" % py_name)
            else:
                wrapper.before_call.write_code("if (%s == NULL)\n{" % py_name)
                wrapper.before_call.indent()
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, py_name,
                                                                           "%s->obj" % py_name)
                wrapper.before_call.unindent()
                wrapper.before_call.write_code('}')
            wrapper.build_params.add_parameter("N", [py_name])
        else:
            wrapper.before_call.write_code("if (typeid(*(%s)) == typeid(%s))\n{"
                                          % (value, self.cpp_class.helper_class.name))
            wrapper.before_call.indent()

            if self.type_traits.target_is_const:
                wrapper.before_call.write_code(
                    "%s = (%s*) (((%s*) ((%s*) %s))->m_pyself);"
                    % (py_name, self.cpp_class.pystruct,
                       self.cpp_class.helper_class.name, self.cpp_class.full_name, value))
                wrapper.before_call.write_code("%s->obj =  (%s*) (%s);" %
                                               (py_name, self.cpp_class.full_name, value))
            else:
                wrapper.before_call.write_code(
                    "%s = (%s*) (((%s*) %s)->m_pyself);"
                    % (py_name, self.cpp_class.pystruct,
                       self.cpp_class.helper_class.name, value))
                wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
            wrapper.before_call.write_code("Py_INCREF(%s);" % py_name)
            wrapper.before_call.unindent()
            wrapper.before_call.write_code("} else {")
            wrapper.before_call.indent()

            try:
                self.cpp_class.wrapper_registry.write_lookup_wrapper(
                    wrapper.before_call, self.cpp_class.pystruct, py_name, value)
            except NotSupportedError:
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(
                    wrapper.before_call, py_name, "%s->obj" % py_name)
            else:
                wrapper.before_call.write_code("if (%s == NULL)\n{" % py_name)
                wrapper.before_call.indent()
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, py_name,
                                                                           "%s->obj" % py_name)
                wrapper.before_call.unindent()
                wrapper.before_call.write_code('}') # closes if (%s == NULL)

            wrapper.before_call.unindent()
            wrapper.before_call.write_code("}") # closes if (typeid(*(%s)) == typeid(%s))\n{
            wrapper.build_params.add_parameter("N", [py_name])
            


def _add_ward(wrapper, custodian, ward):
    wards = wrapper.declarations.declare_variable(
        'PyObject*', 'wards')
    wrapper.after_call.write_code(
        "%(wards)s = PyObject_GetAttrString(%(custodian)s, (char *) \"__wards__\");"
        % vars())
    wrapper.after_call.write_code(
        "if (%(wards)s == NULL) {\n"
        "    PyErr_Clear();\n"
        "    %(wards)s = PyList_New(0);\n"
        "    PyObject_SetAttrString(%(custodian)s, (char *) \"__wards__\", %(wards)s);\n"
        "}" % vars())
    wrapper.after_call.write_code("PyList_Append(%s, %s);" % (wards, ward))
    wrapper.after_call.add_cleanup_code("Py_DECREF(%s);" % wards)



class CppClassPtrReturnValue(CppClassReturnValueBase):
    "Class* return handler"
    CTYPES = []
    SUPPORTS_TRANSFORMATIONS = True
    cpp_class = cppclass.CppClass('dummy') # CppClass instance

    def __init__(self, ctype, caller_owns_return=None, custodian=None, is_const=False):
        """
        @param ctype: C type, normally 'MyClass*'
        @param caller_owns_return: if true, ownership of the object pointer
                              is transferred to the caller; should be
                              omitted when custodian is given.
        @param custodian: the object (custodian) that becomes responsible for
                     managing the life cycle of the return value.
                     Possible values are:
                       - None: no object is custodian;
                       - 0: the instance of the method in which
                     the ReturnValue is being used will become the
                     custodian;
                       - integer > 0: parameter number, starting at 1
                     (i.e. not counting the self/this parameter),
                     whose object will be used as custodian.
        @note: only arguments which are instances of C++ classes
        wrapped by PyBindGen can be used as custodians.
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassPtrReturnValue, self).__init__(ctype, is_const=is_const)
        if custodian is None:
            if caller_owns_return is None:
                if self.type_traits.target_is_const:
                    caller_owns_return = False
                else:
                    raise TypeConfigurationError("caller_owns_return not given")
        else:
            if caller_owns_return is not None:
                raise TypeConfigurationError("caller_owns_return should not given together with custodian")
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
                and (self.caller_owns_return or isinstance(self.cpp_class.memory_policy,
                                                           cppclass.ReferenceCountingPolicy))):

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
                if not isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                    ## The PyObject creates its own copy
                    self.cpp_class.write_create_instance(wrapper.after_call,
                                                         "%s->obj" % py_name,
                                                         '*'+value)
                else:
                    ## The PyObject gets a new reference to the same obj
                    self.cpp_class.memory_policy.write_incref(wrapper.after_call, value)
                    if self.type_traits.target_is_const:
                        wrapper.after_call.write_code("%s->obj = (%s*) (%s);" %
                                                      (py_name, self.cpp_class.full_name, value))
                    else:
                        wrapper.after_call.write_code("%s->obj = %s;" % (py_name, value))
        ## closes def write_create_new_wrapper():

        if self.cpp_class.helper_class is None:
            try:
                self.cpp_class.wrapper_registry.write_lookup_wrapper(
                    wrapper.after_call, self.cpp_class.pystruct, py_name, value)
            except NotSupportedError:
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(
                    wrapper.after_call, py_name, "%s->obj" % py_name)
            else:
                wrapper.after_call.write_code("if (%s == NULL) {" % py_name)
                wrapper.after_call.indent()
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(
                    wrapper.after_call, py_name, "%s->obj" % py_name)
                wrapper.after_call.unindent()

                # If we are already referencing the existing python wrapper,
                # we do not need a reference to the C++ object as well.
                if self.caller_owns_return and \
                        isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                    wrapper.after_call.write_code("} else {")
                    wrapper.after_call.indent()
                    self.cpp_class.memory_policy.write_decref(wrapper.after_call, value)
                    wrapper.after_call.unindent()
                    wrapper.after_call.write_code("}")
                else:
                    wrapper.after_call.write_code("}")            
        else:
            wrapper.after_call.write_code("if (typeid(*(%s)) == typeid(%s))\n{"
                                          % (value, self.cpp_class.helper_class.name))
            wrapper.after_call.indent()

            if self.type_traits.target_is_const:
                const_cast_value = "const_cast<%s *>(%s) " % (self.cpp_class.full_name, value)
            else:
                const_cast_value = value
            wrapper.after_call.write_code(
                "%s = reinterpret_cast< %s* >(reinterpret_cast< %s* >(%s)->m_pyself);"
                % (py_name, self.cpp_class.pystruct,
                   self.cpp_class.helper_class.name, const_cast_value))

            wrapper.after_call.write_code("%s->obj = %s;" % (py_name, const_cast_value))
        
            # We are already referencing the existing python wrapper,
            # so we do not need a reference to the C++ object as well.
            if self.caller_owns_return and \
                    isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                self.cpp_class.memory_policy.write_decref(wrapper.after_call, value)

            wrapper.after_call.write_code("Py_INCREF(%s);" % py_name)
            wrapper.after_call.unindent()
            wrapper.after_call.write_code("} else {") # if (typeid(*(%s)) == typeid(%s)) { ...
            wrapper.after_call.indent()

            # creater new wrapper or reference existing one
            try:
                self.cpp_class.wrapper_registry.write_lookup_wrapper(
                    wrapper.after_call, self.cpp_class.pystruct, py_name, value)
            except NotSupportedError:
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(
                    wrapper.after_call, py_name, "%s->obj" % py_name)
            else:
                wrapper.after_call.write_code("if (%s == NULL) {" % py_name)
                wrapper.after_call.indent()
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(
                    wrapper.after_call, py_name, "%s->obj" % py_name)
                wrapper.after_call.unindent()

                if self.caller_owns_return and \
                        isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                    wrapper.after_call.write_code("} else {")
                    wrapper.after_call.indent()
                    # If we are already referencing the existing python wrapper,
                    # we do not need a reference to the C++ object as well.
                    self.cpp_class.memory_policy.write_decref(wrapper.after_call, value)
                    wrapper.after_call.unindent()
                    wrapper.after_call.write_code("}")
                else:
                    wrapper.after_call.write_code("}")            


            wrapper.after_call.unindent()
            wrapper.after_call.write_code("}") # closes: if (typeid(*(%s)) == typeid(%s)) { ... } else { ...
            
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
            if not isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                ## the caller receives a copy
                self.cpp_class.write_create_instance(wrapper.after_call,
                                                     "%s" % self.value,
                                                     '*'+value)
            else:
                ## the caller gets a new reference to the same obj
                self.cpp_class.memory_policy.write_incref(wrapper.after_call, value)
                if self.type_traits.target_is_const:
                    wrapper.after_call.write_code(
                        "%s = const_cast< %s* >(%s);" %
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


