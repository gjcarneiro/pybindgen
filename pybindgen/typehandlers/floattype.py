# docstrings not neede here (the type handler floaterfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue, Parameter, \
     ReverseWrapperBase, ForwardWrapperBase


class FloatParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['float']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('f', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype, self.name)
        wrapper.parse_params.add_parameter('f', ['&'+name], self.value)
        wrapper.call_params.append(name)


class FloatReturn(ReturnValue):

    CTYPES = ['float']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("f", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("f", [self.value], prepend=True)


class FloatPtrParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['float*']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('f', ['*'+self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("f", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'float*'
        name = wrapper.declarations.declare_variable(self.ctype[:-1], self.name)
        wrapper.call_params.append('&'+name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('f', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("f", [name])
        


class FloatRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['float&']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('f', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("f", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'float&'
        name = wrapper.declarations.declare_variable(self.ctype[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('f', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("f", [name])
