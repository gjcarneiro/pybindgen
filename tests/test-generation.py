#!/usr/bin/env python

import sys

import pybindgen
from pybindgen import typehandlers
from pybindgen.typehandlers import codesink
from pybindgen.typehandlers.base import Parameter, ReturnValue
from pybindgen.function import Function
from pybindgen.module import Module
from pybindgen import cppclass


class MyReverseWrapper(typehandlers.base.ReverseWrapperBase):
    def generate_python_call(self):
        params = ['NULL'] # function object to call
        params.extend(self.build_params.get_parameters())
        self.before_call.write_code('py_retval = PyObject_CallFunction(%s);' % (', '.join(params),))
        self.before_call.write_error_check('py_retval == NULL')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')

        

def test():
    pybindgen.write_preamble(codesink.FileCodeSink(sys.stdout))
    print
    print "#include <string>"
    print

    ## Declare a dummy class
    sys.stdout.write('''
class Foo
{
    std::string m_datum;
public:
    Foo () : m_datum ("")
        {}
    Foo (std::string datum) : m_datum (datum)
        {}
    std::string get_datum () const { return m_datum; }

    Foo (Foo const & other) : m_datum (other.get_datum ())
        {}
};
''')

    module = Module("foo")
    code_out = codesink.FileCodeSink(sys.stdout)

    ## Register type handlers for the class
    Foo = cppclass.CppClass('Foo')
    Foo.full_name = Foo.name # normally adding the class to a module would take care of this
    Foo.generate_forward_declarations(code_out)

    wrapper_number = 0

    ## test return type handlers of reverse wrappers
    for return_type, return_handler in typehandlers.base.return_type_matcher.items():
        if issubclass(return_handler, (cppclass.CppClassPtrReturnValue,
                                       typehandlers.pyobjecttype.PyObjectReturnValue)):
            for caller_owns_return in True, False:
                retval = return_handler(return_type, caller_owns_return=caller_owns_return)
                wrapper = MyReverseWrapper(retval, [])
                wrapper_number += 1
                try:
                    wrapper.generate(code_out,
                                     '_test_wrapper_number_%i' % (wrapper_number,),
                                     ['static'])
                except NotImplementedError:
                    print >> sys.stderr, \
                        ("ReverseWrapper %s(void) (caller_owns_return=%r)"
                         " could not be generated: not implemented"
                         % (retval.ctype, caller_owns_return))
                print
        else:
            retval = return_handler(return_type)
            wrapper = MyReverseWrapper(retval, [])
            wrapper_number += 1
            try:
                wrapper.generate(code_out,
                                 '_test_wrapper_number_%i' % (wrapper_number,),
                                 ['static'])
            except NotImplementedError:
                print >> sys.stderr, ("ReverseWrapper %s(void) could not be generated: not implemented"
                                      % (retval.ctype,))
            print


    ## test parameter type handlers of reverse wrappers
    for param_type, param_handler in typehandlers.base.param_type_matcher.items():
        for direction in param_handler.DIRECTIONS:
            if direction == (Parameter.DIRECTION_IN):
                param_name = 'param'
            elif direction == (Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT):
                param_name = 'param_inout'
            elif direction == (Parameter.DIRECTION_OUT):
                param_name = 'param_out'
            param = param_handler(param_type, param_name, direction)

            if 'const' in param.ctype and direction&Parameter.DIRECTION_OUT:
                continue

            wrapper = MyReverseWrapper(ReturnValue.new('void'), [param])
            wrapper_number += 1
            try:
                wrapper.generate(code_out,
                                 '_test_wrapper_number_%i' % (wrapper_number,),
                                 ['static'])
            except NotImplementedError:
                print >> sys.stderr, ("ReverseWrapper void(%s) could not be generated: not implemented"
                                      % (param.ctype))
            print
    
    ## test generic forward wrappers, and module

    for return_type, return_handler in typehandlers.base.return_type_matcher.items():
        wrapper_number += 1
        function_name = 'foo_function_%i' % (wrapper_number,)
        ## declare a fake prototype
        print "%s %s(void);" % (return_type, function_name)
        print

        if issubclass(return_handler, (cppclass.CppClassPtrReturnValue,
                                       typehandlers.pyobjecttype.PyObjectReturnValue)):
            retval = return_handler(return_type, caller_owns_return=True)
        else:
            retval = return_handler(return_type)

        wrapper = Function(retval, function_name, [])
        module.add_function(wrapper)
    
    for param_type, param_handler in typehandlers.base.param_type_matcher.items():
        for direction in param_handler.DIRECTIONS:
            if direction == (Parameter.DIRECTION_IN):
                param_name = 'param'
            elif direction == (Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT):
                param_name = 'param_inout'
            elif direction == (Parameter.DIRECTION_OUT):
                param_name = 'param_out'

            if issubclass(param_handler, (cppclass.CppClassPtrParameter,
                                          typehandlers.pyobjecttype.PyObjectParam)):
                for transfer_ownership in True, False:
                    name = param_name + (transfer_ownership and '_transfer' or '_notransfer')
                    param = param_handler(param_type, name , transfer_ownership=transfer_ownership)
                    wrapper_number += 1
                    function_name = 'foo_function_%i' % (wrapper_number,)
                    ## declare a fake prototype
                    print "void %s(%s %s);" % (function_name, param_type, name)
                    print
                    wrapper = Function(ReturnValue.new('void'), function_name, [param])
                    module.add_function(wrapper)
            else:
                param = param_handler(param_type, param_name, direction)
                wrapper_number += 1
                function_name = 'foo_function_%i' % (wrapper_number,)
                ## declare a fake prototype
                print "void %s(%s);" % (function_name, param_type)
                print
                wrapper = Function(ReturnValue.new('void'), function_name, [param])
                module.add_function(wrapper)

    module.generate(code_out)



if __name__ == '__main__':
    test()
