"""
The class that generates code to keep track of existing python
wrappers for a given root class.
"""

from typehandlers.base import NotSupportedError


class WrapperRegistry(object):
    """
    Abstract base class for wrapepr registries.
    """

    def __init__(self, base_name):
        self.base_name = base_name

    def generate_forward_declarations(self, code_sink, module):
        raise NotImplementedError

    def generate(self, code_sink, module):
        raise NotImplementedError

    def write_register_new_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        raise NotImplementedError
        
    def write_lookup_wrapper(self, code_block, wrapper_type, wrapper_lvalue, object_rvalue):
        raise NotImplementedError

    def write_unregister_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        raise NotImplementedError

    
class NullWrapperRegistry(object):
    """
    A 'null' wrapper registry class.  It produces no code, and does
    not guarantee that more than one wrapper cannot be created for
    each object.  Use this class to disable wrapper registries entirely.
    """

    def __init__(self, base_name):
        super(NullWrapperRegistry, self).__init__(base_name)

    def generate_forward_declarations(self, code_sink, module):
        pass

    def generate(self, code_sink, module):
        pass

    def write_register_new_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        pass
        
    def write_lookup_wrapper(self, code_block, wrapper_type, wrapper_lvalue, object_rvalue):
        raise NotSupportedError

    def write_unregister_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        pass


class StdMapWrapperRegistry(object):
    """
    A wrapper registry that uses std::map as implementation.  Do not
    use this if generating pure C wrapping code, else the code will
    not compile.
    """

    def __init__(self, base_name):
        super(StdMapWrapperRegistry, self).__init__(base_name)
        self.map_name = "%s_wrapper_registry" % base_name

    def generate_forward_declarations(self, code_sink, module):
        #module.add_include("<map>")
        code_sink.writeln("#include <map>")
        code_sink.writeln("extern std::map<void*, PyObject*> %s;" % self.map_name)

    def generate(self, code_sink, dummy_module):
        code_sink.writeln("std::map<void*, PyObject*> %s;" % self.map_name)

    def write_register_new_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        code_block.write_code("%s[(void *) %s] = (PyObject *) %s;" % (self.map_name, object_rvalue, wrapper_lvalue))
        
    def write_lookup_wrapper(self, code_block, wrapper_type, wrapper_lvalue, object_rvalue):
        iterator = code_block.declare_variable("std::map<void*, PyObject*>::const_iterator", "wrapper_lookup_iter")
        code_block.write_code("%s = %s.find((void *) %s);" % (iterator, self.map_name, object_rvalue))
        code_block.write_code("if (%(ITER)s == %(MAP)s.end()) {\n"
                              "    %(WRAPPER)s = NULL;\n"
                              "} else {\n"
                              "    %(WRAPPER)s = (%(TYPE)s *) %(ITER)s->second;\n"
                              "    Py_INCREF(%(WRAPPER)s);\n"
                              "}\n"
                              % dict(ITER=iterator, MAP=self.map_name, WRAPPER=wrapper_lvalue, TYPE=wrapper_type))
        
    def write_unregister_wrapper(self, code_block, dummy_wrapper_lvalue, object_rvalue):
        code_block.write_code("%s.erase((void *) %s);" % (self.map_name, object_rvalue))

