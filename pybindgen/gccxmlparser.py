#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os.path
import warnings
import re
from pygccxml import parser
from pygccxml import declarations
from module import Module
from typehandlers.codesink import FileCodeSink, CodeSink, NullCodeSink
import typehandlers.base
from typehandlers.base import ReturnValue, Parameter, TypeLookupError, TypeConfigurationError, NotSupportedError
from pygccxml.declarations.enumeration import enumeration_t
from cppclass import CppClass
from pygccxml.declarations import type_traits
from pygccxml.declarations import cpptypes
from pygccxml.declarations import calldef
from pygccxml.declarations import templates
from pygccxml.declarations.class_declaration import class_declaration_t, class_t
import settings

#from pygccxml.declarations.calldef import \
#    destructor_t, constructor_t, member_function_t
from pygccxml.declarations.variable import variable_t


###
### some patched pygccxml functions, from the type_traits module
###
def remove_pointer(type):
    """removes pointer from the type definition

    If type is not pointer type, it will be returned as is.
    """
    #nake_type = remove_alias( type )
    nake_type = type
    if not type_traits.is_pointer( nake_type ):
        return type
    elif isinstance( nake_type, cpptypes.volatile_t ) and isinstance( nake_type.base, cpptypes.pointer_t ):
        return cpptypes.volatile_t( nake_type.base.base )
    elif isinstance( nake_type, cpptypes.const_t ) and isinstance( nake_type.base, cpptypes.pointer_t ):
        return cpptypes.const_t( nake_type.base.base )
    elif isinstance(nake_type, cpptypes.compound_t) and isinstance( nake_type.base, cpptypes.calldef_type_t ):
        return type
    else:
        if isinstance(nake_type, cpptypes.compound_t):
            return nake_type.base
        else:
            return nake_type

def remove_reference(type):
    """removes reference from the type definition

    If type is not reference type, it will be returned as is.
    """
    #nake_type = remove_alias( type )
    nake_type = type
    if not type_traits.is_reference( nake_type ):
        return type
    else:
        if isinstance(nake_type, cpptypes.compound_t):
            return nake_type.base
        else:
            return nake_type

def remove_const(type):
    """removes const from the type definition

    If type is not const type, it will be returned as is
    """

    #nake_type = remove_alias( type )
    nake_type = type
    if not type_traits.is_const( nake_type ):
        return type
    else:
        if isinstance(nake_type, cpptypes.compound_t):
            return nake_type.base
        else:
            return nake_type
###
### end of patched pygccxml functions
###



class ModuleParserWarning(Warning):
    """
    Base class for all warnings reported here.
    """
class NotSupportedWarning(ModuleParserWarning):
    """
    Warning for pybindgen GccxmlParser, to report something pybindgen does not support.
    """
class WrapperWarning(ModuleParserWarning):
    """
    Warning for pybindgen GccxmlParser, to be used when a C++
    definition cannot be converted to a pybindgen wrapper.
    """
class AnnotationsWarning(ModuleParserWarning):
    """
    Warning for pybindgen GccxmlParser to report a problem in annotations.
    """

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
                                   WrapperWarning, definition.location.file_name,
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

def normalize_class_name(class_name, module_namespace):
    if not class_name.startswith(module_namespace):
        class_name = module_namespace + class_name
    class_name = normalize_name(class_name)
    return class_name


def _pygen_kwargs(kwargs):
    l = []
    for key, val in kwargs.iteritems():
        if isinstance(val, CppClass):
            l.append("%s=root_module[%r]" % (key, val.full_name))
        else:
            l.append("%s=%r" % (key, val))
    return l

def _pygen_args_kwargs(args, kwargs):
    return ", ".join([repr(arg) for arg in args] + _pygen_kwargs(kwargs))

def _pygen_args_kwargs_dict(args, kwargs):
    l = [repr(arg) for arg in args]
    if kwargs:
        l.append("dict(%s)" % ', '.join(_pygen_kwargs(kwargs)))
    return ", ".join(l)

def _pygen_retval(args, kwargs):
    if len(args) == 1 and len(kwargs) == 0:
        return repr(args[0])
    return "retval(%s)" % _pygen_args_kwargs(args, kwargs)

def _pygen_param(args, kwargs):
    return "param(%s)" % _pygen_args_kwargs(args, kwargs)


