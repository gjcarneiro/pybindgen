// -*- C++ -*-

#include <boost/smart_ptr/shared_ptr.hpp>

class TestClass {
 public:
       typedef boost::shared_ptr< TestClass > Ptr;
 public:
};


TestClass::Ptr someFct();

