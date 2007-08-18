"""
C wrapper wrapper
"""
from typehandlers.base import ForwardWrapperBase
from typehandlers import codesink


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
        self.wrapper_name = wrapper_name
        self.wrapper_function_name = None
        self.pystruct = 'PyObject'
        
    def add(self, wrapper):
        """
        Add a wrapper to the overloaded wrapper
        wrapper -- a Wrapper object
        """
        assert isinstance(wrapper, ForwardWrapperBase)
        self.wrappers.append(wrapper)
    
    def generate(self, code_sink):
        """
        Generate all the wrappers plus the 'aggregator' wrapper to a code sink.
        """
        if len(self.wrappers) == 1:
            ## special case when there's only one wrapper; keep
            ## simple things simple
            self.wrappers[0].generate(code_sink)
            self.wrapper_function_name = self.wrappers[0].wrapper_actual_name
            assert self.wrapper_function_name is not None
        else:
            ## multiple overloaded wrappers case..

            ## Generate the individual "low level" wrappers that handle a single prototype
            self.wrapper_function_name = self.wrappers[0].wrapper_base_name
            delegate_wrappers = []
            for number, wrapper in enumerate(self.wrappers):
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
                wrapper.generate(code_sink, wrapper_name,
                                 extra_wrapper_params=["PyObject **return_exception"])
                delegate_wrappers.append(wrapper_name)
            
            ## Generate the 'main wrapper' that calls the other ones
            code_sink.writeln()
            code_sink.writeln("static " + self.RETURN_TYPE)
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
        if len(self.wrappers) == 1:
            return self.wrappers[0].get_py_method_def(name)
        else:
            flags = self.wrappers[0].get_py_method_def_flags()
            ## detect inconsistencies in flags; they must all be the same
            if __debug__:
                for func in self.wrappers:
                    assert func.get_py_method_def_flags() == flags
            docstring = None # FIXME
            return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
                (name, self.wrapper_function_name, '|'.join(flags),
                 (docstring is None and "NULL" or ('"'+docstring+'"')))
