#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os.path
import warnings
import re
from pygccxml import parser
from pygccxml import declarations
from module import Module
from typehandlers.codesink import FileCodeSink
import typehandlers.base
from typehandlers.base import ReturnValue, Parameter, TypeLookupError, TypeConfigurationError, NotSupportedError
from pygccxml.declarations.enumeration import enumeration_t
from enum import Enum
from function import Function
from cppclass import CppClass, CppConstructor, CppMethod
from pygccxml.declarations import type_traits
from pygccxml.declarations import cpptypes
from pygccxml.declarations import calldef
from pygccxml.declarations import templates
from pygccxml.declarations.class_declaration import class_declaration_t, class_t
import settings

#from pygccxml.declarations.calldef import \
#    destructor_t, constructor_t, member_function_t
from pygccxml.declarations.variable import variable_t

## ------------------------

class ErrorHandler(settings.ErrorHandler):
    def handle_error(self, wrapper, exception, traceback_):
        if hasattr(wrapper, "gccxml_definition"):
            definition = wrapper.gccxml_definition
        elif hasattr(wrapper, "main_wrapper"):
            try:
                definition = wrapper.main_wrapper.gccxml_definition
            except AttributeError:
                definition = None
        else:
            definition = None

        if definition is None:
            print >> sys.stderr, "exception %r in wrapper %s" % (exception, wrapper)
        else:
            warnings.warn_explicit("exception %r in wrapper for %s"
                                   % (exception, definition),
                                   Warning, definition.location.file_name,
                                   definition.location.line)
        return True
settings.error_handler = ErrorHandler()

_digits = re.compile(r"\s*\d+\s*")
def normalize_name(decl_string):
    if templates.is_instantiation(decl_string):
        cls_name, template_parameters = templates.split(decl_string)
    else:
        cls_name = decl_string
        template_parameters = None
    if not _digits.match(cls_name):
        if cls_name.startswith('::'):
            cls_name = cls_name[2:]
    if template_parameters is None:
        return cls_name
    else:
        return "%s< %s >" % (cls_name, ', '.join([normalize_name(name) for name in template_parameters]))


