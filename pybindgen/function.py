"""
C function wrapper
"""
from typehandlers.base import ForwardWrapperBase
from typehandlers import codesink


class Function(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C function.
    """

    def __init__(self, return_value, function_name, parameters, docstring=None):
        """
        return_value -- the function return value
        function_name -- name of the C function
        parameters -- the function parameters
        """
        super(Function, self).__init__(
            return_value, parameters,
            parse_error_return="return NULL;",
            error_return="return NULL;")
        self.function_name = function_name
        self.wrapper_name = None
        self.docstring = docstring
    
    def generate_call(self):
        "virtual method implementation; do not call"
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' % (self.function_name, ", ".join(self.call_params)))
        else:
            self.before_call.write_code(
                'retval = %s(%s);' % (self.function_name, ", ".join(self.call_params)))

    def generate(self, code_sink, wrapper_name=None, extra_wrapper_params=()):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        wrapper_name -- name of wrapper function
        """
        if wrapper_name is None:
            wrapper_name = "_wrap_%s" % (self.function_name,)
        self.wrapper_name = wrapper_name
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject *")
        prototype_line = ("%s(PyObject *dummy PYBINDGEN_UNUSED, "
                          "PyObject *args, PyObject *kwargs") % (wrapper_name,)
        if extra_wrapper_params:
            prototype_line += ", " + ", ".join(extra_wrapper_params)
        prototype_line += ')'
        code_sink.writeln(prototype_line)
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')
        return wrapper_name
        

    def get_py_method_def(self, name):
        """Returns an array element to use in a PyMethodDef table.
         Should only be called after code generation.

        name -- python function/method name
        """
        flags = self.get_py_method_def_flags()
        return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
               (name, self.wrapper_name, '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))


class OverloadedFunction(object):
    """
    An object that aggregates a set of Function objects; it generates
    a single python function wrapper that supports overloading,
    i.e. tries to parse parameters according to each individual
    Function parameter list, and uses the first wrapper that doesn't
    generate parameter parsing error.
    """

    def __init__(self, function_name):
        """
        function_name -- C/C++ name of the function
        """
        self.functions = []
        self.function_name = function_name
        self.wrapper_name = None
        
    def add_function(self, function):
        """
        Add a function to the overloaded wrapper
        function -- a Function object
        """
        assert isinstance(function, Function)
        self.functions.append(function)
    
    def generate(self, code_sink):
        """
        Generate all the wrappers plus the 'aggregator' wrapper to a code sink.
        """
        if len(self.functions) == 1:
            ## special case when there's only one function; keep
            ## simple things simple
            self.wrapper_name = self.functions[0].generate(code_sink)
        else:
            ## multiple overloaded functions case..

            ## Generate the individual "low level" wrappers that handle a single prototype
            self.wrapper_name = "_wrap_%s" % (self.function_name,)
            delegate_wrappers = []
            for number, function in enumerate(self.functions):
                ## enforce uniform method flags
                function.force_parse = Function.PARSE_TUPLE_AND_KEYWORDS
                ## an extra parameter 'return_exception' is used to
                ## return parse error exceptions to the 'main wrapper'
                error_return = """{
    PyObject *exc_type, *traceback;
    PyErr_Fetch(&exc_type, return_exception, &traceback);
    Py_XDECREF(exc_type);
    Py_XDECREF(traceback);
}
return NULL;"""
                function.set_parse_error_return(error_return)
                function.generate(code_sink, wrapper_name,
                                  extra_wrapper_params=["PyObject **return_exception"])

                wrapper_name = "%s__%i" % (self.wrapper_name, number)
                delegate_wrappers.append(wrapper_name)
            
            ## Generate the 'main wrapper' that calls the other ones
            code_sink.writeln("static PyObject *")
            code_sink.writeln("%s(PyObject *dummy PYBINDGEN_UNUSED,"
                              " PyObject *args, PyObject *kwargs)"
                              % (self.wrapper_name,))
            code_sink.writeln('{')
            code_sink.indent()
            code_sink.writeln('PyObject *retval, *error_list;')
            code_sink.writeln('PyObject *exceptions[%i] = {0,};' % len(delegate_wrappers))
            for number, delegate_wrapper in enumerate(delegate_wrappers):
                ## call the delegate wrapper
                code_sink.writeln("retval = %s(dummy, args, kwargs, &exceptions[%i]);"
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
            code_sink.writeln('return NULL;')
            code_sink.unindent()
            code_sink.writeln('}')
        
    def get_py_method_def(self, name):
        """
        Returns an array element to use in a PyMethodDef table.
        Should only be called after code generation.

        name -- python function/method name
        """
        if len(self.functions) == 1:
            return self.functions[0].get_py_method_def(name)
        else:
            flags = self.functions[0].get_py_method_def_flags()
            ## detect inconsistencies in flags; they must all be the same
            if __debug__:
                for func in self.functions:
                    assert func.get_py_method_def_flags() == flags
            docstring = None # FIXME
            return "{\"%s\", (PyCFunction) %s, %s, %s }," % \
                (name, self.wrapper_name, '|'.join(flags),
                 (docstring is None and "NULL" or ('"'+docstring+'"')))
