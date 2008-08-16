"""
Wrap C++ STL containers
"""

#import warnings

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase, \
    Parameter, ReturnValue, param_type_matcher, return_type_matcher
from typehandlers import codesink
from pytypeobject import PyTypeObject
import settings
import utils


class IterNextWrapper(ForwardWrapperBase):
    '''
    tp_iternext wrapper
    '''
    def __init__(self, container):
        """
        value_type -- a ReturnValue object handling the value type;
        container -- the L{Container}
        """
        super(IterNextWrapper, self).__init__(
            container.value_type, [], "return NULL;", "return NULL;", no_c_retval=True)
        assert isinstance(container, Container)
        self.container = container
        self.c_function_name = "_wrap_%s__tp_iternext" % (self.container.iter_pystruct)
        container.value_type.value = "*(*self->iterator)++"

    def generate_call(self):
        "virtual method implementation; do not call"
        self.before_call.write_error_check("*self->iterator == self->container->obj->end()",
                                           "PyErr_SetNone(PyExc_StopIteration);")
        

    def generate(self, code_sink):
        """
        code_sink -- a CodeSink instance that will receive the generated code
        """
        
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject* %s(%s *self)" % (self.c_function_name,
                                                             self.container.iter_pystruct))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')


class Container(object):
    def __init__(self, name, value_type, outer_class=None, template_parameters=(), custom_name=None):
        self.name = utils.ascii(name)
        self.full_name = None
        self.template_parameters = template_parameters
        self._module = None
        self.outer_class = outer_class
        self.mangled_name = None
        self.mangled_full_name = None
        self.custom_name = custom_name
        self._pystruct = None
        self.pytypestruct = "***GIVE ME A NAME***"
        self.pytype = PyTypeObject()

        self.iter_pytypestruct = "***GIVE ME A NAME***"
        self.iter_pytype = PyTypeObject()
        self._iter_pystruct = None

        value_type = utils.eval_retval(value_type, self)
        self.value_type = value_type
        self.python_to_c_converter = None

        if name != 'dummy':
            ## register type handlers

            class ThisContainerParameter(ContainerParameter):
                """Register this C++ container as pass-by-value parameter"""
                CTYPES = []
                container_type = self
            self.ThisContainerParameter = ThisContainerParameter
            try:
                param_type_matcher.register(name, self.ThisContainerParameter)
            except ValueError:
                pass

            class ThisContainerReturn(ContainerReturnValue):
                """Register this C++ container as value return"""
                CTYPES = []
                container_type = self
            self.ThisContainerReturn = ThisContainerReturn
            self.ThisContainerRefReturn = ThisContainerReturn
            try:
                return_type_matcher.register(name, self.ThisContainerReturn)
                return_type_matcher.register(name, self.ThisContainerRefReturn)
            except ValueError:
                pass

    def __repr__(self):
        return "<pybindgen.Container %r>" % self.full_name
    
    def get_module(self):
        """Get the Module object this type belongs to"""
        return self._module

    def set_module(self, module):
        """Set the Module object this type belongs to"""
        self._module = module
        self._update_names()

    module = property(get_module, set_module)
    
    def get_pystruct(self):
        if self._pystruct is None:
            raise ValueError
        return self._pystruct
    pystruct = property(get_pystruct)

    def get_iter_pystruct(self):
        if self._iter_pystruct is None:
            raise ValueError
        return self._iter_pystruct
    iter_pystruct = property(get_iter_pystruct)

    def _update_names(self):
        
        prefix = settings.name_prefix.capitalize()

        if self.outer_class is None:
            if self._module.cpp_namespace_prefix:
                if self._module.cpp_namespace_prefix == '::':
                    self.full_name = '::' + self.name
                else:
                    self.full_name = self._module.cpp_namespace_prefix + '::' + self.name
            else:
                self.full_name = self.name
        else:
            self.full_name = '::'.join([self.outer_class.full_name, self.name])

        def make_upper(s):
            if s and s[0].islower():
                return s[0].upper()+s[1:]
            else:
                return s

        def mangle(s):
            "make a name Like<This,and,That> look Like__lt__This_and_That__gt__"
            s = s.replace('<', '__lt__').replace('>', '__gt__').replace(',', '_')
            s = s.replace(' ', '_').replace('&', '__amp__').replace('*', '__star__')
            return s
        
        def flatten(name):
            "make a name like::This look LikeThis"
            return ''.join([make_upper(mangle(s)) for s in name.split('::')])

        self.mangled_name = flatten(self.name)
        self.mangled_full_name = flatten(self.full_name)

        if self.template_parameters:
            self.full_name += "< %s >" % (', '.join(self.template_parameters))
            mangled_template_params = '__' + '_'.join([flatten(s) for s in self.template_parameters])
            self.mangled_name += mangled_template_params
            self.mangled_full_name += mangled_template_params

        self._pystruct = "Py%s%s" % (prefix, self.mangled_full_name)
        self.pytypestruct = "Py%s%s_Type" % (prefix,  self.mangled_full_name)

        self._iter_pystruct = "Py%s%sIter" % (prefix, self.mangled_full_name)
        self.iter_pytypestruct = "Py%s%sIter_Type" % (prefix,  self.mangled_full_name)

        ## re-register the class type handlers, now with class full name
        self.register_alias(self.full_name)

        self.python_to_c_converter = self.module.get_root().get_python_to_c_type_converter_function_name(
            self.ThisContainerReturn(self.full_name))


    def register_alias(self, alias):
        """Re-register the class with another base name, in addition to any
        registrations that might have already been done."""

        self.module.register_type(None, alias, self)

        self.ThisContainerParameter.CTYPES.append(alias)
        try:
            param_type_matcher.register(alias, self.ThisContainerParameter)
        except ValueError: pass
        
        self.ThisContainerReturn.CTYPES.append(alias)
        try:
            return_type_matcher.register(alias, self.ThisContainerReturn)
        except ValueError: pass


    def generate_forward_declarations(self, code_sink, module):
        """
        Generates forward declarations for the instance and type
        structures.
        """

        # container pystruct
        code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *obj;
} %s;
    ''' % (self.full_name, self.pystruct))

        # container iterator pystruct
        code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *container;
    %s::iterator *iterator;
} %s;
    ''' % (self.pystruct, self.full_name, self.iter_pystruct))

        code_sink.writeln()
        code_sink.writeln('extern PyTypeObject %s;' % (self.pytypestruct,))
        code_sink.writeln('extern PyTypeObject %s;' % (self.iter_pytypestruct,))
        code_sink.writeln()

        this_type_converter = self.module.get_root().get_python_to_c_type_converter_function_name(
            self.ThisContainerReturn(self.full_name))
        self.module.get_root().declare_one_time_definition(this_type_converter)
        code_sink.writeln('int %(CONTAINER_CONVERTER_FUNC_NAME)s(PyObject *arg, %(CTYPE)s *container);'
                          % {'CTYPE': self.full_name,
                             'CONTAINER_CONVERTER_FUNC_NAME': this_type_converter,
                             })
        self.python_to_c_converter = this_type_converter

    def _get_python_name(self):
        if self.custom_name is None:
            class_python_name = self.mangled_name
        else:
            class_python_name = self.custom_name
        return class_python_name

    python_name = property(_get_python_name)

    def _get_python_full_name(self):
        if self.outer_class is None:
            mod_path = self._module.get_module_path()
            mod_path.append(self.python_name)
            return '.'.join(mod_path)
        else:
            return '%s.%s' % (self.outer_class.pytype.slots['tp_name'], self.python_name)

    python_full_name = property(_get_python_full_name)


    def generate(self, code_sink, module, docstring=None):
        """Generates the class to a code sink"""

        ## --- register the class type in the module ---
        module.after_init.write_code("/* Register the '%s' class */" % self.full_name)

        module.after_init.write_error_check('PyType_Ready(&%s)' % (self.pytypestruct,))
        module.after_init.write_error_check('PyType_Ready(&%s)' % (self.iter_pytypestruct,))

        class_python_name = self.python_name

        if self.outer_class is None:
            module.after_init.write_code(
                'PyModule_AddObject(m, (char *) \"%s\", (PyObject *) &%s);' % (
                class_python_name, self.pytypestruct))
            module.after_init.write_code(
                'PyModule_AddObject(m, (char *) \"%s\", (PyObject *) &%s);' % (
                class_python_name+'Iter', self.iter_pytypestruct))
        else:
            module.after_init.write_code(
                'PyDict_SetItemString((PyObject*) %s.tp_dict, (char *) \"%s\", (PyObject *) &%s);' % (
                self.outer_class.pytypestruct, class_python_name, self.pytypestruct))
            module.after_init.write_code(
                'PyDict_SetItemString((PyObject*) %s.tp_dict, (char *) \"%s\", (PyObject *) &%s);' % (
                self.outer_class.pytypestruct, class_python_name+'Iter', self.iter_pytypestruct))

        self._generate_gc_methods(code_sink)
        self._generate_destructor(code_sink)
        self._generate_iter_methods(code_sink)
        self._generate_container_constructor(code_sink)
        self._generate_type_structure(code_sink, docstring)
        
    def _generate_type_structure(self, code_sink, docstring):
        """generate the type structure"""

        self.pytype.slots.setdefault("tp_basicsize", "sizeof(%s)" % (self.pystruct,))
        self.pytype.slots.setdefault("tp_flags", "Py_TPFLAGS_DEFAULT")
        self.pytype.slots.setdefault("typestruct", self.pytypestruct)
        self.pytype.slots.setdefault("tp_name", self.python_full_name)
        self.pytype.generate(code_sink)

        self.iter_pytype.slots.setdefault("tp_basicsize", "sizeof(%s)" % (self.iter_pystruct,))
        self.iter_pytype.slots.setdefault("tp_flags", ("Py_TPFLAGS_DEFAULT|Py_TPFLAGS_HAVE_GC"))
        self.iter_pytype.slots.setdefault("typestruct", self.iter_pytypestruct)
        self.iter_pytype.slots.setdefault("tp_name", self.python_full_name + 'Iter')
        self.iter_pytype.generate(code_sink)

    def _get_iter_delete_code(self):
        delete_code = ("delete self->iterator;\n"
                       "    self->iterator = NULL;\n")
        return delete_code

    def _get_container_delete_code(self):
        delete_code = ("delete self->obj;\n"
                       "    self->obj = NULL;\n")
        return delete_code

    def _generate_gc_methods(self, code_sink):
        """Generate tp_clear and tp_traverse"""

        ## --- iterator tp_clear ---
        tp_clear_function_name = "%s__tp_clear" % (self.iter_pystruct,)
        self.iter_pytype.slots.setdefault("tp_clear", tp_clear_function_name )

        code_sink.writeln(r'''
static void
%s(%s *self)
{
    Py_CLEAR(self->container);
    %s
}
''' % (tp_clear_function_name, self.iter_pystruct, self._get_iter_delete_code()))

        ## --- iterator tp_traverse ---
        tp_traverse_function_name = "%s__tp_traverse" % (self.iter_pystruct,)
        self.iter_pytype.slots.setdefault("tp_traverse", tp_traverse_function_name )

        code_sink.writeln(r'''
static int
%s(%s *self, visitproc visit, void *arg)
{
    Py_VISIT(self->container);
    return 0;
}
''' % (tp_traverse_function_name, self.iter_pystruct))


    def _generate_destructor(self, code_sink):
        """Generate a tp_dealloc function and register it in the type"""

        # -- container --
        container_tp_dealloc_function_name = "_wrap_%s__tp_dealloc" % (self.pystruct,)
        code_sink.writeln(r'''
static void
%s(%s *self)
{
    %s
    self->ob_type->tp_free((PyObject*)self);
}
''' % (container_tp_dealloc_function_name, self.pystruct,
       self._get_container_delete_code()))

        self.pytype.slots.setdefault("tp_dealloc", container_tp_dealloc_function_name )


        # -- iterator --
        iter_tp_dealloc_function_name = "_wrap_%s__tp_dealloc" % (self.iter_pystruct,)
        code_sink.writeln(r'''
static void
%s(%s *self)
{
    Py_CLEAR(self->container);
    %s
    self->ob_type->tp_free((PyObject*)self);
}
''' % (iter_tp_dealloc_function_name, self.iter_pystruct, self._get_iter_delete_code()))

        self.iter_pytype.slots.setdefault("tp_dealloc", iter_tp_dealloc_function_name )


    def _generate_iter_methods(self, code_sink):

        container_tp_iter_function_name = "_wrap_%s__tp_iter" % (self.pystruct,)
        iterator_tp_iter_function_name = "_wrap_%s__tp_iter" % (self.iter_pystruct,)
        subst_vars = {
            'CONTAINER_ITER_FUNC': container_tp_iter_function_name,
            'ITERATOR_ITER_FUNC': iterator_tp_iter_function_name,
            'PYSTRUCT': self.pystruct,
            'ITER_PYSTRUCT': self.iter_pystruct,
            'ITER_PYTYPESTRUCT': self.iter_pytypestruct,
            'CTYPE': self.full_name,
            }
        # -- container --
        code_sink.writeln(r'''
static PyObject*
%(CONTAINER_ITER_FUNC)s(%(PYSTRUCT)s *self)
{
    %(ITER_PYSTRUCT)s *iter = PyObject_GC_New(%(ITER_PYSTRUCT)s, &%(ITER_PYTYPESTRUCT)s);
    Py_INCREF(self);
    iter->container = self;
    iter->iterator = new %(CTYPE)s::iterator(self->obj->begin());
    return (PyObject*) iter;
}
''' % subst_vars)

        self.pytype.slots.setdefault("tp_iter", container_tp_iter_function_name)
        

        # -- iterator --
        container_tp_iter_function_name = "_wrap_%s__tp_iter" % (self.pystruct,)
        code_sink.writeln(r'''
static PyObject*
%(ITERATOR_ITER_FUNC)s(%(ITER_PYSTRUCT)s *self)
{
    Py_INCREF(self);
    return (PyObject*) self;
}
''' % subst_vars)

        self.iter_pytype.slots.setdefault("tp_iter", iterator_tp_iter_function_name)

        # -- iterator tp_iternext
        iternext = IterNextWrapper(self)
        iternext.generate(code_sink)
        self.iter_pytype.slots.setdefault("tp_iternext", iternext.c_function_name)
        


    def _generate_container_constructor(self, code_sink):
        container_tp_init_function_name = "_wrap_%s__tp_init" % (self.pystruct,)
        item_python_to_c_converter = self.module.get_root().generate_python_to_c_type_converter(self.value_type, code_sink)
        this_type_converter = self.module.get_root().get_python_to_c_type_converter_function_name(
            self.ThisContainerReturn(self.full_name))
        subst_vars = {
            'FUNC': container_tp_init_function_name,
            'PYSTRUCT': self.pystruct,
            'PYTYPESTRUCT': self.pytypestruct,
            'CTYPE': self.full_name,
            'ITEM_CONVERTER': item_python_to_c_converter,
            'PYTHON_NAME': self.python_name,
            'ITEM_CTYPE': self.value_type.ctype,
            'CONTAINER_CONVERTER_FUNC_NAME': this_type_converter,
            }
        code_sink.writeln(r'''
int %(CONTAINER_CONVERTER_FUNC_NAME)s(PyObject *arg, %(CTYPE)s *container)
{
    if (PyObject_IsInstance(arg, (PyObject*) &%(PYTYPESTRUCT)s)) {
        *container = *((%(PYSTRUCT)s*)arg)->obj;
    } else if (PyList_Check(arg)) {
        Py_ssize_t size = PyList_Size(arg);
        for (Py_ssize_t i = 0; i < size; i++) {
            %(ITEM_CTYPE)s item;
            if (!%(ITEM_CONVERTER)s(PyList_GET_ITEM(arg, i), &item)) {
                return 0;
            }
            container->push_back(item);
        }
    } else {
        PyErr_SetString(PyExc_TypeError, "parameter must be None, a %(PYTHON_NAME)s instance, or a list of %(ITEM_CTYPE)s");
        return 0;
    }
    return 1;
}


static int
%(FUNC)s(%(PYSTRUCT)s *self, PyObject *args, PyObject *kwargs)
{
    const char *keywords[] = {"arg", NULL};
    PyObject *arg = NULL;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, (char *) "|O", (char **) keywords, &arg)) {
        return -1;
    }

    self->obj = new %(CTYPE)s;

    if (arg == NULL)
        return 0;

    if (!%(CONTAINER_CONVERTER_FUNC_NAME)s(arg, self->obj)) {
        delete self->obj;
        self->obj = NULL;
        return -1;
    }
    return 0;
}
''' % subst_vars)

        self.pytype.slots.setdefault("tp_init", container_tp_init_function_name)



