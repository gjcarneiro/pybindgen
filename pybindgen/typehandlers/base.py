## -*- python -*-

"""
Base classes for all parameter/return type handlers,
and base interfaces for wrapper generators.
"""

import codesink


try:
    all
except NameError: # for compatibility with Python < 2.5
    def all(iterable):
        "Returns True if all elements are true"
        for element in iterable:
            if not element:
                return False
        return True

class CodeGenerationError(Exception):
    """Exception that is raised when wrapper generation fails for some reason."""


def join_ctype_and_name(ctype, name):
    """
    Utility method that joins a C type and a variable name into
    a single string

    >>> join_ctype_and_name('void*', 'foo')
    'void *foo'
    >>> join_ctype_and_name('void *', 'foo')
    'void *foo'
    >>> join_ctype_and_name("void**", "foo")
    'void **foo'
    >>> join_ctype_and_name("void **", "foo")
    'void **foo'
    """
    if ctype[-1] == '*':
        for i in range(-1, -len(ctype), -1):
            if ctype[i] != '*':
                if ctype[i] == ' ':
                    return "".join([ctype[:i+1], ctype[i+1:], name])
                else:
                    return "".join([ctype[:i+1], ' ', ctype[i+1:], name])
        raise ValueError
    else:
        return " ".join([ctype, name])


class CodeBlock(object):
    '''An intelligent code block that keeps track of cleanup actions.
    This object is to be used by TypeHandlers when generating code.'''

    class CleanupHandle(object):
        """Handle for some cleanup code"""
        __slots__ = ['code_block', 'position']
        def __init__(self, code_block, position):
            """Create a handle given code_block and position"""
            self.code_block = code_block
            self.position = position

        def __cmp__(self, other):
            comp = cmp(self.code_block, other.code_block)
            if comp:
                return comp
            return cmp(self.position, other.position)

        def cancel(self):
            """Cancel the cleanup code"""
            self.code_block.remove_cleanup_code(self)

        def get_position(self):
            "returns the cleanup code relative position"
            return self.position

    
    def __init__(self, error_return, predecessor=None):
        '''
           error_return -- code that is generated on error conditions
                           (detected by write_error_check()); normally
                           it returns from the wrapper function,
                           e.g. return NULL;
           predecessor -- optional predecessor code block; a
                          predecessor is used to search for additional
                          cleanup actions.

        >>> block = CodeBlock('return NULL;')
        >>> block.write_code("foo();")
        >>> cleanup1 = block.add_cleanup_code("clean1();")
        >>> cleanup2 = block.add_cleanup_code("clean2();")
        >>> cleanup3 = block.add_cleanup_code("clean3();")
        >>> cleanup2.cancel()
        >>> block.write_error_check("error()", "error_clean()")
        >>> block.write_code("bar();")
        >>> block.write_cleanup()
        >>> print block.sink.flush().rstrip()
        foo();
        if (error()) {
            error_clean()
            clean3();
            clean1();
            return NULL;
        }
        bar();
        clean3();
        clean1();
        '''
        self.sink = codesink.MemoryCodeSink()
        self.predecessor = predecessor
        self._cleanup_actions = {}
        self._last_cleanup_position = 0
        self.error_return = error_return
        
    def write_code(self, code):
        '''Write out some simple code'''
        self.sink.writeln(code)

    def add_cleanup_code(self, cleanup_code):
        '''Add a chunk of code used to cleanup previously allocated resources

        Returns a handle used to cancel the cleanup code
        '''
        self._last_cleanup_position += 1
        handle = self.CleanupHandle(self, self._last_cleanup_position)
        self._cleanup_actions[handle.get_position()] = cleanup_code
        return handle

    def remove_cleanup_code(self, handle):
        '''Remove cleanup code previously added with add_cleanup_code()
        '''
        assert isinstance(handle, self.CleanupHandle)
        del self._cleanup_actions[handle.get_position()]

    def get_cleanup_code(self):
        '''return a new list with all cleanup actions, including the
        ones from predecessor code blocks; Note: cleanup actions are
        executed in reverse order than when they were added.'''
        if self.predecessor is None:
            cleanup = []
        else:
            cleanup = self.predecessor.get_cleanup_code()
        items = self._cleanup_actions.items()
        items.sort()
        for dummy, code in items:
            cleanup.append(code)
        cleanup.reverse()
        return cleanup

    def write_error_check(self, failure_expression, failure_cleanup=None):
        '''Add a chunk of code that checks for a possible error

        Keywork arguments:

        failure_expression -- C boolean expression that is true when
                              an error occurred
        failure_cleanup -- optional extra cleanup code to write only
                           for the the case when failure_expression is
                           true; this extra cleanup code comes before
                           all other cleanup code previously registered.
        '''
        self.sink.writeln("if (%s) {" % (failure_expression,))
        self.sink.indent()
        if failure_cleanup is not None:
            self.sink.writeln(failure_cleanup)
        self.write_cleanup()
        self.sink.writeln(self.error_return)
        self.sink.unindent()
        self.sink.writeln("}")

    def write_cleanup(self):
        """Write the current cleanup code."""
        for cleanup_action in self.get_cleanup_code():
            self.sink.writeln(cleanup_action)


