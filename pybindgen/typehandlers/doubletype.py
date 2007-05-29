
class DoubleParam(Parameter):
    def get_c_type(self):
        return self.props.get('c_type', 'gdouble')
    def convert_c2py(self):
        self.wrapper.add_declaration("PyObject *py_%s;" % self.name)
        self.wrapper.write_code(code=("py_%s = PyFloat_FromDouble(%s);" %
                                      (self.name, self.name)),
                                cleanup=("Py_DECREF(py_%s);" % self.name))
        self.wrapper.add_pyargv_item("py_%s" % self.name)

class DoublePtrParam(Parameter):
    def __init__(self, wrapper, name, **props):
        if "direction" not in props:
            raise argtypes.ArgTypeConfigurationError(
                "cannot use double* parameter without direction")
        if props["direction"] not in ("out", ): # inout not yet implemented
            raise argtypes.ArgTypeConfigurationError(
                "cannot use double* parameter with direction '%s'"
                % (props["direction"],))
        Parameter.__init__(self, wrapper, name, **props)
    def get_c_type(self):
        return self.props.get('c_type', 'double*')
    def convert_c2py(self):
        self.wrapper.add_pyret_parse_item("d", self.name)
for argtype in ('double*', 'gdouble*'):
    type_matcher.register(argtype, DoublePtrParam)

class DoubleReturn(ReturnType):
    def get_c_type(self):
        return self.props.get('c_type', 'gdouble')
    def write_decl(self):
        self.wrapper.add_declaration("%s retval;" % self.get_c_type())
    def write_error_return(self):
        self.wrapper.write_code("return -G_MAXFLOAT;")
    def write_conversion(self):
        self.wrapper.add_pyret_parse_item("d", "&retval", prepend=True)

for argtype in ('float', 'double', 'gfloat', 'gdouble'):
    type_matcher.register(argtype, DoubleParam)
    type_matcher.register_ret(argtype, DoubleReturn)