## ----------------------------
## Type Handlers
## ----------------------------


class ContainerParameterBase(Parameter):
    "Base class for all C++ Class parameter handlers"
    CTYPES = []
    container_type = Container('dummy', ReturnValue.new('void')) # Container instance
    DIRECTIONS = [Parameter.DIRECTION_IN]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False, default_value=None):
        """
        ctype -- C type, normally 'MyClass*'
        name -- parameter name
        """
        if ctype == self.container_type.name:
            ctype = self.container_type.full_name
        super(ContainerParameterBase, self).__init__(
            ctype, name, direction, is_const, default_value)

        ## name of the PyFoo * variable used in parameter parsing
        self.py_name = None


class ContainerReturnValueBase(ReturnValue):
    "Class return handlers -- base class"
    CTYPES = []
    container_type = Container('dummy', ReturnValue.new('void')) # CppClass instance

    def __init__(self, ctype):
        super(ContainerReturnValueBase, self).__init__(ctype)
        ## name of the PyFoo * variable used in return value building
        self.py_name = None
        
        
    

class ContainerParameter(ContainerParameterBase):
    "Container handlers"
    CTYPES = []
    container_type = Container('dummy', ReturnValue.new('void')) # CppContainer instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.container_type, Container)

        assert self.default_value is None, "default value not implemented for containers"

        self.py_name = wrapper.declarations.declare_variable('PyObject*', self.name)
        container_tmp_var = wrapper.declarations.declare_variable(
            self.container_type.full_name, self.name + '_value')

        wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name)
        wrapper.before_call.write_error_check(
            '!%s(%s, &%s)' % (self.container_type.python_to_c_converter, self.py_name, container_tmp_var))
        wrapper.call_params.append(container_tmp_var)

    def convert_c_to_python(self, wrapper):
        '''Write some code before calling the Python method.'''
        assert isinstance(wrapper, ReverseWrapperBase)

        self.py_name = wrapper.declarations.declare_variable(
            self.container_type.pystruct+'*', 'py_'+self.container_type.name)
        wrapper.before_call.write_code(
            "%s = PyObject_New(%s, %s);" %
            (self.py_name, self.container_type.pystruct, '&'+self.container_type.pytypestruct))

        wrapper.before_call.write_code("%s->obj = new %s(%s);" % (self.py_name, self.container_type.full_name, self.value))

        wrapper.build_params.add_parameter("N", [self.py_name])


