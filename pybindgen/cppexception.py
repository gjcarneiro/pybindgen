

import settings
import utils


class CppException(object):
    def __init__(self, name, parent=None, outer_class=None, custom_name=None):
        self.name = name
        self.full_name = None
        self.parent = parent
        self._module = None
        self.outer_class = outer_class
        self.custom_name = custom_name
        self.mangled_name = None
        self.mangled_full_name = None
        self.pytypestruct = None

    def __repr__(self):
        return "<pybindgen.Container %r>" % self.full_name
    
    def get_module(self):
        """Get the Module object this type belongs to"""
        return self._module

    def set_module(self, module):
        """Set the Module object this type belongs to"""
        self._module = module
        self._update_names()

    module = property(get_module, set_module)

    def _update_names(self):
        
        prefix = settings.name_prefix.capitalize()

        if self.outer_class is None:
            if self._module.cpp_namespace_prefix:
                if self._module.cpp_namespace_prefix == '::':
                    self.full_name = '::' + self.name
                else:
                    self.full_name = self._module.cpp_namespace_prefix + '::' + self.name
            else:
                self.full_name = self.name
        else:
            self.full_name = '::'.join([self.outer_class.full_name, self.name])

        def make_upper(s):
            if s and s[0].islower():
                return s[0].upper()+s[1:]
            else:
                return s

        def flatten(name):
            "make a name like::This look LikeThis"
            return ''.join([make_upper(utils.mangle_name(s)) for s in name.split('::')])

        self.mangled_name = flatten(self.name)
        self.mangled_full_name = utils.mangle_name(self.full_name)

        self.pytypestruct = "Py%s%s_Type" % (prefix,  self.mangled_full_name)

    def _get_python_name(self):
        if self.custom_name is None:
            class_python_name = self.mangled_name
        else:
            class_python_name = self.custom_name
        return class_python_name

    python_name = property(_get_python_name)

    def _get_python_full_name(self):
        if self.outer_class is None:
            mod_path = self._module.get_module_path()
            mod_path.append(self.python_name)
            return '.'.join(mod_path)
        else:
            return '%s.%s' % (self.outer_class.pytype.slots['tp_name'], self.python_name)
    python_full_name = property(_get_python_full_name)


    def generate_forward_declarations(self, code_sink, dummy_module):
        code_sink.writeln()
        code_sink.writeln('extern PyTypeObject *%s;' % (self.pytypestruct,))
        code_sink.writeln()


    def generate(self, code_sink, module, docstring=None):
        """Generates the class to a code sink"""
        code_sink.writeln('PyTypeObject *%s;' % (self.pytypestruct,))
        ## --- register the class type in the module ---
        module.after_init.write_code("/* Register the '%s' exception */" % self.full_name)
        if self.parent is None:
            parent = 'NULL'
        else:
            parent = "(PyObject*) "+self.parent.pytypestruct
        module.after_init.write_error_check('(%s = (PyTypeObject*) PyErr_NewException((char*)"%s", %s, NULL)) == NULL'
                                            % (self.pytypestruct, self.python_full_name, parent))
        if docstring:
            module.after_init.write_code("%s->tp_doc = (char*)\"%s\";" % (self.pytypestruct, docstring))

        if self.outer_class is None:
            module.after_init.write_code(
                'Py_INCREF((PyObject *) %s);\n'
                'PyModule_AddObject(m, (char *) \"%s\", (PyObject *) %s);' % (
                self.pytypestruct, self.python_name, self.pytypestruct))
        else:
            module.after_init.write_code(
                'Py_INCREF((PyObject *) %s);\n'
                'PyDict_SetItemString((PyObject*) %s.tp_dict, (char *) \"%s\", (PyObject *) %s);' % (
                self.pytypestruct, self.outer_class.pytypestruct, self.python_name, self.pytypestruct))
