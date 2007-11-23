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
When True, by default methods/functions/constructors will unblock
threads around the funcion call, i.e. allows other Python threads to
run during the call.
"""