class GccXmlTypeRegistry(object):
    def __init__(self, root_module):
        """
        @param root_module: the root L{Module} object
        """
        assert isinstance(root_module, Module)
        assert root_module.parent is None
        self.root_module = root_module
        self.ordered_classes = [] # registered classes list, by registration order
        self._root_ns_rx = re.compile(r"(^|\s)(::)")
    
    def class_registered(self, cpp_class):
        assert isinstance(cpp_class, CppClass)
        self.ordered_classes.append(cpp_class)

    def get_type_traits(self, type_info):
        assert isinstance(type_info, cpptypes.type_t)

        debug = False #('int64_t' in type_info.decl_string)

        if debug:
            print >> sys.stderr, "***** type traits for %r" % (type_info.decl_string, )

        is_const = False
        is_reference = False
        is_pointer = 0

        while 1:
            prev_type_info = type_info
            if type_traits.is_pointer(type_info):
                is_pointer += 1
                type_info = remove_pointer(type_info)
            elif type_traits.is_const(type_info):
                warnings.warn("multiple consts not handled")
                is_const = True
                type_info = remove_const(type_info)
            elif type_traits.is_reference(type_info):
                warnings.warn("multiple &'s not handled")
                is_reference = True
                type_info = remove_reference(type_info)
            else:
                break
            if type_info is prev_type_info:
                break

        type_name = normalize_name(type_info.decl_string)
        try:
            cpp_type = self.root_module[type_name]
        except KeyError:
            cpp_type = type_name

        if not isinstance(cpp_type, CppClass):
            cpp_type = type_name

        if debug:
            print >> sys.stderr, "*** > return ", repr((cpp_type, is_const, is_pointer, is_reference))
        return (cpp_type, is_const, is_pointer, is_reference)

    def _fixed_std_type_name(self, type_name):
        decl = self._root_ns_rx.sub('', type_name)
        return decl
        
    def lookup_return(self, type_info, annotations={}):
        assert isinstance(type_info, cpptypes.type_t)
        cpp_type, is_const, is_pointer, is_reference = \
            self.get_type_traits(type_info)

        kwargs = {}
        for name, value in annotations.iteritems():
            if name == 'caller_owns_return':
                kwargs['caller_owns_return'] = annotations_scanner.parse_boolean(value)
            elif name == 'custodian':
                kwargs['custodian'] = int(value)
            else:
                warnings.warn("invalid annotation name %r" % name, AnnotationsWarning)

        if is_const:
            kwargs['is_const'] = True

        if isinstance(cpp_type, CppClass):
            cpp_type = cpp_type.full_name
        else:
            if isinstance(type_traits.remove_declarated(type_info), enumeration_t):
                cpp_type = normalize_name(cpp_type)
            else:
                cpp_type = self._fixed_std_type_name(cpp_type)

        if not is_pointer and not is_reference:
            return (cpp_type,), kwargs

        ## pointer to class
        if is_pointer and not is_reference:
            if is_const and 'caller_owns_return' not in kwargs:
                ## a pointer to const object "usually" means caller_owns_return=False
                ## some guessing going on here, though..
                kwargs['caller_owns_return'] = False
            return (cpp_type + ' *'*is_pointer,), kwargs
            
        ## reference of class
        if not is_pointer and is_reference:
            return (cpp_type + ' *'*is_pointer + '&',), kwargs

        assert 0, "this line should not be reached"

    def lookup_parameter(self, type_info, param_name, annotations={}, default_value=None):
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
                    warnings.warn("invalid direction direction %r" % value, AnnotationsWarning)
            elif name == 'custodian':
                kwargs['custodian'] = int(value)
            elif name == 'array_length':
                kwargs['array_length'] = int(value)
            else:
                warnings.warn("invalid annotation name %r" % name, AnnotationsWarning)

        cpp_type, is_const, is_pointer, is_reference = \
            self.get_type_traits(type_info)

        if is_const:
            kwargs['is_const'] = True
        if default_value:
            kwargs['default_value'] = default_value

        if isinstance(cpp_type, CppClass):
            cpp_type = cpp_type.full_name
        else:
            if isinstance(type_traits.remove_declarated(type_info), enumeration_t):
                cpp_type = normalize_name(cpp_type)
            else:
                cpp_type = self._fixed_std_type_name(cpp_type)

        if not is_pointer and not is_reference:
            return (cpp_type, param_name), kwargs

        ## pointer to class
        if is_pointer and not is_reference:
            if is_const:
                ## a pointer to const object usually means transfer_ownership=False
                kwargs.setdefault('transfer_ownership', False)
            return (cpp_type + ' *'*is_pointer, param_name), kwargs
        
        ## reference to class
        if not is_pointer and is_reference:
            return (cpp_type + ' *'*is_pointer + '&', param_name), kwargs
        assert 0, "this line should not be reached"


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
                                                   AnnotationsWarning, file_name, line_number)
                    continue
                warnings.warn_explicit("could not parse %r" % (annotation_str),
                                       AnnotationsWarning, file_name, line_number)
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
                                           AnnotationsWarning, file_name, line_number+1)



annotations_scanner = AnnotationsScanner()

## ------------------------

class PygenSection(object):
    "Class to hold information about a python generation section"
    def __init__(self, name, code_sink, local_customizations_module=None):
        """
        @param name: section name; this name should be a valid python
        module name; the special name '__main__' is used to denote the
        main section, which comprises the main script itself
        @type name: str

        @param code_sink: code sink that will receive the generated
        code for the section.  Normally the code sink should write to
        a file with the name of the section and a .py extension, to
        allow importing it as module.
        @type code_sink: L{CodeSink}

        @param local_customizations_module: name of the python module
        that may contain local customizations for the section, or
        None.  If not None, PyBindGen will generate code that tries to
        import that module in the respective section and call
        functions on it, or ignore it if the module does not exist.
        @type local_customizations_module: str
        """
        assert isinstance(name, str)
        self.name = name
        assert isinstance(code_sink, CodeSink)
        self.code_sink = code_sink
        assert local_customizations_module is None or isinstance(local_customizations_module, str)
        self.local_customizations_module = local_customizations_module


class PygenClassifier(object):
    def classify(self, pygccxml_definition):
        """
        This is a pure virtual method that must be implemented by
        subclasses.  It will be called by PyBindGen for every API
        definition, and should return a section name.

        @param pygccxml_definition: gccxml definition object
        @returns: section name
        """
        raise NotImplementedError



