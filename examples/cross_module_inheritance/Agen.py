import sys
from pybindgen import *
from ModuleGenerationFactory import *

# Module
mod = Module("A")
mod.add_include('"classes.hh"')

# Base
Base = mod.add_class("Base", allow_subclassing = True)
Base.add_constructor([])
Base.add_method("do_something", None, [], is_virtual=True)

# Generate the code.
assert len(sys.argv) == 2
out = ModuleGenerationFactory(sys.argv[1], [])
mod.generate(out, "A")
out.close()
