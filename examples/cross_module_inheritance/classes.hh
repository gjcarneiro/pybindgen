#ifndef __PYBINDGEN_CROSS_MODULE_EXAMPLE_CLASSES_HH__
#define __PYBINDGEN_CROSS_MODULE_EXAMPLE_CLASSES_HH__

#include <iostream>

class Base {
public:
  Base() { std::cerr << "Base::Base()" << std::endl; }
  virtual ~Base() { std::cerr << "Base::~Base()" << std::endl; }
  virtual void do_something() const { std::cerr << "Base::do_something()" << std::endl; }
};

class Derived: public Base {
public:
  Derived(): Base() { std::cerr << "Derived::Derived()" << std::endl; }
  virtual ~Derived() { std::cerr << "Derived::~Derived()" << std::endl; }
  virtual void do_something() const { std::cerr << "Derived::do_something()" << std::endl; }
};

#endif
