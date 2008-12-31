// -*- Mode: C++; c-file-style: "stroustrup"; indent-tabs-mode:nil; -*-
#ifndef   	FOO_H_
# define   	FOO_H_

#include <Python.h>
#include <string>
#include <iostream>
#include <sstream>
#include <vector>
#include <map>
#include <set>

// Deprecation warnings look ugly and confusing; better to just
// disable them and change this macro when we want to specifically
// test them.
#define ENABLE_DEPRECATIONS 0

#ifndef DEPRECATED
# if ENABLE_DEPRECATIONS && __GNUC__ > 2
#  define DEPRECATED  __attribute__((deprecated))
# else
#  define DEPRECATED
# endif
#endif

// Yes, this code is stupid, I know; it is only meant as an example!

int print_something(const char *message) DEPRECATED;
int print_something_else(const char *message2);

/* -#- name=get_int -#- */
int get_int_from_string(const char *from_string, int multiplier=1);
// -#- name=get_int; @multiplier(default_value=1) -#-
int get_int_from_float(double from_float, int multiplier);

// In this example PointerHolder<T> automatically implies
// caller_owns_return=True when used as ReturnValue, and
// transfer_ownership=False when used as parameter.
template <typename T>
struct PointerHolder
{
    T *thePointer;
};


class Foo
// -#- automatic_type_narrowing=True -#-
{
    std::string m_datum;
    bool m_initialized;
public:
    static int instance_count;

    Foo () : m_datum (""), m_initialized (false)
        { Foo::instance_count++; }

    Foo (int xpto)  DEPRECATED : m_initialized (false) { xpto++; }

    Foo (std::string const &datum) : m_datum (datum), m_initialized (false)
        { Foo::instance_count++; }
    const std::string get_datum () const { return m_datum; }

    std::string get_datum_deprecated () const DEPRECATED { return m_datum; }

    Foo (Foo const & other) : m_datum (other.get_datum ()), m_initialized (false)
        { Foo::instance_count++; }

    void initialize () { m_initialized = true; }
    bool is_initialized () const { return m_initialized; }

    virtual ~Foo() { Foo::instance_count--; }
};

inline std::ostream & operator << (std::ostream &os, Foo const &foo)
{
    os << foo.get_datum ();
    return os;
}

class Zoo
// -#- automatic_type_narrowing=True -#-
{
    std::string m_datum;
public:
    Zoo () : m_datum ("")
        {}
    Zoo (std::string datum) : m_datum (datum)
        {}
    virtual ~Zoo() {}
    std::string get_datum () const { return m_datum; }

    operator Foo() const {
        return Foo(m_datum);
    }
};


class ClassThatTakesFoo
{
    Foo m_foo;
public:
    ClassThatTakesFoo(Foo foo) : m_foo(foo) {}
    Foo get_foo () const { return m_foo; }
};

extern Foo g_foo;

void function_that_takes_foo(Foo foo);
Foo function_that_returns_foo();


class Bar : public Foo
{
public:
    static std::string Hooray () {
        return std::string ("Hooray!");
    }
    virtual ~Bar() {}
};

// caller owns return
// -#- @return(caller_owns_return=true) -#-
Foo* get_hidden_subclass_pointer ();

class Zbr
// -#- incref_method=Ref; decref_method=Unref; peekref_method=GetReferenceCount -#-
{
    int m_refcount;
    std::string m_datum;
public:
    Zbr () : m_refcount (1), m_datum ("")
        { Zbr::instance_count++; }
    Zbr (std::string datum) :  m_refcount (1), m_datum (datum)
        { Zbr::instance_count++; }

    std::string get_datum () const { return m_datum; }

    Zbr (Zbr const & other) :
        m_refcount (1), m_datum (other.get_datum ())
        {Zbr::instance_count++;}

    void Ref () {
        // std::cerr << "Ref Zbr " << this << " from " << m_refcount << std::endl;
        ++m_refcount;
    }
    void Unref () {
        // std::cerr << "Unref Zbr " << this << " from " << m_refcount << std::endl;
        if (--m_refcount == 0)
            delete this;
    }
    int GetReferenceCount () const { return m_refcount; }

    virtual int get_int (int x) {
        return x;
    }
    
    static int instance_count;

    virtual ~Zbr () {
        --Zbr::instance_count;
    }
};

