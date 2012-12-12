# This bit of magic is required for GNU compilers for now for resolving symbols
# across libraries.  See many rants online regarding this issue...
import sys, ctypes
sys.setdlopenflags(sys.getdlopenflags() | ctypes.RTLD_GLOBAL)

import A, B

b = B.Derived()
print isinstance(b, A.Base)
