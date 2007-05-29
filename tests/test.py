import pybindgen.typehandlers.base
import pybindgen.typehandlers.codesink

import unittest
import doctest

suite = unittest.TestSuite()
for mod in [
    pybindgen.typehandlers.base,
    pybindgen.typehandlers.codesink,
    ]:
    suite.addTest(doctest.DocTestSuite(mod))
runner = unittest.TextTestRunner()
runner.run(suite)

