from pybindgen import *
from ModuleGenerationFactory import *
import Agen

# Module
mod = Module("B")
mod.add_include('"classes.hh"')
mod.add_include('"A.hh"')

# Derived
mod.begin_section("B_DerivedBindings")
Derived = mod.add_class("Derived", allow_subclassing = True, parent = Agen.Base)
Derived.add_constructor([])
Derived.add_method("do_something", None, [], is_virtual=True)
mod.end_section("B_DerivedBindings")

# Generate the code.
out = ModuleGenerationFactory("B.C", ["DerivedBindings"])
mod.generate(out, "B")
out.close()