class ParseTupleParameters(object):
    "Object to keep track of PyArg_ParseTuple (or similar) parameters"

    def __init__(self):
        """
        >>> tuple_params = ParseTupleParameters()
        >>> tuple_params.add_parameter('i', ['&foo'], 'foo')
        >>> tuple_params.add_parameter('s', ['&bar'], 'bar', optional=True)
        >>> tuple_params.get_parameters()
        ['"i|s"', '&foo', '&bar']
        >>> tuple_params.get_keywords()
        ['foo', 'bar']

        >>> tuple_params = ParseTupleParameters()
        >>> tuple_params.add_parameter('i', ['&foo'], 'foo')
        >>> tuple_params.add_parameter('s', ['&bar'], 'bar', prepend=True)
        >>> tuple_params.get_parameters()
        ['"si"', '&bar', '&foo']
        >>> tuple_params.get_keywords()
        ['bar', 'foo']

        >>> tuple_params = ParseTupleParameters()
        >>> tuple_params.add_parameter('i', ['&foo'])
        >>> print tuple_params.get_keywords()
        None
        """
        self._parse_tuple_items = [] # (template, param_values, param_name, optional)
        
    def add_parameter(self, param_template, param_values, param_name=None,
                      prepend=False, optional=False):
        """
        Adds a new parameter specification

        param_template -- template item, see documentation for
                          PyArg_ParseTuple for more information
        param_values -- list of parameters, see documentation
                       for PyArg_ParseTuple for more information
        prepend -- whether this parameter should be parsed first
        optional -- whether the parameter is optional; note that after
                    the first optional parameter, all remaining
                    parameters must also be optional
        """
        assert isinstance(param_values, list)
        assert isinstance(param_template, str)
        item = (param_template, param_values, param_name, optional)
        if prepend:
            self._parse_tuple_items.insert(0, item)
        else:
            self._parse_tuple_items.append(item)

    def get_parameters(self):
        """
        returns a list of parameters to pass into a
        PyArg_ParseTuple-style function call, the first paramter in
        the list being the template string.
        """
        template = ['"']
        last_was_optional = False
        for (param_template, dummy,
             dummy, optional) in self._parse_tuple_items:
            assert last_was_optional and optional or not last_was_optional
            if not last_was_optional and optional:
                template.append('|')
            last_was_optional = optional
            template.append(param_template)
        template.append('"')
        params = [''.join(template)]
        for (dummy, param_values,
             dummy, dummy) in self._parse_tuple_items:
            params.extend(param_values)
        return params
        
    def get_keywords(self):
        """
        returns list of keywords (parameter names), or None if none of
        the parameters had a name; should only be called if names were
        given for all parameters or none of them.
        """
        keywords = []
        for (dummy, dummy, name, dummy) in self._parse_tuple_items:
            if name is None:
                if keywords:
                    raise ValueError("mixing parameters with and without keywords")
            else:
                keywords.append(name)
        if keywords:
            return keywords
        else:
            return None


