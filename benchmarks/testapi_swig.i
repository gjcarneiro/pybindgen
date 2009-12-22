/* example.i */

%module testapi_swig
%{

#include "testapi.h"

%}

extern void func1(void);
extern double func2(double x, double y, double z);

class Multiplier
{
    double m_factor;
    
public:
    Multiplier ();
    Multiplier (double factor);
    
    double GetFactor () const;
    virtual double Multiply (double value) const;
};
