# pylint: disable-msg=W0105

"""

Global settings to the code generator.

"""

name_prefix = ''
"""
Prefix applied to global declarations, such as instance and type
structures.
"""

automatic_type_narrowing = False
"""
Default value for the automatic_type_narrowing parameter of C++ classes.
"""

allow_subclassing = False
"""
Allow generated classes to be subclassed by default.
"""

unblock_threads = False
"""
Generate code to support threads.
When True, by default methods/functions/constructors will unblock
threads around the funcion call, i.e. allows other Python threads to
run during the call.
"""


class ErrorHandler(object):
    def handle_error(self, wrapper, exception, traceback_):
        """
        Handles a code generation error.  Should return True to tell
        pybindgen to ignore the error and move on to the next wrapper.
        Returning False will cause pybindgen to allow the exception to
        propagate, thus aborting the code generation procedure.
        """
        raise NotImplementedError

error_handler = None
"""
Custom error handling.
Error handler, or None.  When it is None, code generation exceptions
propagate to the caller.  Else it can be a
pybindgen.utils.ErrorHandler subclass instance that handles the error.
"""