// -#- @zbr(transfer_ownership=true) -#-
void store_zbr (Zbr *zbr);
int invoke_zbr (int x);
void delete_stored_zbr (void);


class Foobar
{
public:
    static int instance_count;

    Foobar ()
        { Foobar::instance_count++; }

    virtual ~Foobar() { Foobar::instance_count--; }
};


class SomeObject
{
public:
    std::string m_prefix;
    
    enum {
        TYPE_FOO,
        TYPE_BAR,
    } type;

    static int instance_count;


    // A nested class
    class NestedClass
    // -#- automatic_type_narrowing=True -#-
    {
        std::string m_datum;
    public:
        static int instance_count;

        NestedClass () : m_datum ("")
            { Foo::instance_count++; }
        NestedClass (std::string datum) : m_datum (datum)
            { Foo::instance_count++; }
        std::string get_datum () const { return m_datum; }

        NestedClass (NestedClass const & other) : m_datum (other.get_datum ())
            { Foo::instance_count++; }

        virtual ~NestedClass() { NestedClass::instance_count--; }
    };

    // A nested enum
    enum NestedEnum {
        FOO_TYPE_AAA,
        FOO_TYPE_BBB,
        FOO_TYPE_CCC,
    };


    // An anonymous nested enum
    enum  {
        CONSTANT_A,
        CONSTANT_B,
        CONSTANT_C
    };


private:
    Foo m_foo_value;
    Foo *m_foo_ptr;
    Foo *m_foo_shared_ptr;
    Zbr *m_zbr;
    Zbr *m_internal_zbr;

    PyObject *m_pyobject;

    SomeObject ();

public:

    static std::string staticData;

    virtual ~SomeObject ();
    SomeObject (const SomeObject &other);
    SomeObject (std::string const prefix);
    SomeObject (int prefix_len);

    // -#- @message(direction=inout) -#-
    int add_prefix (std::string& message) {
        message = m_prefix + message;
        return message.size ();
    }

    // -#- @message(direction=inout) -#-
    int operator() (std::string& message) {
        message = m_prefix + message;
        return message.size ();
    }

    // --------  Virtual methods ----------
    virtual std::string get_prefix () const {
        return m_prefix;
    }

    std::string call_get_prefix () const {
        return get_prefix();
    }

    virtual std::string get_prefix_with_foo_value (Foo foo) const {
        return m_prefix + foo.get_datum();
    }

    // -#- @foo(direction=inout) -#-
    virtual std::string get_prefix_with_foo_ref (const Foo &foo) const {
        return m_prefix + foo.get_datum ();
    }

    virtual std::string get_prefix_with_foo_ptr (const Foo *foo) const {
        return m_prefix + foo->get_datum ();
    }


    // A couple of overloaded virtual methods
    virtual std::string get_something () const {
        return "something";
    }
    virtual std::string get_something (int x) const {
        std::stringstream out;
        out << x;
        return out.str ();
    }

    // -#- @pyobject(transfer_ownership=false) -#-
    virtual void set_pyobject (PyObject *pyobject) {
        if (m_pyobject) {
            Py_DECREF(m_pyobject);
        }
        Py_INCREF(pyobject);
        m_pyobject = pyobject;
    }

    // -#- @return(caller_owns_return=true) -#-
    virtual PyObject* get_pyobject (void) {
        if (m_pyobject) {
            Py_INCREF(m_pyobject);
            return m_pyobject;
        } else {
            return NULL;
        }
    }

    // pass by value, direction=in
    void set_foo_value (Foo foo) {
        m_foo_value = foo;
    }

    // pass by reference, direction=in
    void set_foo_by_ref (const Foo& foo) {
        m_foo_value = foo;
    }

    // pass by reference, direction=out
    // -#- @foo(direction=out) -#-
    void get_foo_by_ref (Foo& foo) {
        foo = m_foo_value;
    }

    // -#- @foo(transfer_ownership=true) -#-
    void set_foo_ptr (Foo *foo) {
        if (m_foo_ptr)
            delete m_foo_ptr;
        m_foo_ptr = foo;
    }

