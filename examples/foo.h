// -*- Mode: C++; c-file-style: "stroustrup"; indent-tabs-mode:nil; -*-
#ifndef   	FOO_H_
# define   	FOO_H_

#include <string>
#include <iostream>

// Yes, this code is stupid, I know; it is only meant as an example!

int print_something(const char *message);
int print_something_else(const char *message2);

// In this example PointerHolder<T> automatically implies
// caller_owns_return=True when used as ReturnValue, and
// transfer_ownership=False when used as parameter.
template <typename T>
struct PointerHolder
{
    T *thePointer;
};


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
public:
    static std::string Hooray () {
        return std::string ("Hooray!");
    }
};


class Zbr
{
    int m_refcount;
    std::string m_datum;
public:
    Zbr () : m_refcount (1), m_datum ("")
        {}
    Zbr (std::string datum) :  m_refcount (1), m_datum (datum)
        {}

    std::string get_datum () const { return m_datum; }

    Zbr (Zbr const & other) :
        m_refcount (1), m_datum (other.get_datum ())
        {}

    void Ref () {
        // std::cerr << "Ref Zbr " << this << " from " << m_refcount << std::endl;
        ++m_refcount;
    }
    void Unref () {
        // std::cerr << "Unref Zbr " << this << " from " << m_refcount << std::endl;
        if (--m_refcount == 0)
            delete this;
    }
};


class SomeObject
{
    std::string m_prefix;
    Foo m_foo_value;
    Foo *m_foo_ptr;
    Foo *m_foo_shared_ptr;
    Zbr *m_zbr;

public:

    ~SomeObject () {
        delete m_foo_ptr;
        if (m_zbr)
            m_zbr->Unref ();
    }

    SomeObject (std::string const prefix)
        : m_prefix (prefix), m_foo_ptr (0),
          m_foo_shared_ptr (0), m_zbr (0)
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
    void set_foo_by_ref (Foo& foo) {
        m_foo_value = foo;
    }

    // pass by reference, direction=out
    void get_foo_by_ref (Foo& foo) {
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

    // return reference counted object, caller owns return
    Zbr* get_zbr () {
        if (m_zbr)
        {
            m_zbr->Ref ();
            return m_zbr;
        } else
            return NULL;
    }

    // return reference counted object, caller does not own return
    Zbr* peek_zbr () { return m_zbr; }

    // pass reference counted object, transfer ownership
    void set_zbr_transfer (Zbr *zbr) {
        if (m_zbr)
            m_zbr->Unref ();
        m_zbr = zbr;
    }

    // pass reference counted object, does not transfer ownership
    void set_zbr_shared (Zbr *zbr) {
        if (m_zbr)
            m_zbr->Unref ();
        zbr->Ref ();
        m_zbr = zbr;
    }


    // return reference counted object, caller does not own return
    PointerHolder<Zbr> get_zbr_pholder () {
        PointerHolder<Zbr> foo = { m_zbr };
        m_zbr->Ref ();
        return foo;
    }

    // pass reference counted object, transfer ownership
    void set_zbr_pholder (PointerHolder<Zbr> zbr) {
        if (m_zbr)
            m_zbr->Unref ();
        m_zbr = zbr.thePointer;
        m_zbr->Ref ();
    }

};


#endif 	    /* !FOO_H_ */
