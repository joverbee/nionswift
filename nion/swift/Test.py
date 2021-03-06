# futures
from __future__ import absolute_import

# standard libraries
import importlib
import inspect
import os
import unittest

# third party libraries
# None

# local libraries
from nion.swift.model import PlugInManager

"""
Running tests without Qt:

import Application
import TestUI
import Test
Application.Application(TestUI.UserInterface())
Test.run_all_tests()
Test.run_test("TestApplicationClass")
"""



suites = []
suite_dict = {}
alltests = None

def append_test_suites(suites):
    suites.append(suites)

# scan through directory and look for tests (files ending in test.py)
# load the module and add the tests
def load_tests(base_path):
    global suites
    global suite_dict
    global alltests

    for subdir in ["nionswift/nion/swift", "niondata/nion/data", "nionutils/nion/utils", "nionui/nion/ui"]:
        localpath = os.path.join(base_path, subdir)
        for file in os.listdir(os.path.join(localpath, "test")):
            if file.endswith("_test.py"):
                module_name = "nion.{0}.test.".format(os.path.basename(subdir)) + file.replace(".py", "")
                module = importlib.import_module(module_name)
                for maybe_a_class in inspect.getmembers(module):
                    if inspect.isclass(maybe_a_class[1]) and maybe_a_class[0].startswith("Test"):
                        test_name = maybe_a_class[0]
                        # It is a class... add it to the test suite.
                        cls = getattr(module, test_name)
                        suite = unittest.TestLoader().loadTestsFromTestCase(cls)
                        suites.append(suite)
                        suite_dict[test_name] = suite

    suites.extend(PlugInManager.test_suites())

    alltests = unittest.TestSuite(suites)

def run_all_tests():
    unittest.TextTestRunner(verbosity=2).run(alltests)

def run_test(test_name):
    unittest.TextTestRunner(verbosity=2).run(suite_dict[test_name])