class ModuleParser(object):
    def __init__(self, module_name, module_namespace_name='::'):
        """
        Creates an object that will be able parse header files and
        create a pybindgen module definition.

        @param module_name: name of the Python module
        @param module_namespace_name: optional C++ namespace name; if
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
        self.type_registry = None
        self._stage = None
        self._pygen_sink = None
        self._pygen_factory = None
        self._anonymous_structs = [] # list of (pygccxml_anonymous_class, outer_pybindgen_class)

    def add_pre_scan_hook(self, hook):
        """
        Add a function to be called right before converting a gccxml
        definition to a PyBindGen wrapper object.  This hook function
        will be called for every scanned type, function, or method,
        and given the a chance to modify the annotations for that
        definition.  It will be called like this:::

          pre_scan_hook(module_parser, pygccxml_definition, global_annotations,
                        parameter_annotations)
        
        where:

           - module_parser -- the ModuleParser (this class) instance
           - pygccxml_definition -- the definition reported by pygccxml
           - global_annotations -- a dicionary containing the "global annotations"
                                 for the definition, i.e. a set of key=value
                                 pairs not associated with any particular
                                 parameter
           - parameter_annotations -- a dicionary containing the "parameter
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
        every scanned type, function, or method.  It will be called like this::

          post_scan_hook(module_parser, pygccxml_definition, pybindgen_wrapper)
        
        where:

           - module_parser -- the ModuleParser (this class) instance
           - pygccxml_definition -- the definition reported by pygccxml
           - pybindgen_wrapper -- a pybindgen object that generates a wrapper,
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

    def parse(self, header_files, include_paths=None, whitelist_paths=None, includes=(),
              pygen_sink=None, pygen_classifier=None):
        """
        parses a set of header files and returns a pybindgen Module instance.
        It is equivalent to calling the following methods:
         1. parse_init(header_files, include_paths, whitelist_paths)
         2. scan_types()
         3. scan_methods()
         4. scan_functions()
         5. parse_finalize()

         The documentation for L{ModuleParser.parse_init} explains the parameters.
        """
        self.parse_init(header_files, include_paths, whitelist_paths, includes, pygen_sink, pygen_classifier)
        self.scan_types()
        self.scan_methods()
        self.scan_functions()
        self.parse_finalize()
        return self.module

    def parse_init(self, header_files, include_paths=None,
                   whitelist_paths=None, includes=(), pygen_sink=None, pygen_classifier=None):
        """
        Prepares to parse a set of header files.  The following
        methods should then be called in order to finish the rest of
        scanning process:
         1. scan_types()
         2. scan_methods()
         2. scan_functions()
         3. parse_finalize()

         @param header_files: header files to parse
         @type header_files: list of string

         @param include_paths: list of include paths
         @type include_paths: list of string

         @param whitelist_paths: additional directories for definitions to be included
           Normally the module parser filters out API definitions that
           have been defined outside one of the header files indicated
           for parsing.  The parameter whitelist_paths instructs the
           module parser to accept definitions defined in another
           header file if such header file is inside one of the
           directories listed by whitelist_paths.
         @type whitelist_paths: list of string

         @param pygen_sink: code sink for python script generation.

           This parameter activates a mode wherein ModuleParser, in
           addition to building in memory API definitions, creates a
           python script that will generate the module, when executed.
           The generated Python script can be human editable and does
           not require pygccxml or gccxml to run, only PyBindGen to be
           installed.

           The pygen parameter can be either:
             1. A single code sink: this will become the main and only script file to be generated
             2. A list of L{PygenSection} objects.  This option
             requires the pygen_classifier to be given.

         @type pygen_sink: L{CodeSink} or list of L{PygenSection} objects

         @param pygen_classifier: the classifier to use when pygen is given and is a dict
        """
        assert isinstance(header_files, list)
        assert isinstance(includes, (list, tuple))
        self._pygen = pygen_sink
        self._pygen_classifier = pygen_classifier
        if isinstance(pygen_sink, list):
            assert isinstance(pygen_classifier, PygenClassifier)
            has_main = False
            for sect in self._pygen:
                if not isinstance(sect, PygenSection):
                    raise TypeError
                if sect.name == '__main__':
                    has_main = True
            if not has_main:
                raise ValueError("missing __main__ section")
        elif pygen_sink is None:
            pass
        else:
            assert isinstance(pygen_sink, CodeSink)

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
        for inc in includes:
            self.module.add_include(inc)

        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("from pybindgen import Module, FileCodeSink, write_preamble, param, retval")
            pygen_sink.writeln()

        pygen_sink = self._get_main_pygen_sink()
        if pygen_sink:
            pygen_sink.writeln("""
import pybindgen.settings
import warnings

class ErrorHandler(pybindgen.settings.ErrorHandler):
    def handle_error(self, wrapper, exception, traceback_):
        warnings.warn("exception %r in wrapper %s" % (exception, wrapper))
        return True
pybindgen.settings.error_handler = ErrorHandler()

""")
            pygen_sink.writeln("import sys")
            if isinstance(self._pygen, list):
                for sect in self._pygen:
                    if sect.name == '__main__':
                        continue
                    pygen_sink.writeln("import %s" % sect.name)
            pygen_sink.writeln()
            pygen_sink.writeln("def module_init():")
            pygen_sink.indent()
            pygen_sink.writeln("root_module = Module(%r, cpp_namespace=%r)"
                               % (self.module_name, self.module_namespace.decl_string))
            for inc in includes:
                pygen_sink.writeln("root_module.add_include(%r)" % inc)
            pygen_sink.writeln("return root_module")
            pygen_sink.unindent()
            pygen_sink.writeln()

        self.type_registry = GccXmlTypeRegistry(self.module)
        self._stage = 'init'

    def _get_main_pygen_sink(self):
        if isinstance (self._pygen, CodeSink):
            return self._pygen
        elif isinstance(self._pygen, list):
            for sect in self._pygen:
                if sect.name == '__main__':
                    return sect.code_sink
        else:
            return None

    def _get_all_pygen_sinks(self):
        if isinstance (self._pygen, CodeSink):
            return [self._pygen]
        elif isinstance(self._pygen, list):
            return [sect.code_sink for sect in self._pygen]
        else:
            return []

    def _get_pygen_sink_for_definition(self, pygccxml_definition):
        if self._pygen_classifier is None:
            return self._pygen
        else:
            section = self._pygen_classifier.classify(pygccxml_definition)
            for sect in self._pygen:
                if sect is section or sect.name == section:
                    return sect.code_sink
            else:
                raise ValueError("CodeSink for section %r not available" % section)

    def scan_types(self):
        self._stage = 'scan types'
        self._registered_classes = {} # class_t -> CppClass
        self._scan_namespace_types(self.module, self.module_namespace, pygen_register_function_name="register_types")
        self._types_scanned = True

    def scan_methods(self):
        self._stage = 'scan methods'
        assert self._types_scanned
        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("def register_methods(root_module):")
            pygen_sink.indent()

        for class_wrapper in self.type_registry.ordered_classes:
            if isinstance(class_wrapper.gccxml_definition, class_declaration_t):
                continue # skip classes not fully defined
            pygen_sink =  self._get_pygen_sink_for_definition(class_wrapper.gccxml_definition)
            if pygen_sink:
                register_methods_func = "register_%s_methods"  % (class_wrapper.mangled_full_name,)
                pygen_sink.writeln("%s(root_module, root_module[%r])" % (register_methods_func, class_wrapper.full_name))

        for pygen_sink in self._get_all_pygen_sinks():
            if pygen_sink is self._get_main_pygen_sink() and isinstance(self._pygen, list):
                for sect in self._pygen:
                    if sect.name == '__main__':
                        continue
                    pygen_sink.writeln("root_module.begin_section(%r)" % sect.name)
                    pygen_sink.writeln("%s.register_methods(root_module)" % sect.name)
                    if sect.local_customizations_module:
                        pygen_sink.writeln("\ntry:\n"
                                           "    import %s\n"
                                           "except ImportError:\n"
                                           "    pass\n"
                                           "else:\n"
                                           "    %s.register_methods(root_module)\n"
                                           % (sect.local_customizations_module, sect.local_customizations_module))
                    pygen_sink.writeln("root_module.end_section(%r)" % sect.name)

            pygen_sink.writeln("return")
            pygen_sink.unindent()
            pygen_sink.writeln()

        for class_wrapper in self.type_registry.ordered_classes:
            if isinstance(class_wrapper.gccxml_definition, class_declaration_t):
                continue # skip classes not fully defined
            register_methods_func = "register_%s_methods"  % (class_wrapper.mangled_full_name,)

            pygen_sink =  self._get_pygen_sink_for_definition(class_wrapper.gccxml_definition)
            if pygen_sink:
                pygen_sink.writeln("def %s(root_module, cls):" % (register_methods_func,))
                pygen_sink.indent()
            ## Add attributes from inner anonymous to each outer class (LP#237054)
            for anon_cls, wrapper in self._anonymous_structs:
                if wrapper is class_wrapper:
                    self._scan_class_methods(anon_cls, wrapper, pygen_sink)
            self._scan_class_methods(class_wrapper.gccxml_definition, class_wrapper, pygen_sink)

            if pygen_sink:
                pygen_sink.writeln("return")
                pygen_sink.unindent()
                pygen_sink.writeln()


    def parse_finalize(self):
        annotations_scanner.warn_unused_annotations()
        pygen_sink = self._get_main_pygen_sink()
        if pygen_sink:
            pygen_sink.writeln("def main():")
            pygen_sink.indent()
            pygen_sink.writeln("out = FileCodeSink(sys.stdout)")
            pygen_sink.writeln("root_module = module_init()")
            pygen_sink.writeln("register_types(root_module)")
            pygen_sink.writeln("register_methods(root_module)")
            pygen_sink.writeln("register_functions(root_module)")
            pygen_sink.writeln("write_preamble(out)")
            pygen_sink.writeln("root_module.generate(out)")
            pygen_sink.unindent()
            pygen_sink.writeln()
            pygen_sink.writeln("if __name__ == '__main__':\n    main()")
            pygen_sink.writeln()

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
            elif name == 'pygen_comment':
                pass
            else:
                warnings.warn_explicit("Class annotation %r ignored" % name,
                                       AnnotationsWarning, cls.location.file_name, cls.location.line)
                
        if isinstance(cls, class_t):
            if self._class_has_virtual_methods(cls):
                kwargs.setdefault('allow_subclassing', True)

            if not type_traits.has_public_destructor(cls):
                kwargs.setdefault('is_singleton', True)

    def _scan_namespace_types(self, module, module_namespace, outer_class=None, pygen_register_function_name=None):
        root_module = module.get_root()

        if pygen_register_function_name:
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.writeln("def %s(module):" % pygen_register_function_name)
                pygen_sink.indent()
                pygen_sink.writeln("root_module = module.get_root()")
                pygen_sink.writeln()
                if pygen_sink is self._get_main_pygen_sink() and isinstance(self._pygen, list):
                    for section in self._pygen:
                        if section.name == '__main__':
                            continue
                        if pygen_register_function_name == "register_types":
                            pygen_sink.writeln("root_module.begin_section(%r)" % section.name)
                            pygen_sink.writeln("%s.%s(module)" % (section.name, pygen_register_function_name))
                            if section.local_customizations_module:
                                pygen_sink.writeln("\ntry:\n"
                                                   "    import %s\n"
                                                   "except ImportError:\n"
                                                   "    pass\n"
                                                   "else:\n"
                                                   "    %s.register_types(module)\n"
                                                   % (section.local_customizations_module, section.local_customizations_module))
                            pygen_sink.writeln("root_module.end_section(%r)" % section.name)

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
                                           NotSupportedWarning, enum.location.file_name, enum.location.line)
                    continue
                enums.append(enum)

        for enum in enums:

            global_annotations, param_annotations = \
                annotations_scanner.get_annotations(enum.location.file_name,
                                                    enum.location.line)
            for hook in self._pre_scan_hooks:
                hook(self, enum, global_annotations, param_annotations)
            if 'ignore' in global_annotations:
                continue

            enum_values_repr = '[' + ', '.join([repr(name) for name, dummy_val in enum.values]) + ']'
            l = [repr(enum.name), enum_values_repr]
            if outer_class is not None:
                l.append('outer_class=root_module[%r]' % outer_class.full_name)
            pygen_sink = self._get_pygen_sink_for_definition(enum)
            if pygen_sink:
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                pygen_sink.writeln('module.add_enum(%s)' % ', '.join(l))

            module.add_enum(enum.name, [name for name, dummy_val in enum.values],
                            outer_class=outer_class)

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

            pygen_sink = self._get_pygen_sink_for_definition(cls)
            if pygen_sink:
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                pygen_sink.writeln("module.add_class(%s)" %
                                   ", ".join([repr(alias.name)] + _pygen_kwargs(kwargs)))

            class_wrapper = module.add_class(alias.name, **kwargs)

            class_wrapper.gccxml_definition = cls
            self._registered_classes[cls] = class_wrapper
            if cls.name != alias.name:
                class_wrapper.register_alias(normalize_name(cls.name))
            self.type_registry.class_registered(class_wrapper)

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

        def postpone_class(cls, reason):
            ## detect the case of a class being postponed many times; that
            ## is almost certainly an error and a sign of an infinite
            ## loop.
            count = getattr(cls, "_pybindgen_postpone_count", 0)
            count += 1
            cls._pybindgen_postpone_count = count
            if count >= 100:
                raise AssertionError("The class %s registration is being postponed for "
                                     "the %ith time (last reason: %r, current reason: %r);"
                                     " something is wrong, please file a bug report"
                                     " (https://bugs.launchpad.net/pybindgen/+filebug) with a test case."
                                     % (cls, cls._pybindgen_postpone_reason, reason))
            cls._pybindgen_postpone_reason = reason
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

            if not cls.name:
                if outer_class is None:
                    warnings.warn_explicit(("Class %s ignored: anonymous structure not inside a named structure/union."
                                            % cls.decl_string),
                                           NotSupportedWarning, cls.location.file_name, cls.location.line)
                    continue

                self._anonymous_structs.append((cls, outer_class))
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
                                       NotSupportedWarning, cls.location.file_name, cls.location.line)
                continue
            if cls.bases:
                base_cls = cls.bases[0].related_class
                try:
                    base_class_wrapper = self._registered_classes[base_cls]
                except KeyError:
                    ## base class not yet registered => postpone this class registration
                    if base_cls not in unregistered_classes:
                        warnings.warn_explicit("Class %s ignored because it uses a base class (%s) "
                                               "which is not declared."
                                               % (cls.decl_string, base_cls.decl_string),
                                               ModuleParserWarning, cls.location.file_name, cls.location.line)
                        continue
                    postpone_class(cls, "waiting for base class %s to be registered first" % base_cls)
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
                    dummy = root_module[normalize_class_name(operator.return_type.decl_string, '::')]
                except KeyError:
                    ok = False
                    break
            else:
                ok = True
            if not ok:
                postpone_class(cls, ("waiting for implicit conversion target class %s to be registered first"
                                     % (operator.return_type.decl_string,)))
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

            if base_class_wrapper is not None:
                kwargs["parent"] = base_class_wrapper
            if outer_class is not None:
                kwargs["outer_class"] = outer_class
            if template_parameters:
                kwargs["template_parameters"] = template_parameters
            if custom_template_class_name:
                kwargs["custom_template_class_name"] = custom_template_class_name

            pygen_sink = self._get_pygen_sink_for_definition(cls)
            if pygen_sink:
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                pygen_sink.writeln("module.add_class(%s)" %
                                   ", ".join([repr(cls_name)] + _pygen_kwargs(kwargs)))

            class_wrapper = module.add_class(cls_name, **kwargs)
            class_wrapper.gccxml_definition = cls
            self._registered_classes[cls] = class_wrapper
            if alias:
                class_wrapper.register_alias(normalize_name(alias))
            self.type_registry.class_registered(class_wrapper)

            for hook in self._post_scan_hooks:
                hook(self, cls, class_wrapper)

            del cls_name

            ## scan for nested classes/enums
            self._scan_namespace_types(module, module_namespace, outer_class=class_wrapper)

            for operator in cls.casting_operators(allow_empty=True):
                target_type = type_traits.remove_declarated(operator.return_type)
                if not isinstance(target_type, class_t):
                    continue
                #other_class = type_registry.find_class(operator.return_type.decl_string, '::')
                other_class = root_module[normalize_class_name(operator.return_type.decl_string, '::')]
                class_wrapper.implicitly_converts_to(other_class)
                if pygen_sink:
                    if 'pygen_comment' in global_annotations:
                        pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                    pygen_sink.writeln("root_module[%r].implicitly_converts_to(root_module[%r])"
                                       % (class_wrapper.full_name, other_class.full_name))

        pygen_function_closed = False
        if outer_class is None:
            ## scan nested namespaces (mapped as python submodules)
            nested_modules = []
            for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
                if nested_namespace.name.startswith('__'):
                    continue

                if pygen_register_function_name:
                    nested_module = module.add_cpp_namespace(nested_namespace.name)
                    nested_modules.append(nested_module)
                    for pygen_sink in self._get_all_pygen_sinks():
                        pygen_sink.writeln()
                        pygen_sink.writeln("## Register a nested module for the namespace %s" % nested_namespace.name)
                        pygen_sink.writeln()
                        pygen_sink.writeln("nested_module = module.add_cpp_namespace(%r)" % nested_namespace.name)
                        nested_module_type_init_func = "register_types_" + "_".join(nested_module.get_namespace_path())
                        pygen_sink.writeln("%s(nested_module)" % nested_module_type_init_func)
                        pygen_sink.writeln()
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.unindent()
                pygen_sink.writeln()
            pygen_function_closed = True

            ## scan nested namespaces (mapped as python submodules)
            for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
                if nested_namespace.name.startswith('__'):
                    continue

                if pygen_register_function_name:
                    nested_module = nested_modules.pop(0)
                    nested_module_type_init_func = "register_types_" + "_".join(nested_module.get_namespace_path())
                    self._scan_namespace_types(nested_module, nested_namespace,
                                               pygen_register_function_name=nested_module_type_init_func)
            assert not nested_modules # make sure all have been consumed by the second for loop

        if pygen_register_function_name and not pygen_function_closed:
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.unindent()
                pygen_sink.writeln()


    def _class_has_virtual_methods(self, cls):
        """return True if cls has at least one virtual method, else False"""
        for member in cls.get_members():
            if isinstance(member, calldef.member_function_t):
                if member.virtuality != calldef.VIRTUALITY_TYPES.NOT_VIRTUAL:
                    return True
        return False

    def _is_ostream(self, cpp_type):
        return (isinstance (cpp_type, cpptypes.reference_t)
                and not isinstance(cpp_type.base, cpptypes.const_t)
                and str(cpp_type.base) == 'std::ostream')

    def _scan_class_methods(self, cls, class_wrapper, pygen_sink):
        have_trivial_constructor = False
        have_copy_constructor = False
        has_output_stream_operator = False


        for op in self.module_namespace.free_operators(function=self.location_filter,
                                                       allow_empty=True, 
                                                       recursive=True):
            if self._is_ostream (op.return_type) \
                    and len (op.arguments) >= 2 \
                    and self._is_ostream (op.arguments[0].type) \
                    and type_traits.is_convertible (cls, op.arguments[1].type):
                has_output_stream_operator = True

        for op in cls.member_operators(function=self.location_filter,
                                       allow_empty=True, 
                                       recursive=True):
            if self._is_ostream (op.return_type) \
                    and len (op.arguments) >= 2 \
                    and self._is_ostream (op.arguments[0].type) \
                    and type_traits.is_convertible (cls, op.arguments[1].type):
                has_output_stream_operator = True

        if pygen_sink is None:
            pygen_sink = NullCodeSink()

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
                    (cpp_type, dummy_is_const, dummy_is_pointer,
                     is_reference) = \
                        self.type_registry.get_type_traits(member.arguments[0].type)
                    if cpp_type is class_wrapper and is_reference:
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
                    elif key == 'pygen_comment':
                        pass
                    else:
                        warnings.warn_explicit("Annotation '%s=%s' not used (used in %s)"
                                               % (key, val, member),
                                               AnnotationsWarning, member.location.file_name, member.location.line)

                ## --- pygen ---
                return_type_spec = self.type_registry.lookup_return(member.return_type,
                                                                    parameter_annotations.get('return', {}))
                argument_specs = []
                for arg in member.arguments:
                    argument_specs.append(self.type_registry.lookup_parameter(arg.type, arg.name,
                                                                              parameter_annotations.get(arg.name, {}),
                                                                              arg.default_value))
                    
                

                if pure_virtual and not class_wrapper.allow_subclassing:
                    class_wrapper.set_cannot_be_constructed("pure virtual method and subclassing disabled")
                    #self.pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method not wrapped")')

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

                kwargs = {}
                if member.has_const:
                    kwargs['is_const'] = True
                if member.has_static:
                    kwargs['is_static'] = True
                if is_virtual:
                    kwargs['is_virtual'] = True
                if pure_virtual:
                    kwargs['is_pure_virtual'] = True
                if template_parameters:
                    kwargs['template_parameters'] = template_parameters
                if custom_template_method_name:
                    kwargs['custom_template_method_name'] = custom_template_method_name
                if member.access_type != 'public':
                    kwargs['visibility'] = member.access_type

                ## ignore methods that are private and not virtual or
                ## pure virtual, as they do not affect the bindings in
                ## any way and only clutter the generated python script.
                if (kwargs.get('visibility', 'public') == 'private'
                    and not (kwargs.get('is_virtual', False) or kwargs.get('is_pure_virtual', False))):
                    continue

                ## --- pygen ---
                arglist_repr = ("[" + ', '.join([_pygen_param(args_, kwargs_) for (args_, kwargs_) in argument_specs]) +  "]")
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                pygen_sink.writeln("cls.add_method(%s)" %
                                   ", ".join(
                        [repr(member.name), _pygen_retval(return_type_spec[0], return_type_spec[1]), arglist_repr]
                        + _pygen_kwargs(kwargs)))

                ## --- realize the return type and parameters
                try:
                    return_type = ReturnValue.new(*return_type_spec[0], **return_type_spec[1])
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                           % (member.return_type.decl_string, member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed("pure virtual method not wrapped")
                        class_wrapper.set_helper_class_disabled(True)
                        #self.pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method not wrapped")')
                        #self.pygen_sink.writeln('cls.set_helper_class_disabled(True)')
                    continue
                arguments = []
                ok = True
                for arg in argument_specs:
                    try:
                        arguments.append(Parameter.new(*arg[0], **arg[1]))
                    except (TypeLookupError, TypeConfigurationError), ex:
                        warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                               % (arg[0][0], arg[0][1], member, ex),
                                               WrapperWarning, member.location.file_name, member.location.line)
                        ok = False
                if not ok:
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed("pure virtual method not wrapped")
                        class_wrapper.set_helper_class_disabled(True)
                        #self.pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method not wrapped")')
                        #self.pygen_sink.writeln('cls.set_helper_class_disabled(True)')
                    continue


                try:
                    method_wrapper = class_wrapper.add_method(member.name, return_type, arguments, **kwargs)
                    method_wrapper.gccxml_definition = member
                except NotSupportedError, ex:
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed("pure virtual method %r not wrapped" % member.name)
                        class_wrapper.set_helper_class_disabled(True)
                        pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method %%r not wrapped" %% %r)'
                                           % member.name)
                        pygen_sink.writeln('cls.set_helper_class_disabled(True)')

                    warnings.warn_explicit("Error adding method %s: %r"
                                           % (member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                except ValueError, ex:
                    warnings.warn_explicit("Error adding method %s: %r"
                                           % (member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                    raise
                else: # no exception, add method succeeded
                    for hook in self._post_scan_hooks:
                        hook(self, member, method_wrapper)
                

            ## ------------ constructor --------------------
            elif isinstance(member, calldef.constructor_t):
                if member.access_type not in ['public', 'protected']:
                    continue

                if not member.arguments:
                    have_trivial_constructor = True

                argument_specs = []
                for arg in member.arguments:
                    argument_specs.append(self.type_registry.lookup_parameter(arg.type, arg.name,
                                                                              default_value=arg.default_value))

                arglist_repr = ("[" + ', '.join([_pygen_param(args_, kwargs_) for (args_, kwargs_) in argument_specs]) +  "]")
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                pygen_sink.writeln("cls.add_constructor(%s)" %
                                   ", ".join([arglist_repr, "visibility=%r" % member.access_type]))


                arguments = []
                for a, kw in argument_specs:
                    try:
                        arguments.append(Parameter.new(*a, **kw))
                    except (TypeLookupError, TypeConfigurationError), ex:
                        warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                               % (arg.type.decl_string, arg.name, member, ex),
                                               WrapperWarning, member.location.file_name, member.location.line)
                        ok = False
                        break
                else:
                    ok = True
                if not ok:
                    continue
                constructor_wrapper = class_wrapper.add_constructor(arguments, visibility=member.access_type)
                constructor_wrapper.gccxml_definition = member
                for hook in self._post_scan_hooks:
                    hook(self, member, constructor_wrapper)

                if (len(arguments) == 1
                    and isinstance(arguments[0], class_wrapper.ThisClassRefParameter)):
                    have_copy_constructor = True

            ## ------------ attribute --------------------
            elif isinstance(member, variable_t):
                if not member.name:
                    continue # anonymous structure
                if member.access_type == 'protected':
                    warnings.warn_explicit("%s: protected member variables not yet implemented "
                                           "by PyBindGen."
                                           % member,
                                           NotSupportedWarning, member.location.file_name, member.location.line)
                    continue
                if member.access_type == 'private':
                    continue

                return_type_spec = self.type_registry.lookup_return(member.type)

                ## pygen...
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                if member.type_qualifiers.has_static:
                    pygen_sink.writeln("cls.add_static_attribute(%r, %s, is_const=%r)" %
                                       (member.name, _pygen_retval(*return_type_spec),
                                        type_traits.is_const(member.type)))
                else:
                    pygen_sink.writeln("cls.add_instance_attribute(%r, %s, is_const=%r)" %
                                       (member.name, _pygen_retval(*return_type_spec),
                                        type_traits.is_const(member.type)))
                    
                ## convert the return value
                try:
                    return_type = ReturnValue.new(*return_type_spec[0], **return_type_spec[1])
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                           % (member.type.decl_string, member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                    continue

                if member.type_qualifiers.has_static:
                    class_wrapper.add_static_attribute(member.name, return_type,
                                                       is_const=type_traits.is_const(member.type))
                else:
                    class_wrapper.add_instance_attribute(member.name, return_type,
                                                         is_const=type_traits.is_const(member.type))
                ## TODO: invoke post_scan_hooks
            elif isinstance(member, calldef.destructor_t):
                pass

        ## gccxml 0.9, unlike 0.7, does not explicitly report inheritted trivial constructors
        ## thankfully pygccxml comes to the rescue!
        if not have_trivial_constructor:
            if type_traits.has_trivial_constructor(cls):
                class_wrapper.add_constructor([])
                pygen_sink.writeln("cls.add_constructor([])")
                
        if not have_copy_constructor:
            try: # pygccxml > 0.9
                has_copy_constructor = type_traits.has_copy_constructor(cls)
            except AttributeError: # pygccxml <= 0.9
                has_copy_constructor = type_traits.has_trivial_copy(cls)
            if has_copy_constructor:
                class_wrapper.add_constructor([
                            class_wrapper.ThisClassRefParameter("%s &" % class_wrapper.full_name,
                                                                'ctor_arg', is_const=True)])
        if has_output_stream_operator:
            class_wrapper.add_output_stream_operator()
            pygen_sink.writeln("cls.add_output_stream_operator()")


    def scan_functions(self):
        self._stage = 'scan functions'
        assert self._types_scanned
        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("def register_functions(root_module):")
            pygen_sink.indent()
            pygen_sink.writeln("module = root_module")
            if pygen_sink is self._get_main_pygen_sink() and isinstance(self._pygen, list):
                for section in self._pygen:
                    if section.name == '__main__':
                        continue
                    pygen_sink.writeln("root_module.begin_section(%r)" % section.name)
                    pygen_sink.writeln("%s.register_functions(root_module)" % section.name)
                    if section.local_customizations_module:
                        pygen_sink.writeln("\ntry:\n"
                                           "    import %s\n"
                                           "except ImportError:\n"
                                           "    pass\n"
                                           "else:\n"
                                           "    %s.register_functions(root_module)\n"
                                           % (section.local_customizations_module, section.local_customizations_module))
                    pygen_sink.writeln("root_module.end_section(%r)" % section.name)
        self._scan_namespace_functions(self.module, self.module_namespace)
            
    def _scan_namespace_functions(self, module, module_namespace):
        root_module = module.get_root()

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
                elif name == 'pygen_comment':
                    pass
                else:
                    warnings.warn_explicit("Incorrect annotation %s=%s" % (name, value),
                                           AnnotationsWarning, fun.location.file_name, fun.location.line)
            if ignore:
                continue


            is_constructor_of = global_annotations.get("is_constructor_of", None)
            return_annotations = parameter_annotations.get('return', {})
            if is_constructor_of:
                return_annotations['caller_owns_return'] = 'true'

            params_ok = True
            return_type_spec = self.type_registry.lookup_return(fun.return_type, return_annotations)
            try:
                return_type = ReturnValue.new(*return_type_spec[0], **return_type_spec[1])
            except (TypeLookupError, TypeConfigurationError), ex:
                warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                       % (fun.return_type.decl_string, fun, ex),
                                       WrapperWarning, fun.location.file_name, fun.location.line)
                params_ok = False
            except TypeError, ex:
                warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                       % (fun.return_type.decl_string, fun, ex),
                                       WrapperWarning, fun.location.file_name, fun.location.line)
                raise
            argument_specs = []
            arguments = []
            for argnum, arg in enumerate(fun.arguments):
                annotations = parameter_annotations.get(arg.name, {})
                if argnum == 0 and as_method is not None \
                        and isinstance(arg.type, cpptypes.pointer_t):
                    annotations.setdefault("transfer_ownership", "false")
                    
                spec = self.type_registry.lookup_parameter(arg.type, arg.name,
                                                           annotations,
                                                           default_value=arg.default_value)
                argument_specs.append(spec)
                try:
                    arguments.append(Parameter.new(*spec[0], **spec[1]))
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                           % (arg.type.decl_string, arg.name, fun, ex),
                                           WrapperWarning, fun.location.file_name, fun.location.line)

                    params_ok = False
                except TypeError, ex:
                    warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                           % (arg.type.decl_string, arg.name, fun, ex),
                                           WrapperWarning, fun.location.file_name, fun.location.line)
                    raise

            arglist_repr = ("[" + ', '.join([_pygen_param(*arg)  for arg in argument_specs]) +  "]")
            retval_repr = _pygen_retval(*return_type_spec)

            if as_method is not None:
                assert of_class is not None
                cpp_class = root_module[normalize_class_name(of_class, (self.module_namespace_name or '::'))]

                pygen_sink = self._get_pygen_sink_for_definition(fun)
                if pygen_sink:
                    if 'pygen_comment' in global_annotations:
                        pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                    pygen_sink.writeln("root_module[%r].add_function_as_method(%s, custom_name=%r)" %
                                       (cpp_class.full_name,
                                        ", ".join([repr(fun.name), retval_repr, arglist_repr]),
                                        as_method))
                if params_ok:
                    function_wrapper = cpp_class.add_function_as_method(fun.name, return_type, arguments, custom_name=as_method)
                    function_wrapper.gccxml_definition = fun

                continue

            if is_constructor_of is not None:
                #cpp_class = type_registry.find_class(is_constructor_of, (self.module_namespace_name or '::'))
                cpp_class = root_module[normalize_class_name(is_constructor_of, (self.module_namespace_name or '::'))]

                pygen_sink = self._get_pygen_sink_for_definition(fun)
                if pygen_sink:
                    if 'pygen_comment' in global_annotations:
                        pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                    pygen_sink.writeln("root_module[%r].add_function_as_constructor(%s)" %
                                       (cpp_class.full_name,
                                        ", ".join([repr(fun.name), retval_repr, arglist_repr]),))

                if params_ok:
                    function_wrapper = cpp_class.add_function_as_constructor(fun.name, return_type, arguments)
                    function_wrapper.gccxml_definition = fun


                continue

            kwargs = {}

            if templates.is_instantiation(fun.demangled_name):
                kwargs['template_parameters'] = templates.args(fun.demangled_name)
                
            if alt_name:
                kwargs['custom_name'] = alt_name

            pygen_sink = self._get_pygen_sink_for_definition(fun)
            if pygen_sink:
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                pygen_sink.writeln("module.add_function(%s)" %
                                   (", ".join([repr(fun.name), retval_repr, arglist_repr] + _pygen_kwargs(kwargs))))

            if params_ok:
                func_wrapper = module.add_function(fun.name, return_type, arguments, **kwargs)
                func_wrapper.gccxml_definition = fun
                for hook in self._post_scan_hooks:
                    hook(self, fun, func_wrapper)


        ## scan nested namespaces (mapped as python submodules)
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            if nested_namespace.name.startswith('__'):
                continue
            nested_module = module.get_submodule(nested_namespace.name)
            
            nested_module_pygen_func = "register_functions_" + "_".join(nested_module.get_namespace_path())
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.writeln("%s(module.get_submodule(%r), root_module)" %
                                   (nested_module_pygen_func, nested_namespace.name))

        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("return")
            pygen_sink.unindent()
            pygen_sink.writeln()
    
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            if nested_namespace.name.startswith('__'):
                continue
            nested_module = module.get_submodule(nested_namespace.name)

            nested_module_pygen_func = "register_functions_" + "_".join(nested_module.get_namespace_path())
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.writeln("def %s(module, root_module):" % nested_module_pygen_func)
                pygen_sink.indent()

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