    // -#- @foo(transfer_ownership=false) -#-
    void set_foo_shared_ptr (Foo *foo) {
        m_foo_shared_ptr = foo;
    }

    // return value
    Foo get_foo_value () {
        return m_foo_value;
    }

    // -#- @return(caller_owns_return=false) -#-
    Foo * get_foo_shared_ptr () {
        return m_foo_shared_ptr;
    }
    
    // -#- @return(caller_owns_return=true) -#-
    Foo * get_foo_ptr () {
        Foo *foo = m_foo_ptr;
        m_foo_ptr = NULL;
        return foo;
    }

    // -#- @return(caller_owns_return=true) -#-
    Zbr* get_zbr () {
        if (m_zbr)
        {
            m_zbr->Ref ();
            return m_zbr;
        } else
            return NULL;
    }

    // -#- @return(caller_owns_return=true) -#-
    Zbr* get_internal_zbr () {
        m_internal_zbr->Ref ();
        return m_internal_zbr;
    }

    // return reference counted object, caller does not own return
    // -#- @return(caller_owns_return=false) -#-
    Zbr* peek_zbr () { return m_zbr; }

    // pass reference counted object, transfer ownership
    // -#- @zbr(transfer_ownership=true) -#-
    void set_zbr_transfer (Zbr *zbr) {
        if (m_zbr)
            m_zbr->Unref ();
        m_zbr = zbr;
    }

    // pass reference counted object, does not transfer ownership
    // -#- @zbr(transfer_ownership=false) -#-
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

    int get_int (const char *from_string);
    int get_int (double from_float);

    // custodian/ward tests

    // -#- @return(custodian=0) -#-
    Foobar* get_foobar_with_self_as_custodian () {
        return new Foobar;
    }
    // -#- @return(custodian=1) -#-
    Foobar* get_foobar_with_other_as_custodian (const SomeObject *other) {
        other++;
        return new Foobar;
    }
    // -#- @foobar(custodian=0) -#-
    void set_foobar_with_self_as_custodian (Foobar *foobar) {
        foobar++;
    }
};


// A function that will appear as a method of SomeObject
// -#- as_method=get_something_prefixed; of_class=SomeObject -#-
// -#- @obj(transfer_ownership=false) -#-
std::string some_object_get_something_prefixed(const SomeObject *obj, const std::string something);

// -#- as_method=val_get_something_prefixed; of_class=SomeObject -#-
std::string some_object_val_get_something_prefixed(SomeObject obj, const std::string something);
// -#- as_method=ref_get_something_prefixed; of_class=SomeObject -#-
std::string some_object_ref_get_something_prefixed(const SomeObject &obj, const std::string something);


// Transfer ownership of 'obj' to the library
// -#- @obj(transfer_ownership=true) -#-
void store_some_object(SomeObject *obj);

// Invokes the virtual method in the stored SomeObject
std::string invoke_some_object_get_prefix();

// Transfer ownership of 'obj' away from the library
// -#- @return(caller_owns_return=true) -#-
SomeObject* take_some_object();

// Deletes the contained object, if any
void delete_some_object();


namespace xpto
{
    std::string some_function();

    class SomeClass
    {
    public:
        SomeClass() {}
    };

    enum FooType {
        FOO_TYPE_AAA,
        FOO_TYPE_BBB,
        FOO_TYPE_CCC,
    };

    FooType get_foo_type ();
    void set_foo_type (FooType type);

    typedef Foo FooXpto;

    std::string get_foo_datum(FooXpto const &foo);
}

// -#- @return(custodian=1) -#-
Foobar* get_foobar_with_other_as_custodian(const SomeObject *other);

// -#- @return(caller_owns_return=true) -#-
Foobar* create_new_foobar();
// -#- @foobar(custodian=2) -#-
void set_foobar_with_other_as_custodian(Foobar *foobar, const SomeObject *other);
// -#- @foobar(custodian=-1); @return(caller_owns_return=true) -#-
SomeObject * set_foobar_with_return_as_custodian(Foobar *foobar);

class SingletonClass
// -#- is_singleton=true -#-
{
private:
    static SingletonClass *m_instance;

    SingletonClass () {}
    ~SingletonClass () {}

public:
    // -#- @return(caller_owns_return=true) -#-
    static SingletonClass *GetInstance () {
            if (!m_instance)
                m_instance = new SingletonClass;
            return m_instance;
        }
};


