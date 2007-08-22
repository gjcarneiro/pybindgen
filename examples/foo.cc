#include "foo.h"
#include <iostream>
#include <string.h>
#include <stdlib.h>

int print_something(const char *message)
{
    std::cout << "MESSAGE1: " << message << std::endl;
    return strlen(message);
}

int print_something_else(const char *message2)
{
    std::cout << "MESSAGE2: " << message2 << std::endl;
    return strlen(message2);
}

int get_int_from_string(const char *from_string)
{
    return atoi(from_string);
}

int get_int_from_float(double from_float)
{
    return (int) from_float;
}


std::string SomeObject::staticData = std::string("Hello Static World!");

int SomeObject::get_int (const char *from_string)
{
    return atoi(from_string);
}

int SomeObject::get_int (double from_float)
{
    return (int) from_float;
}

int SomeObject::instance_count = 0;

class HiddenClass : public Bar
{
};


Foo*
get_hidden_subclass_pointer ()
{
    return new HiddenClass;
}

