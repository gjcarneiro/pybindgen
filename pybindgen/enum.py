"""
Wraps enumerations
"""

from typehandlers import inttype


class Enum(object):
    """
    Class that adds support for a C/C++ enum type
    """
    def __init__(self, name, values, values_prefix='', cpp_namespace=None):
        """
        Creates a new enum wrapper, which should be added to a module with module.add_enum().

        cname -- C name of the enum type
        values -- a list of strings with all enumeration value names
        values_prefix -- prefix to add to value names, or None
        cpp_namespace -- optional C++ namespace identifier, or None.
                         Note: this namespace is *in addition to*
                         whatever namespace of the module the enum
                         belongs to.  Typically this parameter is to
                         be used when wrapping enums declared inside
                         C++ classes.
        """
        assert isinstance(name, str)
        assert '::' not in name
        for val in values:
            if not isinstance(val, str):
                raise TypeError

        self.name = name
        self.full_name = None
        self.values = list(values)
        self.values_prefix = values_prefix
        self.cpp_namespace = cpp_namespace
        self._module = None

    def get_module(self):
        """Get the Module object this class belongs to"""
        return self._module

    def set_module(self, module):
        """Set the Module object this class belongs to; can only be set once"""
        assert self._module is None
        self._module = module
        namespace = []
        if module.cpp_namespace_prefix:
            namespace.append(module.cpp_namespace_prefix)
        if self.cpp_namespace:
            namespace.append(self.cpp_namespace)
        self.full_name = '::'.join(namespace + [self.name])

        ## Register type handlers for the enum type
        class ThisEnumParameter(inttype.IntParam):
            CTYPES = [self.name, self.full_name]
            full_type_name = self.full_name
            def __init__(self, ctype, name):
                super(ThisEnumParameter, self).__init__(self.full_type_name, name)
        self.ThisEnumParameter = ThisEnumParameter
        
        class ThisEnumReturn(inttype.IntReturn):
            CTYPES = [self.name, self.full_name]
            full_type_name = self.full_name
            def __init__(self, ctype):
                super(ThisEnumReturn, self).__init__(self.full_type_name)
        self.ThisEnumReturn = ThisEnumReturn


    module = property(get_module, set_module)

    def generate(self, unused_code_sink):
        module = self.module
        namespace = []
        if module.cpp_namespace_prefix:
            namespace.append(module.cpp_namespace_prefix)
        if self.cpp_namespace:
            namespace.append(self.cpp_namespace)
        for value in self.values:
            module.after_init.write_code(
                "PyModule_AddIntConstant(m, \"%s\", %s);"
                % (value, '::'.join(namespace + [self.values_prefix + value])))
