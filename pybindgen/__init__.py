
"""

Introduction
============

  PyBindGen is a Python module that lets you generate python language bindings for C or C++ code.

How to use it
=============

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

        mod.add_function(Function(ReturnValue.new('void'), 'ADoA', []))
        mod.add_function(Function(ReturnValue.new('void'), 'ADoB', [Parameter.new('uint32_t', 'b')]))
        mod.add_function(Function(ReturnValue.new('uint32_t'), 'ADoC', []))

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

"""


from typehandlers.base import ReturnValue, Parameter
from module import Module
from function import Function
from typehandlers.codesink import CodeSink, FileCodeSink
from cppclass import CppMethod, CppClass, CppConstructor
from enum import Enum
from utils import write_preamble
import version


