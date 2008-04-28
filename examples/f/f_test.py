import sys
sys.path.insert(0, "../../build/default/examples/f")
from f import *


class FDerived(FBase):
    def _DoA (self):
        print "FDerived::DoA"
    def _PrivDoB (self):
        print "FDerived::PrivDoB"

f = FDerived ()
f.DoA ()
f.DoB ()

