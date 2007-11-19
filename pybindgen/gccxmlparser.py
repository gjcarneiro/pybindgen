#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os.path
from pygccxml import parser
from pygccxml import declarations
from module import Module
from typehandlers.codesink import FileCodeSink
from typehandlers.base import ReturnValue, Parameter
from enum import Enum
from function import Function
from cppclass import CppClass
from pygccxml.declarations import type_traits
from pygccxml.declarations import cpptypes

__all__ = ['ModuleScanner']

## ------------------------

class GccXmlTypeRegistry(object):
    def __init__(self):
        self.classes = {}  # value is a (return_handler, parameter_handler) tuple
    
    def register_class(self, cpp_class):
        assert isinstance(cpp_class, CppClass)
        if cpp_class.full_name.startswith('::'):
            full_name = cpp_class.full_name
        else:
            full_name = '::' + cpp_class.full_name
        self.classes[full_name] = cpp_class

    def _get_class_type_traits(self, type_info):
        assert isinstance(type_info, cpptypes.type_t)

        decomposed = type_traits.decompose_type(type_info)
        base_type = decomposed.pop()
        is_const = False
        is_reference = False
        is_pointer = False
        pointer_is_const = False
        if isinstance(base_type, cpptypes.declarated_t):
            try:
                cpp_class = self.classes[base_type.decl_string]
            except KeyError:
                return (None, is_const, is_pointer, is_reference, pointer_is_const)

            try:
                type_tmp = decomposed.pop()
            except IndexError:
                return (cpp_class, is_const, is_pointer, is_reference, pointer_is_const)

            if isinstance(type_tmp, cpptypes.const_t):
                is_const = True
                try:
                    type_tmp = decomposed.pop()
                except IndexError:
                    return (cpp_class, is_const, is_pointer, is_reference, pointer_is_const)

            if isinstance(type_tmp, cpptypes.reference_t):
                is_reference = True
            elif isinstance(type_tmp, cpptypes.pointer_t):
                is_pointer = True
            else:
                raise AssertionError
            
            try:
                type_tmp = decomposed.pop()
            except IndexError:
                pass
            else:
                if isinstance(type_tmp, cpptypes.const_t):
                    assert is_pointer
                    pointer_is_const = True
                else:
                    raise AssertionError
            assert len(decomposed) == 0
            return (cpp_class, is_const, is_pointer, is_reference, pointer_is_const)
        return (None, is_const, is_pointer, is_reference, pointer_is_const)

    def lookup_return(self, type_info):
        assert isinstance(type_info, cpptypes.type_t)
        cpp_class, is_const, is_pointer, is_reference, pointer_is_const = \
            self._get_class_type_traits(type_info)
        if cpp_class is None:
            return ReturnValue.new(type_info.decl_string)
        if not is_pointer and not is_reference:
            return cpp_class.ThisClassReturn(type_info.decl_string)
        if is_pointer and not is_reference:
            if is_const:
                ## a pointer to const object usually means caller_owns_return=False
                return cpp_class.ThisClassPtrReturn(type_info.decl_string, caller_owns_return=False)
            else:
                ## This will fail, "missing caller_owns_return
                ## parameter", but the lack of a const does not always
                ## imply caller_owns_return=True, so trying to guess
                ## here is a Bad Idea™
                return cpp_class.ThisClassPtrReturn(type_info.decl_string)
        if not is_pointer and is_reference:
            return cpp_class.ThisClassRefReturn(type_info.decl_string)
        assert 0, "this line should not be reached"

    def lookup_parameter(self, type_info, param_name):
        assert isinstance(type_info, cpptypes.type_t)
        cpp_class, is_const, is_pointer, is_reference, pointer_is_const = \
            self._get_class_type_traits(type_info)
        if cpp_class is None:
            return Parameter.new(type_info.decl_string, param_name)
        if not is_pointer and not is_reference:
            return cpp_class.ThisClassParameter(type_info.decl_string, param_name)
        if is_pointer and not is_reference:
            if is_const:
                ## a pointer to const object usually means transfer_ownership=False
                return cpp_class.ThisClassPtrParameter(type_info.decl_string, param_name,
                                                       transfer_ownership=False)
            else:
                ## This will fail, "missing param_name
                ## parameter", but the lack of a const does not always
                ## imply transfer_ownership=True, so trying to guess
                ## here is a Bad Idea™
                return cpp_class.ThisClassPtrParameter(type_info.decl_string, param_name)
        if not is_pointer and is_reference:
            return cpp_class.ThisClassRefParameter(type_info.decl_string, param_name)
        assert 0, "this line should not be reached"

type_registry = GccXmlTypeRegistry()

## ------------------------


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

        for enum in module_namespace.enums(function=self.location_filter, recursive=False, allow_empty=True):
            module.add_enum(Enum(enum.name, [name for name, dummy_val in enum.values]))

        for cls in module_namespace.classes(function=self.location_filter, recursive=False, allow_empty=True):
            class_wrapper = CppClass(cls.name)
            module.add_class(class_wrapper)
            if __debug__:
                if class_wrapper.full_name.startswith('::'):
                    full_name = class_wrapper.full_name
                else:
                    full_name = '::'+class_wrapper.full_name
                assert cls.decl_string == full_name
            type_registry.register_class(class_wrapper)
            

    def _scan_namespace_functions(self, module, module_namespace):
        for fun in module_namespace.free_functions(function=self.location_filter, recursive=False):
            try:
                return_type = type_registry.lookup_return(fun.return_type)
            except (TypeError, KeyError), ex:
                print >> sys.stderr, ("Return value '%s' error (used in %s): %r"
                                      % (fun.return_type.decl_string, fun, ex))
                continue
            arguments = []
            for arg in fun.arguments:
                try:
                    arguments.append(type_registry.lookup_parameter(arg.type, arg.name))
                except (TypeError, KeyError), ex:
                    print >> sys.stderr, ("Parameter '%s %s' error (used in %s): %r"
                                          % (arg.type.decl_string, arg.name, fun, ex))
                    ok = False
                    break
            else:
                ok = True
            if not ok:
                continue
                    
            func_wrapper = Function(return_type, fun.name, arguments)
            module.add_function(func_wrapper)
    

def _test():
    module_parser = ModuleParser('foo', '::')
    module = module_parser.parse(sys.argv[1:])
    print "------------ cut here ----------------------"
    out = FileCodeSink(sys.stdout)
    import utils
    utils.write_preamble(out)
    module.generate(out)

if __name__ == '__main__':
    _test()
