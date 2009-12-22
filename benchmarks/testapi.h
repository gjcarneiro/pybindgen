// -*- Mode: C++; c-file-style: "stroustrup"; indent-tabs-mode:nil; -*-
#ifndef   	TESTAPI_H_
# define   	TESTAPI_H_


void func1 (void);

double func2 (double x, double y, double z);

class Multiplier
{
    double m_factor;
    
public:
    Multiplier ();
    Multiplier (double factor);
    
    double GetFactor () const;
    virtual double Multiply (double value) const;
};


#endif
