import os
from pybindgen import *

#-------------------------------------------------------------------------------
# This is the implementation of the multi-section factory that allows us to
# write multiple source files for compiling.
# 
# This is directly cribbed from Gustavo's example from the ns3 package at
# http://code.nsnam.org/ns-3-dev/file/e15adc7172f1/bindings/python/ns3modulegen.py
#-------------------------------------------------------------------------------
class ModuleGenerationFactory(module.MultiSectionFactory):

    def __init__(self, main_file_name, modules):
        print "main file name: ", main_file_name
        print "modules:  ", modules
        self.basename, ext = os.path.splitext(main_file_name)
        super(ModuleGenerationFactory, self).__init__()
        self.main_file_name = main_file_name
        self.main_sink = FileCodeSink(open(main_file_name, "wt"))
        self.header_name = self.basename + ".hh"
        header_file_name = os.path.join(os.path.dirname(self.main_file_name), 
                                        '.',
                                        self.header_name)
        self.header_sink = FileCodeSink(open(header_file_name, "wt"))
        self.section_sinks = {'__main__': self.main_sink}
        for module in modules:
            section_name = '%s_%s' % (self.basename, module.replace('-', '_'))
            file_name = os.path.join(os.path.dirname(self.main_file_name), "%s.C" % section_name)
            sink = FileCodeSink(open(file_name, "wt"))
            self.section_sinks[section_name] = sink            

    def get_section_code_sink(self, section_name):
        return self.section_sinks[section_name]

    def get_main_code_sink(self):
        return self.main_sink

    def get_common_header_code_sink(self):
        return self.header_sink

    def get_common_header_include(self):
        return '"%s"' % self.header_name

    def close(self):
        self.header_sink.file.close()
        self.main_sink.file.close()
        for sink in self.section_sinks.itervalues():
            sink.file.close()