class InterfaceId
{
public:
    ~InterfaceId () {}
private:
    InterfaceId () {}
    friend InterfaceId make_interface_id ();
    // -#- ignore -#-
    friend InterfaceId make_object_interface_id ();
};

InterfaceId make_interface_id ();

template <typename T> std::string TypeNameGet (void)
{
  return "unknown";
}


// -#- template_instance_names=int=>IntegerTypeNameGet -#-
template <> std::string TypeNameGet<int> (void);


// just to force a template instantiation
struct __foo__
{
     std::string get ()
        {
            return TypeNameGet<int> ();
        }
};


// Test code generation errors and error handling

class CannotBeConstructed
{
public:
    ~CannotBeConstructed () {}

    // This static method cannot be generated
    static CannotBeConstructed get_value () {
        return CannotBeConstructed ();
    }

    // This static method can be generated because caller-owns-return=true
    // -#- @return(caller_owns_return=true) -#-
    static CannotBeConstructed* get_ptr () {
        return new CannotBeConstructed ();
    }
private:
    CannotBeConstructed () {}
};

// This function cannot be generated
inline CannotBeConstructed get_cannot_be_constructed_value () {
    return CannotBeConstructed::get_value ();
}

// This static method can be generated because caller-owns-return=true
// -#- @return(caller_owns_return=true) -#-
inline CannotBeConstructed* get_cannot_be_constructed_ptr () {
    return CannotBeConstructed::get_ptr ();
}

class AbstractBaseClass
{
public:
    virtual ~AbstractBaseClass () {}

protected:
    // A pure virtual method with a parameter type so strange that it
    // cannot be possibly be automatically wrapped by pybindgen; this
    // will cause the cannot_be_constructed flag on the class to be
    // set to true, and allow us to test code generation error
    // handling (see below).
    virtual void do_something (char ****) = 0;

    AbstractBaseClass () {}
};

class AbstractBaseClassImpl : public AbstractBaseClass
{
public:
    virtual ~AbstractBaseClassImpl () {}

    // -#- @return(caller_owns_return=true) -#-
    static AbstractBaseClass* get_abstract_base_class_ptr1 ()
        {
            return new AbstractBaseClassImpl;
        }

    // This method will be scanned by gccxmlparser and generate an error
    // that is only detected in code generation time.
    // -#- @return(caller_owns_return=false) -#-
    static AbstractBaseClass* get_abstract_base_class_ptr2 ()
        {
            static AbstractBaseClassImpl *singleton = NULL;
            if (!singleton)
                singleton = new AbstractBaseClassImpl;
            return singleton;
        }

protected:
    virtual void do_something (char ****) {}

    AbstractBaseClassImpl () {}
};


// -#- @return(caller_owns_return=true) -#-
inline AbstractBaseClass* get_abstract_base_class_ptr1 ()
{
    return AbstractBaseClassImpl::get_abstract_base_class_ptr1 ();
}

// This function will be scanned by gccxmlparser and generate an error
// that is only detected in code generation time.
// -#- @return(caller_owns_return=false) -#-
inline AbstractBaseClass* get_abstract_base_class_ptr2 ()
{
    static AbstractBaseClass *singleton = NULL;
    if (!singleton)
        singleton = AbstractBaseClassImpl::get_abstract_base_class_ptr1 ();
    return singleton;
}


// Class to test private/protected virtual methods
class AbstractBaseClass2
{
protected:
    AbstractBaseClass2 () {}

public:
    virtual ~AbstractBaseClass2 () {}

    int invoke_private_virtual (int x) const {
        return private_virtual (x);
    }

    int invoke_protected_virtual (int x) const {
        return protected_virtual (x);
    }

protected:
    virtual int protected_virtual (int x) const { return x+1; }

private:
    virtual int private_virtual (int x) const = 0;

    AbstractBaseClass2 (const AbstractBaseClass2 &other) { other.invoke_protected_virtual(0); }
};

