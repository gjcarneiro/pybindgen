#include "d.h"
#include <iostream>

struct D *DCreate (void)
{
  std::cout << "DCreate" << std::endl;
  return new D ();
}
void DDoA (struct D *d)
{
  std::cout << "DDoA" << std::endl;
}
void DDoB (struct D &d)
{
  std::cout << "DDoB" << std::endl;
}
void DDoC (const struct D &d)
{
  std::cout << "DDoC" << std::endl;
}
void DDestroy (struct D *d)
{
  std::cout << "DDestroy" << std::endl;
}