class ContainerReturnValue(ContainerReturnValueBase):
    "Container type return handlers"
    CTYPES = []
    container_type = Container('dummy', ReturnValue.new('void')) # CppContainer instance

    def __init__(self, ctype, is_const=False):
        """override to fix the ctype parameter with namespace information"""
        if ctype == self.container_type.name:
            ctype = self.container_type.full_name
        super(ContainerReturnValue, self).__init__(ctype)
        self.is_const = is_const

    def get_c_error_return(self): # only used in reverse wrappers
        """See ReturnValue.get_c_error_return"""
        return "return %s();" % (self.container_type.full_name,)

    def convert_c_to_python(self, wrapper):
        """see ReturnValue.convert_c_to_python"""
        py_name = wrapper.declarations.declare_variable(
            self.container_type.pystruct+'*', 'py_'+self.container_type.name)
        self.py_name = py_name
        wrapper.after_call.write_code(
            "%s = PyObject_New(%s, %s);" %
            (py_name, self.container_type.pystruct, '&'+self.container_type.pytypestruct))

        wrapper.after_call.write_code("%s->obj = new %s(%s);" % (self.py_name, self.container_type.full_name, self.value))

        wrapper.build_params.add_parameter("N", [py_name], prepend=True)

    def convert_python_to_c(self, wrapper):
        """see ReturnValue.convert_python_to_c"""
        wrapper.parse_params.add_parameter('O&', [self.container_type.python_to_c_converter, '&'+self.value])


## end
