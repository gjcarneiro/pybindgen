//
// foo.cc
//  
// Made by Gustavo J. A. M. Carneiro
// Login   <gjc@localhost.localdomain>
// 
// Started on  Thu May 31 17:36:21 2007 Gustavo J. A. M. Carneiro
// Started on  Thu May 31 17:36:21 2007 Gustavo J. A. M. Carneiro
//

#include "foo.h"
#include <iostream>
#include <string.h>

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

