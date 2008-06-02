
"""

Introduction
============

  PyBindGen is a Python module that lets you generate python language bindings for C or C++ code.

How to use it
=============

 There are multiple ways to use PyBindGen, and they are described in the following subsections.

 Basic Interface
 ---------------

  PyBindGen does not have any command-line interface.  The author
  needs to write a small python script that imports the pybindgen
  module and uses it to generate the bindings.  For instance::

    #! /usr/bin/env python

    import sys

    import pybindgen
    from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)

    def my_module_gen(out_file):
        pybindgen.write_preamble(FileCodeSink(out_file))

        mod = Module('a')
        mod.add_include('"a.h"')

        mod.add_function('ADoA', None, [])
        mod.add_function('ADoB', None, [Parameter.new('uint32_t', 'b')])
        mod.add_function('ADoC', ReturnValue.new('uint32_t'), [])

        mod.generate(FileCodeSink(out_file) )

    if __name__ == '__main__':
        my_module_gen(sys.stdout)


  Running the above python script will generate to stdout the source code for a C library with the following interface::

    #include <stdint.h>

    void ADoA (void);
    void ADoB (uint32_t b);
    uint32_t ADoC (void);

  The most important classes to retain from pybindgen are:

    - L{CodeSink}, which is an object that pybindgen uses to receive
      the generated code.  Typically we want to use a subclass of it
      called L{FileCodeSink}, which receives generated code and writes
      it to a file-like object;

    - L{Module}, which represents a Python extension module.  The
      progammer can L{add functions<Module.add_function>},
      L{classes<Module.add_class>}, L{enums<Module.add_enum>}, or even
      L{other modules<Module.add_cpp_namespace>} to a module object.  The
      module object is the main front-end for L{code
      generation<Module.generate>}, and it "owns" every other object.

    - Then there are objects to represent L{functions<Function>},
      L{C++ classes<CppClass>}, L{enumerations<Enum>}, etc.  These
      additionally make use of objects that represent L{return
      values<ReturnValue>} and L{parameters<Parameter>}.

 Basic Interface with Error Handling
 -----------------------------------

  It is also possible to declare a error handler.  The error handler
  will be invoked for API definitions that cannot be wrapped for some
  reason::

    #! /usr/bin/env python

    import sys

    import pybindgen
    from pybindgen import Module, FileCodeSink, retval, param

    import pybindgen.settings
    import warnings

    class ErrorHandler(pybindgen.settings.ErrorHandler):
        def handle_error(self, wrapper, exception, traceback_):
            warnings.warn("exception %r in wrapper %s" % (exception, wrapper))
            return True
    pybindgen.settings.error_handler = ErrorHandler()


    def my_module_gen(out_file):
        pybindgen.write_preamble(FileCodeSink(out_file))

        mod = Module('a')
        mod.add_include('"a.h"')

        mod.add_function('ADoA', None, [])
        mod.add_function('ADoB', None, [param('uint32_t', 'b')])
        mod.add_function('ADoC', retval('uint32_t'), [])

        mod.generate(FileCodeSink(out_file) )

    if __name__ == '__main__':
        my_module_gen(sys.stdout)

  In this example, we register a error handler that allows PyBindGen
  to simply ignore API definitions with errors, and not wrap them, but
  move on.

  The difference between is Parameter.new(...) and param(...), as well
  as between ReturnValue.new(...) and retval(...) is to be noted here.
  The main difference is not that param(...) and retval(...) are
  shorter, it is that they allow delayed error handling.  For example,
  when you put Parameter.new("type that does not exist", "foo") in
  your python script, a TypeLookupError exception is raised and it is
  not possible for the error handler to catch it.  However, param(...)
  does not try to lookup the type handler immediately and instead lets
  Module.add_function() do that in a way that the error handler can be
  invoked and the function is simply not wrapped if the error handler
  says so.

 Header file scanning with (py)gccxml
 ------------------------------------

  If you have gccxml and pygccxml installed, PyBindGen can use them to
  scan the API definitions directly from the header files::

    #! /usr/bin/env python

    import sys

    import pybindgen
    from pybindgen import FileCodeSink
    from pybindgen.gccxmlparser import ModuleParser

    def my_module_gen():
        module_parser = ModuleParser('a1', '::')
        module = module_parser.parse([sys.argv[1]])
        module.add_include('"a.h"')

        pybindgen.write_preamble(FileCodeSink(sys.stdout))
        module.generate(FileCodeSink(sys.stdout))

    if __name__ == '__main__':
        my_module_gen()
  
  The above script will generate the bindings for the module directly.
  It expects the input header file, a.h, as first command line
  argument.

 Header file scanning with (py)gccxml: python intermediate file
 --------------------------------------------------------------

  The final code generation flow supported by PyBindGen is a hybrid of
  the previous ones.  One script scans C/C++ header files, but instead
  of generating C/C++ binding code directly it instead generates a
  PyBindGen based Python script::

    #! /usr/bin/env python

    import sys

    from pybindgen import FileCodeSink
    from pybindgen.gccxmlparser import ModuleParser

    def my_module_gen():
        module_parser = ModuleParser('a2', '::')
        module_parser.parse([sys.argv[1]], includes=['"a.h"'], pygen_sink=FileCodeSink(sys.stdout))

    if __name__ == '__main__':
        my_module_gen()
 
  The above script produces a Python program on stdout.  Running the
  generated Python program will, in turn, generate the C++ code
  binding our interface.

"""


from typehandlers.base import ReturnValue, Parameter
from module import Module
from function import Function
from typehandlers.codesink import CodeSink, FileCodeSink
from cppclass import CppMethod, CppClass, CppConstructor
from enum import Enum
from utils import write_preamble, param, retval
import version


