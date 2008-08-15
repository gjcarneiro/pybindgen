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

int get_int_from_string(const char *from_string, int multiplier)
{
    return atoi(from_string)*multiplier;
}

int get_int_from_float(double from_float, int multiplier)
{
    return (int) from_float*multiplier;
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


static SomeObject *g_someObject = 0;

// Transfer ownership of 'obj' to the library
void store_some_object(SomeObject *obj)
{
    delete g_someObject;
    g_someObject = obj;
}

// Invokes the virtual method in the stored SomeObject
std::string invoke_some_object_get_prefix()
{
    if (g_someObject)
        return g_someObject->get_prefix();
    else
        return std::string();
}

// Transfer ownership of 'obj' away from the library
SomeObject* take_some_object()
{
    SomeObject *retval = g_someObject;
    g_someObject = 0;
    return retval;
}

// Deletes the contained object, if any
void delete_some_object()
{
    delete g_someObject;
    g_someObject = 0;
}


namespace xpto
{
    std::string some_function()
    {
        return "hello";
    }

    std::string get_foo_datum(FooXpto const &foo)
    {
        return foo.get_datum();
    }

}


Foo g_foo;

void function_that_takes_foo(Foo foo)
{
    g_foo = foo;
}

Foo function_that_returns_foo()
{
    return g_foo;
}

int Foo::instance_count = 0;
int SomeObject::NestedClass::instance_count = 0;
int Foobar::instance_count = 0;

Foobar* get_foobar_with_other_as_custodian (const SomeObject *other)
{
    other++;
    return new Foobar;
}

Foobar* create_new_foobar()
{
    return new Foobar;
}

void set_foobar_with_other_as_custodian(Foobar *foobar, const SomeObject *other)
{
    foobar++;
    other++;
}

SomeObject * set_foobar_with_return_as_custodian(Foobar *foobar)
{
    foobar++;
    return new SomeObject("xxx");
}

std::string some_object_get_something_prefixed(const SomeObject *obj, const std::string something)
{
    return obj->get_prefix() + something;
}

std::string some_object_val_get_something_prefixed(SomeObject obj, const std::string something)
{
    return obj.get_prefix() + something;
}

std::string some_object_ref_get_something_prefixed(const SomeObject &obj, const std::string something)
{
    return obj.get_prefix() + something;
}

namespace xpto
{
    FooType g_fooType;
    FooType get_foo_type ()
    {
        return g_fooType;
    }
    void set_foo_type (FooType type)
    {
        g_fooType = type;
    }
}


SingletonClass *SingletonClass::m_instance = NULL;

InterfaceId make_interface_id ()
{
    return InterfaceId ();
}

template <> std::string TypeNameGet<int> (void)
{
    return "int";
}


static Zbr *g_zbr = NULL;
int Zbr::instance_count = 0;

void store_zbr (Zbr *zbr)
{
    if (g_zbr)
        g_zbr->Unref ();
    g_zbr = zbr;
}

int invoke_zbr (int x)
{
    return g_zbr->get_int (x);
}

void delete_stored_zbr (void)
{
    if (g_zbr)
        g_zbr->Unref ();
    g_zbr = NULL;
}

float matrix_sum_of_elements (float *matrix)
{
    float result = 0;
    for (int i = 0; i < 6; i++)
        result += matrix[i];
    return result;
}

void matrix_identity_new (float *matrix)
{
    matrix[0] = 1;
    matrix[1] = 0;
    matrix[2] = 0;
    matrix[3] = 0;
    matrix[4] = 1;
    matrix[5] = 0;
}

static SimpleStructList g_simpleList;

SimpleStructList get_simple_list ()
{
    SimpleStructList retval;
    for (int i = 0; i < 10; i++)
    {
        simple_struct_t val = {i};
        retval.push_back(val);
    }
    return retval;
}

int set_simple_list (SimpleStructList list)
{
    g_simpleList = list;
    return g_simpleList.size ();
}

