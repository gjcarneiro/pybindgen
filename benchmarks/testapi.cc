// -*- Mode: C++; c-file-style: "stroustrup"; indent-tabs-mode:nil; -*-
#include "testapi.h"

void func1 (void)
{
}

double func2 (double x, double y, double z)
{
    return x + y + z;
}


Multiplier::Multiplier ()
    : m_factor (1.0) 
{
}

Multiplier::Multiplier (double factor)
    : m_factor (factor)
{
}


double Multiplier::GetFactor () const
{
    return m_factor;
}

double
Multiplier::Multiply (double value) const
{
    return value*m_factor;
}


