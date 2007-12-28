"""
C wrapper wrapper
"""
from typehandlers.base import ForwardWrapperBase
import utils

def isiterable(obj): 
    """Returns True if an object appears to be iterable"""
    return hasattr(obj, '__iter__') or isinstance(obj, basestring)

def vector_counter(vec):
    """
    >>> list(vector_counter([[1,2], ['a', 'b'], ['x', 'y']]))
    [[1, 'a', 'x'], [1, 'a', 'y'], [1, 'b', 'x'], [1, 'b', 'y'], [2, 'a', 'x'], [2, 'a', 'y'], [2, 'b', 'x'], [2, 'b', 'y']]
    """
    iters = [iter(l) for l in vec]
    values = [it.next() for it in iters[:-1]] + [vec[-1][0]]
    while 1:
        for idx in xrange(len(iters)-1, -1, -1):
            try:
                values[idx] = iters[idx].next()
            except StopIteration:
                iters[idx] = iter(vec[idx])
                values[idx] = iters[idx].next()
            else:
                break
        else:
            raise StopIteration
        yield list(values)

class OverloadedWrapper(object):
    """
    An object that aggregates a set of wrapper objects; it generates
    a single python wrapper wrapper that supports overloading,
    i.e. tries to parse parameters according to each individual
    Function parameter list, and uses the first wrapper that doesn't
    generate parameter parsing error.
    """

    RETURN_TYPE = NotImplemented
    ERROR_RETURN = NotImplemented

    def __init__(self, wrapper_name):
        """
        wrapper_name -- C/C++ name of the wrapper
        """
        self.wrappers = []
        self.all_wrappers = None
        self.wrapper_name = wrapper_name
        self.wrapper_function_name = None
        self.pystruct = 'PyObject'
        self.static_decl = True
        self.enable_implicit_conversions = True
        
    def add(self, wrapper):
        """
        Add a wrapper to the overloaded wrapper
        wrapper -- a Wrapper object
        """
        assert isinstance(wrapper, ForwardWrapperBase)
        self.wrappers.append(wrapper)

    def _compute_all_wrappers(self):
        """
        Computes all the wrappers that should be generated; this
        includes not only the regular overloaded wrappers but also
        additional wrappers created in runtime to fulfil implicit
        conversion requirements.  The resulting list is stored as
        self.all_wrappers
        """
        self.all_wrappers = []
        for wrapper in self.wrappers:
            self.all_wrappers.append(wrapper)
            if not self.enable_implicit_conversions:
                continue
            ## add additional wrappers to support implicit conversion
            if not hasattr(wrapper, "clone"):
                continue
            implicit_conversion_classes = []
            implicit_conversion_positions = []
            for pos, param in enumerate(wrapper.parameters):
                if not isinstance(param, (CppClassParameter, CppClassRefParameter)):
                    continue
                if isinstance(param, (CppClassRefParameter)) and not param.is_const:
                    continue
                conversion_sources = param.cpp_class.get_all_implicit_conversions()
                if conversion_sources:
                    conversion_sources.insert(0, param.cpp_class)
                    implicit_conversion_classes.append(conversion_sources)
                    implicit_conversion_positions.append(pos)
            if not implicit_conversion_classes:
                continue
            ## Now generate the addition wrappers, with all possible
            ## combinations of implicit conversion source classes...
            combinations = vector_counter(implicit_conversion_classes)
            ## skip the first one, as it is the same as in the original wrapper
            combinations.next()
            for combination in combinations:
                wrapper_clone = wrapper.clone()
                for pos, cpp_class in zip(implicit_conversion_positions, combination):
                    ## now make this parameter handle a different C++ class
                    param = wrapper_clone.parameters[pos]
                    ref = (isinstance(param, CppClassRefParameter) and ' &' or '')
                    const = (param.is_const and 'const ' or '')
                    param.cpp_class = cpp_class
                    param.ctype = '%s%s%s' % (const, cpp_class.full_name, ref)
                self.all_wrappers.append(wrapper_clone)
                

    def generate(self, code_sink):
        """
        Generate all the wrappers plus the 'aggregator' wrapper to a code sink.
        """

        self._compute_all_wrappers()

        if len(self.all_wrappers) == 1:
            ## special case when there's only one wrapper; keep
            ## simple things simple

            #self.all_wrappers[0].generate(code_sink)
            utils.call_with_error_handling(self.all_wrappers[0].generate,
                                           (code_sink,), {}, self.all_wrappers[0])

            self.wrapper_function_name = self.all_wrappers[0].wrapper_actual_name
            assert self.wrapper_function_name is not None
        else:
            ## multiple overloaded wrappers case..

            ## Generate the individual "low level" wrappers that handle a single prototype
            self.wrapper_function_name = self.all_wrappers[0].wrapper_base_name
            delegate_wrappers = []
            for number, wrapper in enumerate(self.all_wrappers):
                ## enforce uniform method flags
                wrapper.force_parse = wrapper.PARSE_TUPLE_AND_KEYWORDS
                ## an extra parameter 'return_exception' is used to
                ## return parse error exceptions to the 'main wrapper'
                error_return = """{
    PyObject *exc_type, *traceback;
    PyErr_Fetch(&exc_type, return_exception, &traceback);
    Py_XDECREF(exc_type);
    Py_XDECREF(traceback);
}
%s""" % (self.ERROR_RETURN,)
                wrapper_name = "%s__%i" % (self.wrapper_function_name, number)
                wrapper.set_parse_error_return(error_return)
                code_sink.writeln()

                # wrapper.generate(code_sink, wrapper_name,
                #                  extra_wrapper_params=["PyObject **return_exception"])
                try:
                    utils.call_with_error_handling(
                        wrapper.generate, args=(code_sink, wrapper_name),
                        kwargs=dict(extra_wrapper_params=["PyObject **return_exception"]),
                        wrapper=wrapper)
                except utils.SkipWrapper:
                    continue

                delegate_wrappers.append(wrapper_name)

            ## if all wrappers did not generate, then the overload
            ## aggregator wrapper should not be generated either..
            if not delegate_wrappers:
                raise utils.SkipWrapper
            
            ## Generate the 'main wrapper' that calls the other ones
            code_sink.writeln()
            if self.static_decl:
                code_sink.writeln("static " + self.RETURN_TYPE)
            else:
                code_sink.writeln(self.RETURN_TYPE)
            code_sink.writeln("%s(%s *self,"
                              " PyObject *args, PyObject *kwargs)"
                              % (self.wrapper_function_name, self.pystruct))
            code_sink.writeln('{')
            code_sink.indent()
            code_sink.writeln(self.RETURN_TYPE + ' retval;')
            code_sink.writeln('PyObject *error_list;')
            code_sink.writeln('PyObject *exceptions[%i] = {0,};' % len(delegate_wrappers))
            for number, delegate_wrapper in enumerate(delegate_wrappers):
                ## call the delegate wrapper
                code_sink.writeln("retval = %s(self, args, kwargs, &exceptions[%i]);"
                                  % (delegate_wrapper, number))
                ## if no parse exception, call was successful:
                ## free previous exceptions and return the result
                code_sink.writeln("if (!exceptions[%i]) {" % number)
                code_sink.indent()
                for i in xrange(number):
                    code_sink.writeln("Py_DECREF(exceptions[%i]);" % i)
                code_sink.writeln("return retval;")
                code_sink.unindent()
                code_sink.writeln("}")

            ## If the following generated code is reached it means
            ## that all of our delegate wrappers had parsing errors:
            ## raise an appropriate exception, free the previous
            ## exceptions, and return NULL
            code_sink.writeln('error_list = PyList_New(%i);' % len(delegate_wrappers))
            for i in xrange(len(delegate_wrappers)):
                code_sink.writeln(
                    'PyList_SET_ITEM(error_list, %i, PyObject_Str(exceptions[%i]));'
                    % (i, i))
                code_sink.writeln("Py_DECREF(exceptions[%i]);" % i)
            code_sink.writeln('PyErr_SetObject(PyExc_TypeError, error_list);')
            code_sink.writeln("Py_DECREF(error_list);")
            code_sink.writeln(self.ERROR_RETURN)
            code_sink.unindent()
            code_sink.writeln('}')
        
    def get_py_method_def(self, name):
        """
        Returns an array element to use in a PyMethodDef table.
        Should only be called after code generation.

        name -- python wrapper/method name
        """
        if len(self.all_wrappers) == 1:
            return self.all_wrappers[0].get_py_method_def(name)
        else:
            flags = self.all_wrappers[0].get_py_method_def_flags()
            ## detect inconsistencies in flags; they must all be the same
            if __debug__:
                for func in self.all_wrappers:
                    assert set(func.get_py_method_def_flags()) == set(flags),\
                        ("Expected PyMethodDef flags %r, got %r"
                         % (flags, func.get_py_method_def_flags()))
            docstring = None # FIXME
            return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
                (name, self.wrapper_function_name, '|'.join(flags),
                 (docstring is None and "NULL" or ('"'+docstring+'"')))

    def generate_declaration(self, code_sink):
        self._compute_all_wrappers()

        if len(self.all_wrappers) > 1:
            for i, wrapper in enumerate(self.all_wrappers):
                wrapper.overload_index = i
                wrapper.force_parse = wrapper.PARSE_TUPLE_AND_KEYWORDS
                wrapper.generate_declaration(
                    code_sink,
                    extra_wrapper_parameters=["PyObject **return_exception"])

        self.all_wrappers[0].overload_index = None
        self.all_wrappers[0].generate_declaration(code_sink)

    def reset_code_generation_state(self):
        self._compute_all_wrappers()
        for wrapper in self.all_wrappers:
            wrapper.reset_code_generation_state()


from cppclass import CppClassParameter, CppClassRefParameter