class BuildValueParameters(object):
    "Object to keep track of Py_BuildValue (or similar) parameters"

    def __init__(self):
        """
        >>> bld = BuildValueParameters()
        >>> bld.add_parameter('i', [123, 456])
        >>> bld.add_parameter('s', ["hello"])
        >>> bld.get_parameters()
        ['"is"', 123, 456, 'hello']
        >>> bld = BuildValueParameters()
        >>> bld.add_parameter('i', [123])
        >>> bld.add_parameter('s', ["hello"], prepend=True)
        >>> bld.get_parameters()
        ['"si"', 'hello', 123]
        """
        self._build_value_items = [] # (template, param_value, cleanup_handle)

    def add_parameter(self, param_template, param_values,
                      prepend=False, cancels_cleanup=None):
        """
        Adds a new parameter to the Py_BuildValue (or similar) statement.

        param_template -- template item, see documentation for
                          Py_BuildValue for more information
        param_values -- list of C expressions to use as value, see documentation
                        for Py_BuildValue for more information
        prepend -- whether this parameter should come first in the tuple being built
        cancels_cleanup -- optional handle to a cleanup action,
                           that is removed after the call.  Typically
                           this is used for 'N' parameters, which
                           already consume an object reference
        """
        item = (param_template, param_values, cancels_cleanup)
        if prepend:
            self._build_value_items.insert(0, item)
        else:
            self._build_value_items.append(item)

    def get_parameters(self):
        """returns a list of parameters to pass into a
        Py_BuildValue-style function call, the first paramter in
        the list being the template string."""
        template = ['"']
        params = [None]
        for (param_template, param_values, dummy) in self._build_value_items:
            template.append(param_template)
            params.extend(param_values)
        template.append('"')
        params[0] = ''.join(template)
        return params

    def get_cleanups(self):
        """Get a list of handles to cleanup actions"""
        return [cleanup for (dummy, dummy, cleanup) in self._build_value_items]


class DeclarationsScope(object):
    """Manages variable declarations in a given scope."""

    def __init__(self, parent_scope=None):
        """Constructor

        parent_scope -- optional 'parent scope'; if given,
                        declarations in this scope will avoid clashing
                        with names in the parent scope, and vice
                        versa.

        >>> scope = DeclarationsScope()
        >>> scope.declare_variable('int', 'foo')
        'foo'
        >>> scope.declare_variable('char*', 'bar')
        'bar'
        >>> scope.declare_variable('int', 'foo')
        'foo2'
        >>> scope.declare_variable('int', 'foo', '1')
        'foo3'
        >>> scope.declare_variable('const char *', 'kwargs', '{"hello", NULL}', '[]')
        'kwargs'
        >>> print scope.get_code_sink().flush().rstrip()
        int foo;
        char *bar;
        int foo2;
        int foo3 = 1;
        const char *kwargs[] = {"hello", NULL};
        """
        self._declarations = codesink.MemoryCodeSink()
        ## name -> number of variables with that name prefix
        if parent_scope is None:
            self.declared_variables = {}
        else:
            assert isinstance(parent_scope, DeclarationsScope)
            self.declared_variables = parent_scope.declared_variables

    def declare_variable(self, type_, name, initializer=None, array=None):
        """Add code to declare a variable. Returns the actual variable
        name used (uses 'name' as base, with a number in case of conflict.)
        type_ -- C type name of the variable
        name -- base name of the variable; actual name used can be
                slightly different in case of name conflict.
        initializer -- optional, value to initialize the variable with
        array -- optional, array size specifiction, e.g. '[]', or '[100]'
        """
        try:
            num = self.declared_variables[name]
        except KeyError:
            num = 0
        num += 1
        self.declared_variables[name] = num
        if num == 1:
            varname = name
        else:
            varname = "%s%i" % (name, num)
        decl = join_ctype_and_name(type_, varname)
        if array is not None:
            decl += array
        if initializer is not None:
            decl += ' = ' + initializer
        self._declarations.writeln(decl + ';')
        return varname

    def get_code_sink(self):
        """Returns the internal MemoryCodeSink that holds all declararions."""
        return self._declarations



