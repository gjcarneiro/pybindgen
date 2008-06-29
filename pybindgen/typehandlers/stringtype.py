# docstrings not neede here (the type handler interfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue, PointerReturnValue, Parameter, PointerParameter, ReverseWrapperBase, ForwardWrapperBase


class CStringParam(PointerParameter):
    """
    >>> isinstance(Parameter.new('char*', 's'), CStringParam)
    True
    """

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['char*', 'const char*']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('s', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype, self.name)
        wrapper.parse_params.add_parameter('s', ['&'+name], self.value)
        wrapper.call_params.append(name)


class CharParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['char']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('c', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype, self.name)
        wrapper.parse_params.add_parameter('c', ['&'+name], self.value)
        wrapper.call_params.append(name)


class StdStringParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['std::string', 'std::string const']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
        len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
        wrapper.before_call.write_code(
            "%s = %s.c_str();" % (ptr, self.value))
        wrapper.before_call.write_code(
            "%s = %s.size();" % (len_, self.value))
        wrapper.build_params.add_parameter('s#', [ptr, len_])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        if self.default_value is None:
            name = wrapper.declarations.declare_variable("const char *", self.name)
            name_len = wrapper.declarations.declare_variable("Py_ssize_t", self.name+'_len')
            wrapper.parse_params.add_parameter('s#', ['&'+name, '&'+name_len], self.value)
            wrapper.call_params.append('std::string(%s, %s)' % (name, name_len))
        else:
            name = wrapper.declarations.declare_variable("const char *", self.name, 'NULL')
            name_len = wrapper.declarations.declare_variable("Py_ssize_t", self.name+'_len')
            wrapper.parse_params.add_parameter('s#', ['&'+name, '&'+name_len], self.value, optional=True)
            wrapper.call_params.append('(%s ? std::string(%s, %s) : %s)'
                                       % (name, name, name_len, self.default_value))


class StdStringRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['std::string&', 'std::string const &']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)

        ptr = None
        if self.direction & Parameter.DIRECTION_IN:
            ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
            len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.before_call.write_code(
                "%s = %s.c_str();" % (ptr, self.value))
            wrapper.before_call.write_code(
                "%s = %s.size();" % (len_, self.value))
            wrapper.build_params.add_parameter('s#', [ptr, len_])

        if self.direction & Parameter.DIRECTION_OUT:
            if ptr is None:
                ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
                len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.parse_params.add_parameter("s#", ['&'+ptr, '&'+len_], self.value)
            wrapper.after_call.write_code(
                "%s = std::string(%s, %s);" % (self.value, ptr, len_))

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("const char *", self.name)
        name_len = wrapper.declarations.declare_variable("Py_ssize_t", self.name+'_len')
        name_std = wrapper.declarations.declare_variable("std::string", self.name + '_std')
        wrapper.call_params.append(name_std)

        if self.direction & Parameter.DIRECTION_IN:
            wrapper.parse_params.add_parameter('s#', ['&'+name, '&'+name_len], self.value)
            wrapper.before_call.write_code('%s = std::string(%s, %s);' %
                                           (name_std, name, name_len))

        if self.direction & Parameter.DIRECTION_OUT:
            wrapper.build_params.add_parameter("s#", [name_std+'.c_str()', name_std+'.size()'])


class CharReturn(ReturnValue):

    CTYPES = ['char']

    def get_c_error_return(self):
        return "return '\\0';"

    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("c", ['&'+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("c", ["(int) %s" % self.value])


class CStringReturn(PointerReturnValue):
    """
    >>> isinstance(ReturnValue.new('char*'), CStringReturn)
    True
    """

    CTYPES = ['char*', 'char const *']

    def get_c_error_return(self):
        return "return NULL;"

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable(self.ctype, "retval_ptr")
        wrapper.parse_params.add_parameter("s", ['&'+name], self.value)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("s", [self.value])


class StdStringReturn(ReturnValue):

    CTYPES = ['std::string']

    def get_c_error_return(self):
        return "return std::string();"
    
    def convert_python_to_c(self, wrapper):
        ptr = wrapper.declarations.declare_variable("const char *", "retval_ptr")
        len_ = wrapper.declarations.declare_variable("Py_ssize_t", "retval_len")
        wrapper.parse_params.add_parameter("s#", ['&'+ptr, '&'+len_])
        wrapper.after_call.write_code(
            "%s = std::string(%s, %s);" % (self.value, ptr, len_))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("s#", ['%s.c_str()' % self.value,
                                                  '%s.size()' % self.value],
                                           prepend=True)
