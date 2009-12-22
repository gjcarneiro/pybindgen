// -*- Mode: C++; c-file-style: "stroustrup"; indent-tabs-mode:nil; -*-
#include "testapi.h"

#include <boost/python.hpp>

BOOST_PYTHON_MODULE(testapi_boost)
{
    using namespace boost::python;
    def("func1", func1);
    def("func2", func2);

    class_<Multiplier>("Multiplier")
        .def(init<double>())
        .def("GetFactor", &Multiplier::GetFactor)
        .def("Multiply", &Multiplier::Multiply)
        ;
    
}