class GccXmlTypeRegistry(object):
    def __init__(self):
        self.classes = {}  # registered classes dictionary
        self.ordered_classes = [] # registered classes list, by registration order
        self._root_ns_rx = re.compile(r"(^|\s)(::)")
    
    def register_class(self, cpp_class, alias=None):
        assert isinstance(cpp_class, CppClass)
        full_name = normalize_name(cpp_class.full_name)
        #print >> sys.stderr, "******** registering class %s as %s" \
        #    % (cpp_class.gccxml_definition, full_name)
        self.classes[full_name] = cpp_class
        self.ordered_classes.append(cpp_class)
        if alias is not None:
            alias = normalize_name(alias)
            self.classes[alias] = cpp_class
            cpp_class.register_alias(alias)
            #print >> sys.stderr, "******** registering class %s also as alias %s" \
            #        % (cpp_class.gccxml_definition, alias)

    def find_class(self, class_name, module_namespace):
        if not class_name.startswith(module_namespace):
            class_name = module_namespace + class_name
        class_name = normalize_name(class_name)
        #if '<' in class_name:
        #    print >> sys.stderr, "******** looking for class %s" \
        #        % (class_name)
        return self.classes[class_name]           

    def get_class_type_traits(self, type_info):
        assert isinstance(type_info, cpptypes.type_t)

        decomposed = type_traits.decompose_type(type_info)

        base_type = decomposed.pop()
        is_const = False
        is_reference = False
        is_pointer = False
        pointer_is_const = False
        if isinstance(base_type, cpptypes.declarated_t):
            class_name = normalize_name(base_type.decl_string)
            #if '<' in class_name:
            #    print >> sys.stderr, "******** looking for class %s" \
            #        % (class_name)
            try:
                cpp_class = self.classes[class_name]
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
                elif isinstance(type_tmp, cpptypes.pointer_t):
                    return (None, is_const, is_pointer, is_reference, pointer_is_const)
                else:
                    raise AssertionError, "found %r for type %s" % (type_tmp, type_info.decl_string)
            assert len(decomposed) == 0
            return (cpp_class, is_const, is_pointer, is_reference, pointer_is_const)
        return (None, is_const, is_pointer, is_reference, pointer_is_const)

    def _fixed_std_type_name(self, type_info):
        decl = self._root_ns_rx.sub('', type_info.decl_string)
        return decl
        

    def lookup_return(self, type_info, annotations={}):
        assert isinstance(type_info, cpptypes.type_t)
        cpp_class, is_const, is_pointer, is_reference, pointer_is_const = \
            self.get_class_type_traits(type_info)

        kwargs = {}
        for name, value in annotations.iteritems():
            if name == 'caller_owns_return':
                kwargs['caller_owns_return'] = annotations_scanner.parse_boolean(value)
            elif name == 'custodian':
                kwargs['custodian'] = int(value)
            else:
                warnings.warn("invalid annotation name %r" % name)

        if is_const:
            kwargs['is_const'] = True

        if cpp_class is None:
            if isinstance(type_traits.remove_declarated(type_info), enumeration_t):
                return ReturnValue.new(normalize_name(type_info.decl_string), **kwargs)
            else:
                return ReturnValue.new(self._fixed_std_type_name(type_info), **kwargs)

        if not is_pointer and not is_reference:
            return cpp_class.ThisClassReturn(type_info.decl_string)
        if is_pointer and not is_reference:
            if is_const:
                ## a pointer to const object usually means caller_owns_return=False
                return cpp_class.ThisClassPtrReturn(type_info.decl_string, caller_owns_return=False,
                                                    **kwargs)
            else:
                ## This will fail, "missing caller_owns_return
                ## parameter", but the lack of a const does not always
                ## imply caller_owns_return=True, so trying to guess
                ## here is a Bad Idea™
                return cpp_class.ThisClassPtrReturn(type_info.decl_string, **kwargs)
        if not is_pointer and is_reference:
            return cpp_class.ThisClassRefReturn(type_info.decl_string, **kwargs)
        assert 0, "this line should not be reached"

    def lookup_parameter(self, type_info, param_name, annotations={}):
        assert isinstance(type_info, cpptypes.type_t)

        kwargs = {}
        for name, value in annotations.iteritems():
            if name == 'transfer_ownership':
                kwargs['transfer_ownership'] = annotations_scanner.parse_boolean(value)
            elif name == 'direction':
                if value.lower() == 'in':
                    kwargs['direction'] = Parameter.DIRECTION_IN
                elif value.lower() == 'out':
                    kwargs['direction'] = Parameter.DIRECTION_OUT
                elif value.lower() == 'inout':
                    kwargs['direction'] = Parameter.DIRECTION_INOUT
                else:
                    warnings.warn("invalid direction direction %r" % value)
            elif name == 'custodian':
                kwargs['custodian'] = int(value)
            else:
                warnings.warn("invalid annotation name %r" % name)

        cpp_class, is_const, is_pointer, is_reference, pointer_is_const = \
            self.get_class_type_traits(type_info)
        if is_const:
            kwargs['is_const'] = True
        if cpp_class is None:
            if isinstance(type_traits.remove_declarated(type_info), enumeration_t):
                return Parameter.new(normalize_name(type_info.decl_string), param_name, **kwargs)
            else:
                return Parameter.new(self._fixed_std_type_name(type_info), param_name, **kwargs)
        if not is_pointer and not is_reference:
            return cpp_class.ThisClassParameter(type_info.decl_string, param_name, **kwargs)
        if is_pointer and not is_reference:
            if is_const:
                ## a pointer to const object usually means transfer_ownership=False
                kwargs.setdefault('transfer_ownership', False)
                return cpp_class.ThisClassPtrParameter(type_info.decl_string, param_name,
                                                       **kwargs)
            else:
                ## This will fail, "missing param_name
                ## parameter", but the lack of a const does not always
                ## imply transfer_ownership=True, so trying to guess
                ## here is a Bad Idea™
                return cpp_class.ThisClassPtrParameter(type_info.decl_string, param_name, **kwargs)
        if not is_pointer and is_reference:
            return cpp_class.ThisClassRefParameter(type_info.decl_string, param_name, **kwargs)
        assert 0, "this line should not be reached"

type_registry = GccXmlTypeRegistry()


