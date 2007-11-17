import os.path
from pygccxml import parser
from pygccxml import declarations
from module import Module
from typehandlers.codesink import FileCodeSink
from typehandlers.base import ReturnValue, Parameter
from enum import Enum
from function import Function

__all__ = ['ModuleScanner']


class ModuleParser(object):
    def __init__(self, module_name, module_namespace_name='::'):
        """
        Creates an object that will be able parse header files and
        create a pybindgen module definition.

        module_name -- name of the Python module
        module_namespace_name -- optional C++ namespace name; if
                                 given, only definitions of this
                                 namespace will be included in the
                                 python module
        """
        self.module_name = module_name
        self.module_namespace_name = module_namespace_name
        self.location_filter = None
        self.header_files = None

    def __location_match(self, decl):
        return (decl.location.file_name in self.header_files)

    def parse(self, header_files):
        """
        parses a set of header files and returns a pybindgen Module instance.
        """
        assert isinstance(header_files, list)
        self.header_files = [os.path.abspath(f) for f in header_files]
        self.location_filter = declarations.custom_matcher_t(self.__location_match)

        config = parser.config_t()
        decls = parser.parse(header_files, config)
        if self.module_namespace_name == '::':
            module_namespace = declarations.get_global_namespace(decls)
        else:
            module_namespace = declarations.get_global_namespace(decls).namespace(self.module_namespace_name)
        module = Module(self.module_name, cpp_namespace=module_namespace.decl_string)
        self._scan_namespace_types(module, module_namespace)
        self._scan_namespace_functions(module, module_namespace)

        return module

    def _scan_namespace_types(self, module, module_namespace):
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            nested_module = Module(name=nested_namespace.name, parent=module, cpp_namespace=nested_namespace.name)
            self._scan_namespace_types(nested_module, nested_namespace)
        for enum in module_namespace.enums(function=self.location_filter, recursive=False):
            module.add_enum(Enum(enum.name, [name for name, dummy_val in enum.values]))

    def _scan_namespace_functions(self, module, module_namespace):
        for fun in module_namespace.free_functions(function=self.location_filter, recursive=False):
            return_type = ReturnValue.new(fun.return_type.decl_string)
            arguments = [Parameter.new(arg.type.decl_string, arg.name) for arg in fun.arguments]
            func_wrapper = Function(return_type, fun.name, arguments)
            module.add_function(func_wrapper)
    

def _test():
    import sys
    module_parser = ModuleParser('xpto', 'xpto')
    module = module_parser.parse(sys.argv[1:])
    print "------------ cut here ----------------------"
    out = FileCodeSink(sys.stdout)
    #import utils
    #utils.write_preamble(out)
    module.generate(out)

if __name__ == '__main__':
    _test()