class AbstractXpto
// -#- allow_subclassing=true -#-
{
public:
    AbstractXpto () {}
    virtual ~AbstractXpto () {}

    virtual void something (int x) const = 0;
};

class AbstractXptoImpl : public AbstractXpto
{
public:
    AbstractXptoImpl () {}

    virtual void something (int x) const { x++; }
};


// Test anonymous structures
union Word
{
    uint16_t word;
    struct
    {
        uint8_t low, high;
    };
};

// Test float array
// -#- @matrix(direction=in, array_length=6) -#-
float matrix_sum_of_elements (float *matrix);

// -#- @matrix(direction=out, array_length=6) -#-
void matrix_identity_new (float *matrix);

namespace TopNs
{

    class OuterBase
    {
    public:
    };

    namespace PrefixBottomNs {
        class PrefixInner : public OuterBase 
        {
        public:
            PrefixInner () {}
            void Do (void) {}
        };
    }

}


// Bug #245097
typedef void (*Callback) (void);
void function_that_takes_callback (Callback cb);


// <Bug #246069>
struct Socket
{
    virtual int Bind () { return -1; }
    virtual int Bind (int address) { return address; }
};

struct UdpSocket : public Socket
{
    virtual int Bind () { return 0; }
};
// </Bug #246069>


struct simple_struct_t
{
    int xpto;
};

// -- Containers:

typedef std::vector<simple_struct_t> SimpleStructList;
typedef std::vector<simple_struct_t> SimpleStructVec;

SimpleStructList get_simple_list ();
int set_simple_list (SimpleStructList list);

class TestContainer
{
public:
    
    std::set<float> m_floatSet;

    TestContainer () { m_floatSet.insert (1.0); m_floatSet.insert (2.0); m_floatSet.insert (3.0); }

    virtual SimpleStructList get_simple_list ();
    virtual int set_simple_list (SimpleStructList list);

    // -#- @inout_list(direction=inout) -#-
    virtual int set_simple_list_by_ref (SimpleStructList &inout_list);

    virtual SimpleStructVec get_simple_vec ();
    virtual int set_simple_vec (SimpleStructVec vec);

    // -#- @outVec(direction=out) -#-
    void get_vec (std::vector<std::string> &outVec);

    // -#- @inVec(direction=in, transfer_ownership=true) -#-
    void set_vec_ptr (std::vector<std::string> *inVec);

    // -#- @outVec(direction=out) -#-
    void get_vec_ptr (std::vector<std::string> *outVec);

private:
    SimpleStructList m_simpleList;

    std::vector<std::string> *m_vec;
    
};

std::map<std::string, int> get_map ();

std::set<uint32_t> get_set ();


// test binary operators

struct Tupl
{
    int x, y;

    inline Tupl operator * (Tupl const &b)
        {
            Tupl retval;
            retval.x = x * b.x;
            retval.y = y * b.y;
            return retval;
        }

    inline Tupl operator / (Tupl const &b)
        {
            Tupl retval;
            retval.x = x / b.x;
            retval.y = y / b.y;
            return retval;
        }

    inline bool operator == (Tupl const &b)
        {
            return (x == b.x && y == b.y);
        }

    inline bool operator != (Tupl const &b)
        {
            return (x != b.x || y != b.y);
        }

};

inline bool operator < (Tupl const &a, Tupl const &b)
{
    return (a.x < b.x || (a.x == b.x && a.y < b.y));
}

inline bool operator <= (Tupl const &a, Tupl const &b)
{
    return (a.x <= b.x || (a.x == b.x && a.y <= b.y));
}

inline bool operator > (Tupl const &a, Tupl const &b)
{
    return (a.x > b.x || (a.x == b.x && a.y > b.y));
}

inline bool operator >= (Tupl const &a, Tupl const &b)
{
    return (a.x >= b.x || (a.x == b.x && a.y >= b.y));
}

inline Tupl operator + (Tupl const &a, Tupl const &b)
{
    Tupl retval;
    retval.x = a.x + b.x;
    retval.y = a.y + b.y;
    return retval;
}

inline Tupl operator - (Tupl const &a, Tupl const &b)
{
    Tupl retval;
    retval.x = a.x - b.x;
    retval.y = a.y - b.y;
    return retval;
}



#endif 	    /* !FOO_H_ */
