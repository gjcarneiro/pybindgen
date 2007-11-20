#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os.path
import warnings
from pygccxml import parser
from pygccxml import declarations
from module import Module
from typehandlers.codesink import FileCodeSink
from typehandlers.base import ReturnValue, Parameter
from enum import Enum
from function import Function
from cppclass import CppClass, CppConstructor, CppMethod
from pygccxml.declarations import type_traits
from pygccxml.declarations import cpptypes
from pygccxml.declarations import calldef

#from pygccxml.declarations.calldef import \
#    destructor_t, constructor_t, member_function_t
from pygccxml.declarations.variable import variable_t

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
        ## scan enumerations
        for enum in module_namespace.enums(function=self.location_filter, recursive=False, allow_empty=True):
            if enum.name.startswith('__'):
                continue
            module.add_enum(Enum(enum.name, [name for name, dummy_val in enum.values]))

        ## scan classes
        unregistered_classes = [cls for cls in
                                module_namespace.classes(function=self.location_filter,
                                                         recursive=False, allow_empty=True)
                                if not cls.name.startswith('__')]
        registered_classes = {} # class_t -> CppClass
        while unregistered_classes:
            cls = unregistered_classes.pop(0)
            if '<' in cls.name:
                warnings.warn("Class %s ignored because it is templated; templates not yet supported"
                              % cls.decl_string)
                continue
                
            if len(cls.bases) > 1:
                warnings.warn("Class %s ignored because it uses multiple "
                              "inheritance (not yet supported by pybindgen)"
                              % cls.decl_string)
                continue
            if cls.bases:
                base_cls = cls.bases[0].related_class
                try:
                    base_class_wrapper = registered_classes[base_cls]
                except KeyError:
                    ## base class not yet registered => postpone this class registration
                    if base_cls not in unregistered_classes:
                        warnings.warn("Class %s ignored because it uses has a base class (%s) "
                                      "which is not declared."
                                      % (cls.decl_string, base_cls.decl_string))
                        continue
                    unregistered_classes.append(cls)
                    continue
            else:
                base_class_wrapper = None

            if self._class_has_virtual_methods(cls):
                allow_subclassing = True
            else:
                allow_subclassing = None

            if self._class_has_public_destructor(cls):
                is_singleton = None
            else:
                is_singleton = True

            class_wrapper = CppClass(cls.name, parent=base_class_wrapper,
                                     allow_subclassing=allow_subclassing,
                                     is_singleton=is_singleton)
            module.add_class(class_wrapper)
            registered_classes[cls] = class_wrapper
            type_registry.register_class(class_wrapper)
            assert cls.decl_string in type_registry.classes\
                and type_registry.classes[cls.decl_string] == class_wrapper

        for cls, class_wrapper in registered_classes.iteritems():
            self._scan_methods(cls, class_wrapper)
            
        ## scan nested namespaces (mapped as python submodules)
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            if nested_namespace.name.startswith('__'):
                continue
            nested_module = Module(name=nested_namespace.name, parent=module, cpp_namespace=nested_namespace.name)
            self._scan_namespace_types(nested_module, nested_namespace)

    def _class_has_virtual_methods(self, cls):
        """return True if cls has at least one virtual method, else False"""
        for member in cls.get_members('public'):
            if isinstance(member, calldef.member_function_t):
                if member.virtuality != calldef.VIRTUALITY_TYPES.NOT_VIRTUAL:
                    return True
        return False

    def _class_has_public_destructor(self, cls):
        """return True if cls has a public destructor, else False"""
        for member in cls.get_members('public'):
            if isinstance(member, calldef.destructor_t):
                return True
        return False

    def _scan_methods(self, cls, class_wrapper):
        for member in cls.get_members('public'):

            if isinstance(member, calldef.member_function_t):
                try:
                    return_type = type_registry.lookup_return(member.return_type)
                except (TypeError, KeyError), ex:
                    warnings.warn("Return value '%s' error (used in %s): %r"
                                  % (member.return_type.decl_string, member, ex))
                    continue
                arguments = []
                for arg in member.arguments:
                    try:
                        arguments.append(type_registry.lookup_parameter(arg.type, arg.name))
                    except (TypeError, KeyError), ex:
                        warnings.warn("Parameter '%s %s' error (used in %s): %r"
                                      % (arg.type.decl_string, arg.name, member, ex))
                        ok = False
                        break
                else:
                    ok = True
                if not ok:
                    continue

                method_wrapper = CppMethod(return_type, member.name, arguments,
                                           is_const=member.has_const,
                                           is_static=member.has_static,
                                           is_virtual=(member.virtuality !=
                                                       calldef.VIRTUALITY_TYPES.NOT_VIRTUAL))
                class_wrapper.add_method(method_wrapper)

            elif isinstance(member, calldef.constructor_t):
                arguments = []
                for arg in member.arguments:
                    try:
                        arguments.append(type_registry.lookup_parameter(arg.type, arg.name))
                    except (TypeError, KeyError), ex:
                        warnings.warn("Parameter '%s %s' error (used in %s): %r"
                                      % (arg.type.decl_string, arg.name, member, ex))
                        ok = False
                        break
                else:
                    ok = True
                if not ok:
                    continue
                constructor_wrapper = CppConstructor(arguments)
                class_wrapper.add_constructor(constructor_wrapper)

            elif isinstance(member, variable_t):
                try:
                    return_type = type_registry.lookup_return(member.type)
                except (TypeError, KeyError), ex:
                    warnings.warn("Return value '%s' error (used in %s): %r"
                                  % (member.type.decl_string, member, ex))
                    continue
                if member.type_qualifiers.has_static:
                    class_wrapper.add_static_attribute(return_type, member.name)
                else:
                    class_wrapper.add_instance_attribute(return_type, member.name)
            
            elif isinstance(member, calldef.destructor_t):
                pass

            
    def _scan_namespace_functions(self, module, module_namespace):
        for fun in module_namespace.free_functions(function=self.location_filter,
                                                   allow_empty=True, recursive=False):
            if fun.name.startswith('__'):
                continue
            try:
                return_type = type_registry.lookup_return(fun.return_type)
            except (TypeError, KeyError), ex:
                warnings.warn("Return value '%s' error (used in %s): %r"
                              % (fun.return_type.decl_string, fun, ex))
                continue
            arguments = []
            for arg in fun.arguments:
                try:
                    arguments.append(type_registry.lookup_parameter(arg.type, arg.name))
                except (TypeError, KeyError), ex:
                    warnings.warn("Parameter '%s %s' error (used in %s): %r"
                                  % (arg.type.decl_string, arg.name, fun, ex))
                    ok = False
                    break
            else:
                ok = True
            if not ok:
                continue
                    
            func_wrapper = Function(return_type, fun.name, arguments)
            module.add_function(func_wrapper)

        ## scan nested namespaces (mapped as python submodules)
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            if nested_namespace.name.startswith('__'):
                continue
            nested_module = Module(name=nested_namespace.name, parent=module, cpp_namespace=nested_namespace.name)
            self._scan_namespace_functions(nested_module, nested_namespace)
    

def _test():
    module_parser = ModuleParser('foo', '::')
    module = module_parser.parse(sys.argv[1:])
    if 0:
        print "------------ cut here ----------------------"
        out = FileCodeSink(sys.stdout)
        import utils
        utils.write_preamble(out)
        module.generate(out)

if __name__ == '__main__':
    _test()