class ReverseWrapperBase(object):
    """Generic base for all reverse wrapper generators.

    Reverse wrappers all have the following general structure in common:

    1. 'declarations' -- variable declarations; for compatibility with
       older C compilers it is very important that all declarations
       come before any simple statement.  Declarations can be added
       with the add_declaration() method on the 'declarations'
       attribute.  Two standard declarations are always predeclared:
       '<return-type> retval', unless return-type is void, and 'PyObject
       *py_retval';

    2. 'code before call' -- this is a code block dedicated to contain
       all code that is needed before calling into Python; code can be
       freely added to it by accessing the 'before_call' (a CodeBlock
       instance) attribute;

    3. 'call into python' -- this is realized by a
       PyObject_CallMethod(...) or similar Python API call; the list
       of parameters used in this call can be customized by accessing
       the 'build_params' (a BuildValueParameters instance) attribute;

    4. 'code after call' -- this is a code block dedicated to contain
       all code that must come after calling into Python; code can be
       freely added to it by accessing the 'after_call' (a CodeBlock
       instance) attribute;

    5. A 'return retval' statement (or just 'return' if return_value is void)

    """

    def __init__(self, return_value, parameters):
        '''
        Base constructor

        return_value -- type handler for the return value
        parameters -- a list of type handlers for the parameters

        '''

        assert isinstance(return_value, ReturnValue)
        assert isinstance(parameters, list)
        assert all([isinstance(param, Parameter) for param in parameters])

        self.return_value = return_value
        self.parameters = parameters

        error_return = return_value.get_c_error_return()
        self.declarations = DeclarationsScope()
        self.before_call = CodeBlock(error_return)
        self.after_call = CodeBlock(error_return, predecessor=self.before_call)
        self.build_params = BuildValueParameters()
        self.parse_params = ParseTupleParameters()

        self.declarations.declare_variable('PyObject*', 'py_retval')
        if return_value.ctype != 'void':
            self.declarations.declare_variable(return_value.ctype, 'retval')

    def generate_python_call(self):
        """Generates the code (into self.before_call) to call into
        Python, storing the result in the variable 'py_retval'; should
        also check for call error.
        """
        raise NotImplementedError

    def generate(self, code_sink, wrapper_name, decl_modifiers=['static']):
        """Generate the wrapper
        code_sink -- a CodeSink object that will receive the code
        wrapper_name -- C/C++ identifier of the function/method to generate
        decl_modifiers -- list of C/C++ declaration modifiers, e.g. 'static'
        """
        assert isinstance(decl_modifiers, list)
        assert all([isinstance(mod, str) for mod in decl_modifiers])

        ## convert the input parameters
        for param in self.parameters:
            param.convert_c_to_python(self)

        ## generate_python_call should include something like
        ## self.after_call.write_error_check('py_retval == NULL')
        self.generate_python_call()

        ## parse the return value
        ## this ensures that py_retval is always a tuple
        self.before_call.write_code('py_retval = Py_BuildValue("(N)", py_retval);')

        ## convert the return value(s)
        self.return_value.convert_python_to_c(self)

        parse_tuple_params = ['py_retval']
        parse_tuple_params.extend(self.parse_params.get_parameters())
        self.before_call.write_error_check('!PyArg_ParseTuple(%s)' %
                                           (', '.join(parse_tuple_params),))

        ## cleanup and return
        self.after_call.write_cleanup()
        if self.return_value.ctype == 'void':
            self.after_call.write_code('return;')
        else:
            self.after_call.write_code('return retval;')

        ## now write out the wrapper function itself

        ## open function
        retline = list(decl_modifiers)
        retline.append(self.return_value.ctype)
        code_sink.writeln(' '.join(retline))

        params_list = ', '.join([join_ctype_and_name(param.ctype, param.name)
                                 for param in self.parameters])
        code_sink.writeln("%s(%s)" % (wrapper_name, params_list))

        ## body
        code_sink.writeln('{')
        code_sink.indent()
        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

        ## close function
        code_sink.unindent()
        code_sink.writeln('}')



