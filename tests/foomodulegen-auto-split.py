#! /usr/bin/env python

import sys
import os.path

import pybindgen
from pybindgen.typehandlers import base as typehandlers
from pybindgen import (ReturnValue, Parameter, Module, Function, FileCodeSink)
from pybindgen import (CppMethod, CppConstructor, CppClass, Enum)
from pybindgen.gccxmlparser import ModuleParser, PygenClassifier, PygenSection
from pybindgen.function import CustomFunctionWrapper
from pybindgen.cppmethod import CustomCppMethodWrapper

import foomodulegen_common


class MyPygenClassifier(PygenClassifier):
    def classify(self, pygccxml_definition):
        if pygccxml_definition.name.lower() <= 'l':
            return 'foomodulegen_module1'
        else:
            return 'foomodulegen_module2'


def my_module_gen():
    pygen = [
        PygenSection('__main__', FileCodeSink(open(sys.argv[2], "wt"))),
        PygenSection('foomodulegen_module1', FileCodeSink(open(sys.argv[3], "wt"))),
        PygenSection('foomodulegen_module2', FileCodeSink(open(sys.argv[4], "wt"))),
        ]
    module_parser = ModuleParser('foo4', '::')
    module_parser.parse([sys.argv[1]], includes=['"foo.h"'], pygen_sink=pygen, pygen_classifier=MyPygenClassifier())
    for sect in pygen:
        sect.code_sink.file.close()


if __name__ == '__main__':
    try:
        import cProfile as profile
    except ImportError:
        my_module_gen()
    else:
        print >> sys.stderr, "** running under profiler"
        profile.run('my_module_gen()', 'foomodulegen-auto-split.pstat')

