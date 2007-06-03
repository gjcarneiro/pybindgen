// -*- Mode: C++; c-file-style: "stroustrup"; indent-tabs-mode:nil; -*-
#ifndef   	FOO_H_
# define   	FOO_H_

#include <string>

// Yes, this code is stupid, I know; it is only meant as an example!

int print_something(const char *message);
int print_something_else(const char *message2);

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

class Bar : public Foo
{

};

class SomeObject
{
    std::string m_prefix;
    Foo m_foo_value;
    Foo *m_foo_ptr;
    Foo *m_foo_shared_ptr;

public:
    SomeObject (std::string const prefix)
        : m_prefix (prefix), m_foo_ptr (0),
          m_foo_shared_ptr (0)
        {}

    int add_prefix (std::string& message) {
        message = m_prefix + message;
        return message.size ();
    }

    // pass by value, direction=in
    void set_foo_value (Foo foo) {
        m_foo_value = foo;
    }

    // pass by reference, direction=in
    void set_foo_ref (Foo& foo) {
        m_foo_value = foo;
    }

    // pass by reference, direction=out
    void peek_foo_ref (Foo& foo) {
        foo = m_foo_value;
    }

    // pass by pointer, direction=in, transfers ownership
    void set_foo_ptr (Foo *foo) {
        if (m_foo_ptr)
            delete m_foo_ptr;
        m_foo_ptr = foo;
    }

    // pass by pointer, direction=in, doesn't transfer ownership
    void set_foo_shared_ptr (Foo *foo) {
        m_foo_shared_ptr = foo;
    }

    // return value
    Foo get_foo_value () {
        return m_foo_value;
    }

    // return pointer, caller doesn't own return
    Foo * get_foo_shared_ptr () {
        return m_foo_shared_ptr;
    }
    
    // return pointer, caller owns return
    Foo * get_foo_ptr () {
        Foo *foo = m_foo_ptr;
        m_foo_ptr = NULL;
        return foo;
    }

};


#endif 	    /* !FOO_H_ */
