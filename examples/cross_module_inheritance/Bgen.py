import sys
from pybindgen import *
from ModuleGenerationFactory import *
import Agen

# Module
mod = Module("B")
mod.add_include('"classes.hh"')
mod.add_include('"Amodule.hh"')

# Derived
Derived = mod.add_class("Derived", allow_subclassing = True, parent = Agen.Base)
Derived.add_constructor([])
Derived.add_method("do_something", None, [], is_virtual=True)

# Generate the code.
assert len(sys.argv) == 2
out = ModuleGenerationFactory(sys.argv[1], [])
mod.generate(out, "B")
out.close()