class AnnotationsScanner(object):
    def __init__(self):
        self.files = {} # file name -> list(lines)
        self.used_annotations = {} # file name -> list(line_numbers)
        self._comment_rx = re.compile(
            r"^\s*(?://\s+-#-(?P<annotation1>.*)-#-\s*)|(?:/\*\s+-#-(?P<annotation2>.*)-#-\s*\*/)")
        self._global_annotation_rx = re.compile(r"(\w+)(?:=([^\s;]+))?")
        self._param_annotation_rx = re.compile(r"@(\w+)\(([^;]+)\)")

    def _declare_used_annotation(self, file_name, line_number):
        try:
            l = self.used_annotations[file_name]
        except KeyError:
            l = []
            self.used_annotations[file_name] = l
        l.append(line_number)

    def get_annotations(self, file_name, line_number):
        """
        file_name -- absolute file name where the definition is
        line_number -- line number of where the definition is within the file
        """
        try:
            lines = self.files[file_name]
        except KeyError:
            lines = file(file_name, "rt").readlines()
            self.files[file_name] = lines

        line_number -= 2
        global_annotations = {}
        parameter_annotations = {}
        while 1:
            line = lines[line_number]
            line_number -= 1
            m = self._comment_rx.match(line)
            if m is None:
                break
            s = m.group('annotation1')
            if s is None:
                s = m.group('annotation2')
            line = s.strip()
            self._declare_used_annotation(file_name, line_number + 2)
            for annotation_str in line.split(';'):
                annotation_str = annotation_str.strip()
                m = self._global_annotation_rx.match(annotation_str)
                if m is not None:
                    global_annotations[m.group(1)] = m.group(2)
                    continue

                m = self._param_annotation_rx.match(annotation_str)
                if m is not None:
                    param_annotation = {}
                    parameter_annotations[m.group(1)] = param_annotation
                    for param in m.group(2).split(','):
                        m = self._global_annotation_rx.match(param.strip())
                        if m is not None:
                            param_annotation[m.group(1)] = m.group(2)
                        else:
                            warnings.warn_explicit("could not parse %r as parameter annotation element" %
                                                   (param.strip()),
                                                   Warning, file_name, line_number)
                    continue
                warnings.warn_explicit("could not parse %r" % (annotation_str),
                                       Warning, file_name, line_number)
        return global_annotations, parameter_annotations

    def parse_boolean(self, value):
        if value.lower() in ['false', 'off']:
            return False
        elif value.lower() in ['true', 'on']:
            return True
        else:
            raise ValueError("bad boolean value %r" % value)

    def warn_unused_annotations(self):
        for file_name, lines in self.files.iteritems():
            try:
                used_annotations = self.used_annotations[file_name]
            except KeyError:
                used_annotations = []
            for line_number, line in enumerate(lines):
                m = self._comment_rx.match(line)
                if m is None:
                    continue
                #print >> sys.stderr, (line_number+1), used_annotations
                if (line_number + 1) not in used_annotations:
                    warnings.warn_explicit("unused annotation",
                                           Warning, file_name, line_number+1)
                    
        