class ForwardWrapperBase(object):
    """Generic base for all forward wrapper generators.

    Forward wrappers all have the following general structure in common:

    1. 'declarations' -- variable declarations; for compatibility with
       older C compilers it is very important that all declarations
       come before any simple statement.  Declarations can be added
       with the add_declaration() method on the 'declarations'
       attribute.  Two standard declarations are always predeclared:
       '<return-type> retval', unless return-type is void, and 'PyObject
       *py_retval';

    2. 'code before parse' -- code before the
       PyArg_ParseTupleAndKeywords call; code can be freely added to
       it by accessing the 'before_parse' (a CodeBlock instance)
       attribute;

    3. A PyArg_ParseTupleAndKeywords call; uses items from the
       parse_params object;

    4. 'code before call' -- this is a code block dedicated to contain
       all code that is needed before calling the C function; code can be
       freely added to it by accessing the 'before_call' (a CodeBlock
       instance) attribute;

    5. 'call into C' -- this is realized by a C/C++ call; the list of
       parameters that should be used is in the 'call_params' wrapper
       attribute;

    6. 'code after call' -- this is a code block dedicated to contain
       all code that must come after calling into Python; code can be
       freely added to it by accessing the 'after_call' (a CodeBlock
       instance) attribute;

    7. A py_retval = Py_BuildValue(...) call; this call can be
       customized, so that out/inout parameters can add additional
       return values, by accessing the 'build_params' (a
       BuildValueParameters instance) attribute;

    8. Cleanup and return.

    Object constructors cannot return values, and so the step 7 is to
    be omitted for them.

    """

    def __init__(self, return_value, parameters,
                 parse_error_return, error_return):
        '''
        Base constructor

        return_value -- type handler for the return value
        parameters -- a list of type handlers for the parameters
        parse_error_return  -- statement to return an error during parameter parsing
        error_return -- statement to return an error after parameter parsing

        '''
        assert isinstance(return_value, ReturnValue)
        assert isinstance(parameters, list)
        assert all([isinstance(param, Parameter) for param in parameters])

        self.return_value = return_value
        self.parameters = parameters
        self.declarations = DeclarationsScope()
        self.before_parse = CodeBlock(parse_error_return)
        self.before_call = CodeBlock(parse_error_return, predecessor=self.before_parse)
        self.after_call = CodeBlock(error_return, predecessor=self.before_call)
        self.build_params = BuildValueParameters()
        self.parse_params = ParseTupleParameters()
        self.call_params = []
        
        self.declarations.declare_variable('PyObject*', 'py_retval')
        if return_value.ctype != 'void':
            self.declarations.declare_variable(return_value.ctype, 'retval')
        

    def generate_call(self):
        """Generates the code (into self.before_call) to call into
        Python, storing the result in the variable 'py_retval'; should
        also check for call error.
        """
        raise NotImplementedError

    def generate_body(self, code_sink):
        """Generate the wrapper function body
        code_sink -- a CodeSink object that will receive the code
        """

        ## convert the input parameters
        for param in self.parameters:
            try:
                param.convert_python_to_c(self)
            except NotImplementedError:
                raise CodeGenerationError(
                    'convert_python_to_c method of parameter %s not implemented'
                    % (param.ctype,))
        params = self.parse_params.get_parameters()
        keywords = self.parse_params.get_keywords()

        if keywords is None:
            param_list = ['args'] + params
            self.before_parse.write_error_check('!PyArg_ParseTuple(%s)' %
                                                (', '.join(param_list),))
        else:
            keywords_var = self.declarations.declare_variable(
                'char *', 'keywords',
                '{' + ', '.join(['"%s"' % kw for kw in keywords] + ['NULL']) + '}',
                 '[]')
            param_list = ['args', 'kwargs', params[0], keywords_var] + params[1:]
            self.before_parse.write_error_check('!PyArg_ParseTupleAndKeywords(%s)' %
                                                (', '.join(param_list),))
        
        self.generate_call()

        ## convert the return value(s)
        try:
            self.return_value.convert_c_to_python(self)
        except NotImplementedError:
            raise CodeGenerationError(
                'python_to_c method of return value %s not implemented'
                % (self.return_value.ctype,))

        params = self.build_params.get_parameters()
        if params:
            self.after_call.write_code('py_retval = Py_BuildValue(%s);' %
                                       (', '.join(params),))

        ## cleanup and return
        self.after_call.write_cleanup()
        self.after_call.write_code('return py_retval;')

        ## now write out the wrapper function body itself
        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_parse.sink.flush_to(code_sink)
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)


