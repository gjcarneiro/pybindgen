/* -*- C++ -*- */
#ifndef   	FOO_H_
# define   	FOO_H_

#include <string>

int print_something(const char *message);
int print_something_else(const char *message2);


class SomeObject
{
    std::string m_prefix;
public:
    SomeObject (std::string const prefix)
        : m_prefix (prefix) {}

    int add_prefix (std::string& message);

};


#endif 	    /* !FOO_H_ */