annotations_scanner = AnnotationsScanner()

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
        self.gccxml_config = None
        self.whitelist_paths = []
        self.module_namespace = None # pygccxml module C++ namespace
        self.module = None # the toplevel pybindgen.module.Module instance (module being generated)
        self.declarations = None # pygccxml.declarations.namespace.namespace_t (as returned by pygccxml.parser.parse)
        self._types_scanned = False
        self._pre_scan_hooks = []
        self._post_scan_hooks = []

    def add_pre_scan_hook(self, hook):
        """
        Add a function to be called right before converting a gccxml
        definition to a PyBindGen wrapper object.  This hook function
        will be called for every scanned type, function, or method,
        and given the a chance to modify the annotations for that
        definition.  It will be called like this:

        pre_scan_hook(module_parser, pygccxml_definition, global_annotations,
                      parameter_annotations)
        
        where:

           module_parser -- the ModuleParser (this class) instance
           pygccxml_definition -- the definition reported by pygccxml
           global_annotations -- a dicionary containing the "global annotations"
                                 for the definition, i.e. a set of key=value
                                 pairs not associated with any particular
                                 parameter
           parameter_annotations -- a dicionary containing the "parameter
                                    annotations" for the definition.  It is a
                                    dict whose keys are parameter names and
                                    whose values are dicts containing the
                                    annotations for that parameter.  Annotations
                                    pertaining the return value of functions or
                                    methods are denoted by a annotation for a
                                    parameter named 'return'.
        """
        if not callable(hook):
            raise TypeError("hook must be callable")
        self._pre_scan_hooks.append(hook)

    def add_post_scan_hook(self, hook):
        """
        Add a function to be called right after converting a gccxml definition
        to a PyBindGen wrapper object.  This hook function will be called for
        every scanned type, function, or method.  It will be called like this:

        post_scan_hook(module_parser, pygccxml_definition, pybindgen_wrapper)
        
        where:

           module_parser -- the ModuleParser (this class) instance
           pygccxml_definition -- the definition reported by pygccxml
           pybindgen_wrapper -- a pybindgen object that generates a wrapper,
                                such as CppClass, Function, or CppMethod.
        """
        if not callable(hook):
            raise TypeError("hook must be callable")
        self._post_scan_hooks.append(hook)

    def __location_match(self, decl):
        if decl.location.file_name in self.header_files:
            return True
        for incdir in self.whitelist_paths:
            if os.path.abspath(decl.location.file_name).startswith(incdir):
                return True
        return False

    def parse(self, header_files, include_paths=None, whitelist_paths=None):
        """
        parses a set of header files and returns a pybindgen Module instance.
        It is equivalent to calling the following methods:
        1. parse_init(header_files, include_paths, whitelist_paths)
        2. scan_types()
        3. scan_methods()
        4. scan_functions()
        5. parse_finalize()
        """
        self.parse_init(header_files, include_paths, whitelist_paths)
        self.scan_types()
        self.scan_methods()
        self.scan_functions()
        self.parse_finalize()
        return self.module

    def parse_init(self, header_files, include_paths=None, whitelist_paths=None):
        """
        Prepares to parse a set of header files.  The following
        methods should then be called in order to finish the rest of
        scanning process:
        1. scan_types()
        2. scan_methods()
        2. scan_functions()
        3. parse_finalize()
        """
        assert isinstance(header_files, list)
        self.header_files = [os.path.abspath(f) for f in header_files]
        self.location_filter = declarations.custom_matcher_t(self.__location_match)

        if whitelist_paths is not None:
            assert isinstance(whitelist_paths, list)
            self.whitelist_paths = [os.path.abspath(p) for p in whitelist_paths]

        if include_paths is not None:
            assert isinstance(include_paths, list)
            self.gccxml_config = parser.config_t(include_paths=include_paths)
        else:
            self.gccxml_config = parser.config_t()

        self.declarations = parser.parse(header_files, self.gccxml_config)
        if self.module_namespace_name == '::':
            self.module_namespace = declarations.get_global_namespace(self.declarations)
        else:
            self.module_namespace = declarations.get_global_namespace(self.declarations).\
                namespace(self.module_namespace_name)
        self.module = Module(self.module_name, cpp_namespace=self.module_namespace.decl_string)

    def scan_types(self):
        self._scan_namespace_types(self.module, self.module_namespace)
        self._types_scanned = True

    def scan_methods(self):
        assert self._types_scanned
        for class_wrapper in type_registry.ordered_classes:
            if isinstance(class_wrapper.gccxml_definition, class_declaration_t):
                continue # skip classes not fully defined
            self._scan_class_methods(class_wrapper.gccxml_definition, class_wrapper)

    def scan_functions(self):
        assert self._types_scanned
        self._scan_namespace_functions(self.module, self.module_namespace)

    def parse_finalize(self):
        annotations_scanner.warn_unused_annotations()
        return self.module

    def _apply_class_annotations(self, cls, annotations, kwargs):
        for name, value in annotations.iteritems():
            if name == 'allow_subclassing':
                kwargs.setdefault('allow_subclassing', annotations_scanner.parse_boolean(value))
            elif name == 'is_singleton':
                kwargs.setdefault('is_singleton', annotations_scanner.parse_boolean(value))
            elif name == 'incref_method':
                kwargs.setdefault('incref_method', value)
            elif name == 'decref_method':
                kwargs.setdefault('decref_method', value)
            elif name == 'peekref_method':
                kwargs.setdefault('peekref_method', value)
            elif name == 'automatic_type_narrowing':
                kwargs.setdefault('automatic_type_narrowing', annotations_scanner.parse_boolean(value))
            elif name == 'free_function':
                kwargs.setdefault('free_function', value)
            elif name == 'incref_function':
                kwargs.setdefault('incref_function', value)
            elif name == 'decref_function':
                kwargs.setdefault('decref_function', value)
            elif name == 'python_name':
                kwargs.setdefault('python_name', value)
            else:
                warnings.warn_explicit("Class annotation %r ignored" % name,
                                       Warning, cls.location.file_name, cls.location.line)
                
        if isinstance(cls, class_t):
            if self._class_has_virtual_methods(cls):
                kwargs.setdefault('allow_subclassing', True)

            if not self._class_has_public_destructor(cls):
                kwargs.setdefault('is_singleton', True)


    def _scan_namespace_types(self, module, module_namespace, outer_class=None):
        ## scan enumerations
        if outer_class is None:
            enums = module_namespace.enums(function=self.location_filter,
                                           recursive=False, allow_empty=True)
        else:
            enums = []
            for enum in outer_class.gccxml_definition.enums(function=self.location_filter,
                                                            recursive=False, allow_empty=True):
                if outer_class.gccxml_definition.find_out_member_access_type(enum) != 'public':
                    continue
                if enum.name.startswith('__'):
                    continue
                if not enum.name:
                    warnings.warn_explicit("Enum %s ignored because it has no name"
                                           % (enum, ),
                                           Warning, enum.location.file_name, enum.location.line)
                    continue
                enums.append(enum)

        for enum in enums:
            module.add_enum(Enum(enum.name, [name for name, dummy_val in enum.values],
                                 outer_class=outer_class))

        registered_classes = {} # class_t -> CppClass

        ## Look for forward declarations of class/structs like
        ## "typedef struct _Foo Foo"; these are represented in
        ## pygccxml by a typedef whose .type.declaration is a
        ## class_declaration_t instead of class_t.
        for alias in module_namespace.typedefs(function=self.location_filter,
                                              recursive=False, allow_empty=True):

            ## handle "typedef int Something;"
            if isinstance(alias.type, cpptypes.int_t):
                param_cls, dummy_transf = typehandlers.base.param_type_matcher.lookup('int')
                for ctype in param_cls.CTYPES:
                    #print >> sys.stderr, "%s -> int" % ctype.replace('int', alias.name)
                    typehandlers.base.param_type_matcher.register(ctype.replace('int', alias.name), param_cls)
                return_cls, dummy_transf = typehandlers.base.return_type_matcher.lookup('int')
                for ctype in return_cls.CTYPES:
                    #print >> sys.stderr, "%s -> int" % ctype.replace('int', alias.name)
                    typehandlers.base.return_type_matcher.register(ctype.replace('int', alias.name), return_cls)
                continue

            if not isinstance(alias.type, cpptypes.declarated_t):
                continue
            cls = alias.type.declaration
            if not isinstance(cls, class_declaration_t):
                continue # fully defined classes handled further below
            if templates.is_instantiation(cls.decl_string):
                continue # typedef to template instantiations, must be fully defined

            global_annotations, param_annotations = \
                annotations_scanner.get_annotations(cls.location.file_name,
                                                    cls.location.line)
            for hook in self._pre_scan_hooks:
                hook(self, cls, global_annotations, param_annotations)
            if 'ignore' in global_annotations:
                continue

            kwargs = dict()
            self._apply_class_annotations(cls, global_annotations, kwargs)
            kwargs.setdefault("incomplete_type", True)
            kwargs.setdefault("automatic_type_narrowing", False)
            kwargs.setdefault("allow_subclassing", False)
            class_wrapper = CppClass(alias.name, **kwargs)
            class_wrapper.gccxml_definition = cls
            module.add_class(class_wrapper)
            registered_classes[cls] = class_wrapper
            type_registry.register_class(class_wrapper, alias=cls.name)

        ## scan classes
        if outer_class is None:
            unregistered_classes = [cls for cls in
                                    module_namespace.classes(function=self.location_filter,
                                                             recursive=False, allow_empty=True)
                                    if not cls.name.startswith('__')]
        else:
            unregistered_classes = []
            for cls in outer_class.gccxml_definition.classes(function=self.location_filter,
                                                             recursive=False, allow_empty=True):
                if outer_class.gccxml_definition.find_out_member_access_type(cls) != 'public':
                    continue
                if cls.name.startswith('__'):
                    continue
                unregistered_classes.append(cls)

        while unregistered_classes:
            cls = unregistered_classes.pop(0)
            typedef = None

            kwargs = {}
            global_annotations, param_annotations = \
                annotations_scanner.get_annotations(cls.location.file_name,
                                                    cls.location.line)
            for hook in self._pre_scan_hooks:
                hook(self, cls, global_annotations, param_annotations)
            if 'ignore' in global_annotations:
                continue

            if '<' in cls.name:

                for typedef in module_namespace.typedefs(function=self.location_filter,
                                                         recursive=False, allow_empty=True):
                    typedef_type = type_traits.remove_declarated(typedef.type)
                    if typedef_type == cls:
                        break
                else:
                    typedef = None
                
            if len(cls.bases) > 1:
                warnings.warn_explicit(("Class %s ignored because it uses multiple "
                                        "inheritance (not yet supported by pybindgen)"
                                        % cls.decl_string),
                                       Warning, cls.location.file_name, cls.location.line)
                continue
            if cls.bases:
                base_cls = cls.bases[0].related_class
                try:
                    base_class_wrapper = registered_classes[base_cls]
                except KeyError:
                    ## base class not yet registered => postpone this class registration
                    if base_cls not in unregistered_classes:
                        warnings.warn_explicit("Class %s ignored because it uses has a base class (%s) "
                                               "which is not declared."
                                               % (cls.decl_string, base_cls.decl_string),
                                               Warning, cls.location.file_name, cls.location.line)
                        continue
                    unregistered_classes.append(cls)
                    continue
            else:
                base_class_wrapper = None

            ## If this class implicitly converts to another class, but
            ## that other class is not yet registered, postpone.
            for operator in cls.casting_operators(allow_empty=True):
                target_type = type_traits.remove_declarated(operator.return_type)
                if not isinstance(target_type, class_t):
                    continue
                try:
                    type_registry.find_class(operator.return_type.decl_string, '::')
                except KeyError:
                    ok = False
                    break
            else:
                ok = True
            if not ok:
                unregistered_classes.append(cls)
                continue

            self._apply_class_annotations(cls, global_annotations, kwargs)

            custom_template_class_name = None
            template_parameters = ()
            if typedef is None:
                alias = None
                if templates.is_instantiation(cls.decl_string):
                    cls_name, template_parameters = templates.split(cls.name)
                    assert template_parameters
                    if '::' in cls_name:
                        cls_name = cls_name.split('::')[-1]
                    template_instance_names = global_annotations.get('template_instance_names', '')
                    if template_instance_names:
                        for mapping in template_instance_names.split('|'):
                            type_names, name = mapping.split('=>')
                            instance_types = type_names.split(',')
                            if instance_types == template_parameters:
                                custom_template_class_name = name
                                break
                else:
                    cls_name = cls.name
            else:
                cls_name = typedef.name
                alias = '::'.join([module.cpp_namespace_prefix, cls.name])

            class_wrapper = CppClass(cls_name, parent=base_class_wrapper, outer_class=outer_class,
                                     template_parameters=template_parameters,
                                     custom_template_class_name=custom_template_class_name,
                                     **kwargs)
            class_wrapper.gccxml_definition = cls
            module.add_class(class_wrapper)
            registered_classes[cls] = class_wrapper
            type_registry.register_class(class_wrapper, alias)

            for hook in self._post_scan_hooks:
                hook(self, cls, class_wrapper)

            del cls_name

            ## scan for nested classes/enums
            self._scan_namespace_types(module, module_namespace, outer_class=class_wrapper)

            for operator in cls.casting_operators(allow_empty=True):
                target_type = type_traits.remove_declarated(operator.return_type)
                if not isinstance(target_type, class_t):
                    continue
                other_class = type_registry.find_class(operator.return_type.decl_string, '::')
                class_wrapper.implicitly_converts_to(other_class)

        if outer_class is None:
            ## scan nested namespaces (mapped as python submodules)
            for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
                if nested_namespace.name.startswith('__'):
                    continue
                nested_module = Module(name=nested_namespace.name, parent=module, cpp_namespace=nested_namespace.name)
                self._scan_namespace_types(nested_module, nested_namespace)

    def _class_has_virtual_methods(self, cls):
        """return True if cls has at least one virtual method, else False"""
        for member in cls.get_members():
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

    def _scan_class_methods(self, cls, class_wrapper):
        have_trivial_constructor = False
        have_copy_constructor = False

        for member in cls.get_members():
            if isinstance(member, calldef.member_function_t):
                if member.access_type not in ['protected', 'private']:
                    continue

            elif isinstance(member, calldef.constructor_t):
                if member.access_type not in ['protected', 'private']:
                    continue

                if len(member.arguments) == 0:
                    have_trivial_constructor = True

                elif len(member.arguments) == 1:
                    (cpp_class, dummy_is_const, dummy_is_pointer,
                     is_reference, dummy_pointer_is_const) = \
                        type_registry.get_class_type_traits(member.arguments[0].type)
                    if cpp_class is class_wrapper and is_reference:
                        have_copy_constructor = True

        for member in cls.get_members():
            if member.name in [class_wrapper.incref_method, class_wrapper.decref_method,
                               class_wrapper.peekref_method]:
                continue

            global_annotations, parameter_annotations = \
                annotations_scanner.get_annotations(member.location.file_name,
                                                    member.location.line)
            for hook in self._pre_scan_hooks:
                hook(self, member, global_annotations, parameter_annotations)

            if 'ignore' in global_annotations:
                continue

            ## ------------ method --------------------
            if isinstance(member, calldef.member_function_t):
                is_virtual = (member.virtuality != calldef.VIRTUALITY_TYPES.NOT_VIRTUAL)
                pure_virtual = (member.virtuality == calldef.VIRTUALITY_TYPES.PURE_VIRTUAL)

                for key, val in global_annotations.iteritems():
                    if key == 'template_instance_names' \
                            and templates.is_instantiation(member.demangled_name):
                        pass
                    else:
                        warnings.warn_explicit("Annotation '%s=%s' not used (used in %s)"
                                               % (key, val, member),
                                               Warning, member.location.file_name, member.location.line)
                
                try:
                    return_type = type_registry.lookup_return(member.return_type,
                                                              parameter_annotations.get('return', {}))
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                           % (member.return_type.decl_string, member, ex),
                                           Warning, member.location.file_name, member.location.line)
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed(True)
                        class_wrapper.set_helper_class_disabled(True)
                    continue
                arguments = []
                ok = True
                for arg in member.arguments:
                    try:
                        arguments.append(type_registry.lookup_parameter(arg.type, arg.name,
                                                                        parameter_annotations.get(arg.name, {})))
                    except (TypeLookupError, TypeConfigurationError), ex:
                        warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                               % (arg.type.decl_string, arg.name, member, ex),
                                               Warning, member.location.file_name, member.location.line)
                        ok = False
                if not ok:
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed(True)
                        class_wrapper.set_helper_class_disabled(True)
                    continue

                if pure_virtual and not class_wrapper.allow_subclassing:
                    class_wrapper.set_cannot_be_constructed(True)

                custom_template_method_name = None
                if templates.is_instantiation(member.demangled_name):
                    template_parameters = templates.args(member.demangled_name)
                    template_instance_names = global_annotations.get('template_instance_names', '')
                    if template_instance_names:
                        for mapping in template_instance_names.split('|'):
                            type_names, name = mapping.split('=>')
                            instance_types = type_names.split(',')
                            if instance_types == template_parameters:
                                custom_template_method_name = name
                                break
                else:
                    template_parameters = ()

                method_wrapper = CppMethod(return_type, member.name, arguments,
                                           is_const=member.has_const,
                                           is_static=member.has_static,
                                           is_virtual=(is_virtual and class_wrapper.allow_subclassing),
                                           is_pure_virtual=pure_virtual,
                                           template_parameters=template_parameters,
                                           custom_template_method_name=custom_template_method_name,
                                           visibility=member.access_type)
                method_wrapper.gccxml_definition = member
                try:
                    class_wrapper.add_method(method_wrapper)
                except NotSupportedError, ex:
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed(True)
                        class_wrapper.set_helper_class_disabled(True)
                    warnings.warn_explicit("Error adding method %s: %r"
                                           % (member, ex),
                                           Warning, member.location.file_name, member.location.line)
                else:
                    for hook in self._post_scan_hooks:
                        hook(self, member, method_wrapper)

            ## ------------ constructor --------------------
            elif isinstance(member, calldef.constructor_t):
                if member.access_type not in ['public', 'protected']:
                    continue

                if not member.arguments:
                    have_trivial_constructor = True

                arguments = []
                for arg in member.arguments:
                    try:
                        arguments.append(type_registry.lookup_parameter(arg.type, arg.name))
                    except (TypeLookupError, TypeConfigurationError), ex:
                        warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                               % (arg.type.decl_string, arg.name, member, ex),
                                               Warning, member.location.file_name, member.location.line)
                        ok = False
                        break
                else:
                    ok = True
                if not ok:
                    continue
                constructor_wrapper = CppConstructor(arguments, visibility=member.access_type)
                constructor_wrapper.gccxml_definition = member
                class_wrapper.add_constructor(constructor_wrapper)
                for hook in self._post_scan_hooks:
                    hook(self, member, constructor_wrapper)

                if (len(arguments) == 1
                    and isinstance(arguments[0], class_wrapper.ThisClassRefParameter)):
                    have_copy_constructor = True

            ## ------------ attribute --------------------
            elif isinstance(member, variable_t):
                if member.access_type == 'protected':
                    warnings.warn_explicit("%s: protected member variables not yet implemented "
                                           "by PyBindGen."
                                           % member,
                                           Warning, member.location.file_name, member.location.line)
                    continue
                if member.access_type == 'private':
                    continue

                try:
                    return_type = type_registry.lookup_return(member.type)
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                           % (member.type.decl_string, member, ex),
                                           Warning, member.location.file_name, member.location.line)
                    continue
                if member.type_qualifiers.has_static:
                    class_wrapper.add_static_attribute(return_type, member.name,
                                                       is_const=type_traits.is_const(member.type))
                else:
                    class_wrapper.add_instance_attribute(return_type, member.name,
                                                         is_const=type_traits.is_const(member.type))
                ## TODO: invoke post_scan_hooks
            elif isinstance(member, calldef.destructor_t):
                pass

        ## gccxml 0.9, unlike 0.7, does not explicitly report inheritted trivial constructors
        ## thankfully pygccxml comes to the rescue!
        if not have_trivial_constructor:
            if type_traits.has_trivial_constructor(cls):
                class_wrapper.add_constructor(CppConstructor([]))
        if not have_copy_constructor:
            try: # pygccxml > 0.9
                has_copy_constructor = type_traits.has_copy_constructor(cls)
            except AttributeError: # pygccxml <= 0.9
                has_copy_constructor = type_traits.has_trivial_copy(cls)
            if has_copy_constructor:
                class_wrapper.add_constructor(CppConstructor([
                            class_wrapper.ThisClassRefParameter("%s const &" % class_wrapper.full_name,
                                                                'ctor_arg', is_const=True)]))

            
    def _scan_namespace_functions(self, module, module_namespace):
        for fun in module_namespace.free_functions(function=self.location_filter,
                                                   allow_empty=True, recursive=False):
            if fun.name.startswith('__'):
                continue

            global_annotations, parameter_annotations = \
                annotations_scanner.get_annotations(fun.location.file_name,
                                                    fun.location.line)
            for hook in self._pre_scan_hooks:
                hook(self, fun, global_annotations, parameter_annotations)

            as_method = None
            of_class = None
            alt_name = None
            ignore = False
            for name, value in global_annotations.iteritems():
                if name == 'as_method':
                    as_method = value
                elif name == 'of_class':
                    of_class = value
                elif name == 'name':
                    alt_name = value
                elif name == 'ignore':
                    ignore = True
                elif name == 'is_constructor_of':
                    pass
                else:
                    warnings.warn_explicit("Incorrect annotation %s=%s" % (name, value),
                                           Warning, fun.location.file_name, fun.location.line)
            if ignore:
                continue


            is_constructor_of = global_annotations.get("is_constructor_of", None)
            return_annotations = parameter_annotations.get('return', {})
            if is_constructor_of:
                return_annotations['caller_owns_return'] = 'true'
            try:
                return_type = type_registry.lookup_return(fun.return_type, return_annotations)
            except (TypeLookupError, TypeConfigurationError), ex:
                warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                       % (fun.return_type.decl_string, fun, ex),
                                       Warning, fun.location.file_name, fun.location.line)
                continue
            except TypeError, ex:
                warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                       % (fun.return_type.decl_string, fun, ex),
                                       Warning, fun.location.file_name, fun.location.line)
                raise
            arguments = []
            for argnum, arg in enumerate(fun.arguments):
                annotations = parameter_annotations.get(arg.name, {})
                if argnum == 0 and as_method is not None \
                        and isinstance(arg.type, cpptypes.pointer_t):
                    annotations.setdefault("transfer_ownership", "false")
                try:
                    arguments.append(type_registry.lookup_parameter(arg.type, arg.name,
                                                                    annotations))
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                           % (arg.type.decl_string, arg.name, fun, ex),
                                           Warning, fun.location.file_name, fun.location.line)

                    ok = False
                    break
                except TypeError, ex:
                    warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                           % (arg.type.decl_string, arg.name, fun, ex),
                                           Warning, fun.location.file_name, fun.location.line)
                    raise
            else:
                ok = True
            if not ok:
                continue

            if as_method is not None:
                assert of_class is not None
                cpp_class = type_registry.find_class(of_class, (self.module_namespace_name or '::'))
                function_wrapper = Function(return_type, fun.name, arguments)
                cpp_class.add_method(function_wrapper, name=as_method)
                function_wrapper.gccxml_definition = fun
                continue
            if is_constructor_of is not None:
                cpp_class = type_registry.find_class(is_constructor_of, (self.module_namespace_name or '::'))
                function_wrapper = Function(return_type, fun.name, arguments)
                cpp_class.add_constructor(function_wrapper)
                function_wrapper.gccxml_definition = fun
                continue

            if templates.is_instantiation(fun.demangled_name):
                template_parameters = templates.args(fun.demangled_name)
            else:
                template_parameters = ()
                    
            func_wrapper = Function(return_type, fun.name, arguments,
                                    template_parameters=template_parameters)
            func_wrapper.gccxml_definition = fun
            module.add_function(func_wrapper, name=alt_name)
            for hook in self._post_scan_hooks:
                hook(self, fun, func_wrapper)

        ## scan nested namespaces (mapped as python submodules)
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            if nested_namespace.name.startswith('__'):
                continue
            nested_module = module.get_submodule(nested_namespace.name)
            self._scan_namespace_functions(nested_module, nested_namespace)
    

def _test():
    module_parser = ModuleParser('foo', '::')
    module = module_parser.parse(sys.argv[1:])
    if 0:
        out = FileCodeSink(sys.stdout)
        import utils
        utils.write_preamble(out)
        module.generate(out)

if __name__ == '__main__':
    _test()
