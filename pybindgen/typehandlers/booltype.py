
class BooleanReturn(ReturnType):
    def get_c_type(self):
        return "gboolean"
    def write_decl(self):
        self.wrapper.add_declaration("gboolean retval;")
        self.wrapper.add_declaration("PyObject *py_main_retval;")
    def write_error_return(self):
        self.wrapper.write_code("return FALSE;")
    def write_conversion(self):
        self.wrapper.add_pyret_parse_item("O", "&py_main_retval", prepend=True)
        self.wrapper.write_code(
            "retval = PyObject_IsTrue(py_main_retval)? TRUE : FALSE;",
            code_sink=self.wrapper.post_return_code)
type_matcher.register_ret("gboolean", BooleanReturn)

class BooleanParam(Parameter):
    def get_c_type(self):
        return "gboolean"
    def convert_c2py(self):
        self.wrapper.add_declaration("PyObject *py_%s;" % self.name)
        self.wrapper.write_code("py_%s = %s? Py_True : Py_False;"
                                % (self.name, self.name))
        self.wrapper.add_pyargv_item("py_%s" % self.name)

type_matcher.register("gboolean", BooleanParam)


