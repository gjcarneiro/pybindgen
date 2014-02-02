#! /usr/bin/env python
from __future__ import unicode_literals, print_function

import sys
import os.path

import pybindgen
from pybindgen.module import MultiSectionFactory
from pybindgen import (FileCodeSink)

import foomodulegen_split
import foomodulegen_common


class MyMultiSectionFactory(MultiSectionFactory):

    def __init__(self, main_file_name):
        self.main_file_name = main_file_name
        self.main_sink = FileCodeSink(open(main_file_name, "wt"))
        self.header_name = "foomodule4.h"
        header_file_name = os.path.join(os.path.dirname(self.main_file_name), self.header_name)
        self.header_sink = FileCodeSink(open(header_file_name, "wt"))
        self.section_sinks = {}

    def get_section_code_sink(self, section_name):
        if section_name == '__main__':
            return self.main_sink
        try:
            return self.section_sinks[section_name]
        except KeyError:
            file_name = os.path.join(os.path.dirname(self.main_file_name), "%s.cc" % section_name)
            sink = FileCodeSink(open(file_name, "wt"))
            self.section_sinks[section_name] = sink
            return sink

    def get_main_code_sink(self):
        return self.main_sink

    def get_common_header_code_sink(self):
        return self.header_sink

    def get_common_header_include(self):
        return '"%s"' % self.header_name

    def close(self):
        self.header_sink.file.close()
        self.main_sink.file.close()
        for sink in self.section_sinks.values():
            sink.file.close()

def my_module_gen():
    out = MyMultiSectionFactory(sys.argv[1])
    root_module = foomodulegen_split.module_init()
    root_module.add_exception('exception', foreign_cpp_namespace='std', message_rvalue='%(EXC)s.what()')

    foomodulegen_split.register_types(root_module)
    foomodulegen_split.register_methods(root_module)
    foomodulegen_split.register_functions(root_module)
    foomodulegen_common.customize_module(root_module)

    root_module.generate(out)

    out.close()



if __name__ == '__main__':
    try:
        import cProfile as profile
    except ImportError:
        my_module_gen()
    else:
        print("** running under profiler", file=sys.stderr)
        profile.run('my_module_gen()', 'foomodulegen4.pstat')