class ReturnValue(object):
    '''Abstract base class for all classes dedicated to handle
    specific return value types'''

    class __metaclass__(type):
        "Metaclass for automatically registering parameter type handlers"
        def __init__(mcs, name, bases, dict_):
            "metaclass __init__"
            type.__init__(mcs, name, bases, dict_)
            if __debug__:
                try:
                    iter(mcs.CTYPES)
                except TypeError:
                    print "ERROR: missing CTYPES on class ", mcs
            for ctype in mcs.CTYPES:
                return_type_matcher.register(ctype, mcs)

    ## list of C type names it can handle
    CTYPES = []

    def __init__(self, ctype):
        '''
        Creates a return value object

        Keywork Arguments:

        ctype -- actual C/C++ type being used
        '''
        self.ctype = ctype

    def get_c_error_return(self):
        '''Return a "return <value>" code string, for use in case of error'''
        raise NotImplementedError

    def convert_python_to_c(self, wrapper):
        '''
        Writes code to convert the Python return value into the C "retval" variable.
        '''
        raise NotImplementedError
        #assert isinstance(wrapper, ReverseWrapperBase)

    def convert_c_to_python(self, wrapper):
        '''
        Writes code to convert the C return value the Python return.
        '''
        raise NotImplementedError
        #assert isinstance(wrapper, ReverseWrapperBase)

ReturnValue.CTYPES = NotImplemented


class Parameter(object):
    '''Abstract base class for all classes dedicated to handle specific parameter types'''

    class __metaclass__(type):
        "Metaclass for automatically registering parameter type handlers"
        def __init__(mcs, name, bases, dict_):
            "metaclass __init__"
            type.__init__(mcs, name, bases, dict_)
            if __debug__:
                try:
                    iter(mcs.CTYPES)
                except TypeError:
                    print "ERROR: missing CTYPES on class ", mcs
            for ctype in mcs.CTYPES:
                param_type_matcher.register(ctype, mcs)

    ## bit mask values
    DIRECTION_IN = 1
    DIRECTION_OUT = 2

    ## list of possible directions for this type
    DIRECTIONS = NotImplemented

    ## list of C type names it can handle
    CTYPES = []
    
    def __init__(self, ctype, name, direction=DIRECTION_IN):
        '''
        Creates a parameter object

        Keywork Arguments:

        ctype -- actual C/C++ type being used
        name -- parameter name
        direction -- direction of the parameter transfer, valid values
                     are DIRECTION_IN, DIRECTION_OUT, and
                     DIRECTION_IN|DIRECTION_OUT
        '''
        self.ctype = ctype
        self.name = name
        assert direction in self.DIRECTIONS
        self.direction = direction

    def convert_c_to_python(self, wrapper):
        '''Write some code before calling the Python method.'''
        #assert isinstance(wrapper, ReverseWrapperBase)
        raise NotImplementedError

    def convert_python_to_c(self, wrapper):
        '''Write some code before calling the C method.'''
        #assert isinstance(wrapper, ReverseWrapperBase)
        raise NotImplementedError

Parameter.CTYPES = NotImplemented


class TypeMatcher(object):
    """Type matcher object: maps C type names to classes that handle those types"""
    
    def __init__(self):
        """Constructor"""
        self._types = {}

    def register(self, name, type_handler):
        """Register a new handler class for a given C type
        name -- C type name
        type_handler -- class to handle this C type
        """
        if name in self._types:
            raise ValueError("return type %s already registered" % (name,))
        self._types[name] = type_handler
        
    def lookup(self, name):
        "Returns a handler with the given ctype name, or raises KeyError"
        return self._types[name]

    def items(self):
        "Returns an iterator over all registered items"
        return self._types.iteritems()


return_type_matcher = TypeMatcher()
param_type_matcher = TypeMatcher()

