from pybindgen import *
from ModuleGenerationFactory import *

# Module
mod = Module("A")
mod.add_include('"classes.hh"')

# Base
mod.begin_section("A_BaseBindings")
Base = mod.add_class("Base", allow_subclassing = True)
Base.add_constructor([])
Base.add_method("do_something", None, [], is_virtual=True)
mod.end_section("A_BaseBindings")

# Generate the code.
out = ModuleGenerationFactory("A.C", ["BaseBindings"])
mod.generate(out, "A")
out.close()
