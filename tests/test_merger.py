import os
import ast
import unittest
import tempfile
from monoscript import PythonModuleMerger


class TestPythonModuleMerger(unittest.TestCase):

    def test_is_internal_import(self):
        merger = PythonModuleMerger("test_modules/module1")  # static path
        internal_import_node = ast.parse("from module1.utils import x").body[0]
        self.assertTrue(merger.is_internal_import(internal_import_node))

        internal_import_node_relative = ast.parse("from .utils import x").body[0]
        self.assertTrue(merger.is_internal_import(internal_import_node_relative))

        internal_import_node = ast.parse("import module1.utils").body[0]
        self.assertTrue(merger.is_internal_import(internal_import_node))

        external_import_node = ast.parse("import os").body[0]
        self.assertFalse(merger.is_internal_import(external_import_node))

        external_import_node = ast.parse("from os.path import join").body[0]
        self.assertFalse(merger.is_internal_import(external_import_node))

    def test_extract_explicit_all(self):
        merger = PythonModuleMerger("test_modules/module1")
        assign_node = ast.parse("__all__ = ['a', 'b']").body[0]
        all_list = merger.extract_explicit_all(assign_node)
        self.assertEqual(all_list, ['a', 'b'])

        assign_node_tuple = ast.parse("__all__ = ('a', 'b')").body[0]
        all_tuple = merger.extract_explicit_all(assign_node_tuple)
        self.assertEqual(all_tuple, ['a', 'b'])

        assign_node_wrong = ast.parse("__all__ = 1").body[0]
        all_wrong = merger.extract_explicit_all(assign_node_wrong)
        self.assertEqual(all_wrong, [])

    def test_merge_simple(self):
        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module1", output_dir=tempdir)
            merger.merge_files()
            output_file = os.path.join(merger.output_dir, "module1.py")
            self.assertTrue(os.path.exists(output_file))

            with open(output_file, 'r') as f:
                merged_code = f.read()
            print(merged_code)
            self.assertIn("__all__ = ['a', 'b']", merged_code)
            self.assertIn("def func1(): pass", merged_code)
            self.assertIn("import os", merged_code)
            self.assertIn("from tests.test_modules.test_module.module1 import func1", merged_code)

    def test_merge_files_no_init(self):
        merger = PythonModuleMerger("tests/test_modules/test_module_no_init")
        merger.merge_files()
        output_file = os.path.join(merger.output_dir, "test_module_no_init.py")

        self.assertTrue(os.path.exists(output_file))

        with open(output_file, 'r') as f:
            merged_code = f.read()
        self.assertIn("__all__ = ['b']", merged_code)
        self.assertIn("def func1(): pass", merged_code)
        self.assertIn("from tests.test_modules.test_module_no_init.module1 import func1", merged_code)

    def test_merge_files_custom_all(self):
        merger = PythonModuleMerger("tests/test_modules/test_module", custom_all=['c'])
        merger.merge_files()
        output_file = os.path.join(merger.output_dir, "test_module.py")
        with open(output_file, 'r') as f:
            merged_code = f.read()
        self.assertIn("__all__ = ['a', 'c']", merged_code)

    def test_merge_files_process_all_none(self):
        merger = PythonModuleMerger("tests/test_modules/test_module", process_all='none')
        merger.merge_files()
        output_file = os.path.join(merger.output_dir, "test_module.py")
        with open(output_file, 'r') as f:
            merged_code = f.read()
        self.assertNotIn("__all__", merged_code)

    def test_merge_files_process_all_remove(self):
        merger = PythonModuleMerger("tests/test_modules/test_module", process_all='remove')
        merger.merge_files()
        output_file = os.path.join(merger.output_dir, "test_module.py")
        with open(output_file, 'r') as f:
            merged_code = f.read()
        self.assertNotIn("__all__", merged_code)


if __name__ == '__main__':
    unittest.main()
