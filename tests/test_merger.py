import os
import ast
import unittest
import tempfile

from monoscript import PythonModuleMerger, ProcessAllStrategy
from monoscript.parser import ScriptParser


class TestPythonModuleMerger(unittest.TestCase):

    def test_parser(self):
        filepath = "test_modules/parser_test.py"
        with open(filepath) as fin:
            code = fin.read()
        parsed_code = ScriptParser(code).parse()
        self.assertIn('import os', parsed_code.children[0].get_code())
        self.assertIn('    from pathlib import Path', parsed_code.children[5].get_code())
        self.assertIn('    from pathlib import Path', parsed_code.children[5].get_code())

        function_node = parsed_code.children[6]
        self.assertIsInstance(function_node.node, ast.FunctionDef)
        self.assertIn('import json', function_node.children[2].get_code())

        inside_function_code = 'my_list: List[int] = [1, 2, 3]  # Example of type hint using imported List'
        self.assertIn(inside_function_code, function_node.get_code())
        self.assertIn(inside_function_code, parsed_code.get_code())

        # testing context
        self.assertIn('matho', parsed_code.context)
        self.assertIn('dd', parsed_code.context)
        self.assertIn('Counter', parsed_code.context)
        self.assertIn('my_function', parsed_code.context)
        self.assertIn('MyClass', parsed_code.context)
        self.assertIn('json', function_node.context)
        self.assertIn('my_var', function_node.context)
        self.assertIn('d', function_node.context)
        self.assertIn('sub_func', function_node.context)
        self.assertIn('SubClass', function_node.context)

        # remove function
        parsed_code.remove_child(function_node)
        self.assertNotIn(inside_function_code, parsed_code.get_code())

    def test_is_internal_import(self):
        test_cases = [
            ("from module1.utils import x", True),
            ("from .utils import x", True),
            ("from .. import x", True),
            ("from os.path import join", False),
            ("import module1.utils", True),
            ("import os, json", False),
            ("import os, module1.utils", True),  # mixed
        ]
        for code, expected_result in test_cases:
            parsed_code = ScriptParser(code).parse()
            self.assertIs(parsed_code.children[0].is_internal_import('module1'), expected_result)

    def test_extract_explicit_all(self):
        test_cases = [
            ("from module1.utils import x", None),
            ("__all__ = ['a', 'b']", ['a', 'b']),
            ("__all__ = ('a', 'b')", ['a', 'b']),
            ("__all__ += ('a', 'b')", ['a', 'b']),
            ("__all__ : list = ('a', 'b')", ['a', 'b']),
            ("__all__ = not_all = ('a', 'b')", ['a', 'b']),
            ("not_all = __all__ = ('a', 'b')", ['a', 'b']),
            ("__all__ = 1", []),
            ("__all__ = ['a', 'b', None]", ['a', 'b']),
            ("__all__ = ['a', 'b',\n'c',\nNone\n]", ['a', 'b', 'c']),

        ]
        for code, expected_result in test_cases:
            parsed_code = ScriptParser(code).parse()
            self.assertEqual(parsed_code.children[0].extract_all_names(), expected_result)

    def test_process_internal_imports(self):
        # Create a mock file structure
        merger = PythonModuleMerger("test_modules/module2_nested")

        test_cases = [
            ("from ....nested1 import nested1_b_function", "nested2/c/ca/__init__.py",
             ['nested1/__init__.py'], ['nested1_b_function']),
            ("from .b import nested1_b_function, nested1_b_function2", "nested1/__init__.py",
             ['nested1/b.py'], ['nested1_b_function', 'nested1_b_function2']),
            ("from .. import nested1_b_function", "nested1/a/ab.py",
             ['nested1/__init__.py'], ['nested1_b_function']),
            ("from module2_nested.nested2.b import nested2_b_function, nested2_b_function2", "nested2/__init__.py",
             ['nested2/b.py'], ['nested2_b_function', 'nested2_b_function2']),
            ("from .. import nested2_b_function", "nested2/a/ab.py",
             ['nested2/__init__.py'], ['nested2_b_function']),
            ("from ..nested1 import nested1_b_function", "nested1/b.py",
             ['nested1/__init__.py'], ['nested1_b_function']),
            ("import module2_nested.nested1.c, module2_nested.nested1.b", "nested1/b.py",
             ['nested1/c/__init__.py', 'nested1/b.py'], None),

        ]

        for statement, cur_rel_path, import_rel_paths, imported_names in test_cases:
            import_node = ast.parse(statement).body[0]
            current_path = os.path.join(merger.module_path, cur_rel_path)
            import_paths = [os.path.join(merger.module_path, rel_path) for rel_path in
                            import_rel_paths] if import_rel_paths else None
            result = merger.process_internal_import(current_path, import_node)
            self.assertEqual(result[0], import_paths)
            self.assertEqual(result[1], imported_names)

    def test_merge_simple(self):
        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module1", output_dir=tempdir)
            merger.merge_files()
            self.assertEqual(len(merger.processed_code), 3)
            self.assertTrue(os.path.exists(merger.output_file))

            with open(merger.output_file, 'r') as f:
                merged_code = f.read()
            # print(merged_code)
            self.assertIn("__all__ = ['CoreClass', 'UtilClass', 'util_function']", merged_code)
            self.assertIn("def util_function():", merged_code)
            self.assertIn("from os.path import join", merged_code)
            self.assertIn("import sys\nfrom os.path import join", merged_code)

        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module1", output_dir=tempdir, organize_imports=False)
            merger.merge_files()
            self.assertTrue(os.path.exists(merger.output_file))
            self.assertEqual(len(merger.processed_code), 3)

            with open(merger.output_file, 'r') as f:
                merged_code = f.read()

            self.assertIn("__all__ = ['CoreClass', 'UtilClass', 'util_function']", merged_code)
            self.assertIn("def util_function():", merged_code)
            self.assertIn("from os.path import join", merged_code)
            self.assertNotIn("import sys\nfrom os.path import join", merged_code)

    def test_merge_header(self):
        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module1", output_dir=tempdir)
            merger.merge_files()

            with open(merger.output_file, 'r') as f:
                merged_code = f.read()

            self.assertIn("This module was automatically generated By Monoscript", merged_code)
            self.assertIn("Module Name: module1", merged_code)
            self.assertIn("Generated On: ", merged_code)
            self.assertNotIn("Additional Metadata:", merged_code)

        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module1", output_dir=tempdir,
                                        author='Test <test@example.com>',
                                        module_description='bla bla bla',
                                        project_website='https://example.com',
                                        licence='MIT',
                                        additional_headers={'Author Email': 'test@example.com', 'Blood Type': 'X+'}
                                        )
            merger.merge_files()

            with open(merger.output_file, 'r') as f:
                merged_code = f.read()
            self.assertIn("Description: bla bla bla", merged_code)
            self.assertIn("Author: Test <test@example.com>", merged_code)
            self.assertIn("License: MIT", merged_code)
            self.assertIn("Additional Metadata:", merged_code)
            self.assertIn("  Author Email: test@example.com", merged_code)
            self.assertIn("  Blood Type: X+", merged_code)

    def test_merge_all_strategies(self):
        test_cases = [
            ({}, ['CoreClass', 'UtilClass', 'util_function']),

            (dict(process_all_strategy=ProcessAllStrategy.AUTO, custom_all=None, additional_all=None),
             ['CoreClass', 'UtilClass', 'util_function']),

            (dict(process_all_strategy=ProcessAllStrategy.NONE, custom_all=None, additional_all=None),
             None),

            (dict(process_all_strategy=ProcessAllStrategy.INIT, custom_all=None, additional_all=None),
             []),

            (dict(process_all_strategy=ProcessAllStrategy.AUTO, custom_all=['test1', 'test2'], additional_all=None),
             ['test1', 'test2']),

            (dict(process_all_strategy=ProcessAllStrategy.AUTO, custom_all=None, additional_all=['a1', 'a2']),
             ['CoreClass', 'UtilClass', 'a1', 'a2', 'util_function']),

            (dict(process_all_strategy=ProcessAllStrategy.NONE, custom_all=None, additional_all=['a1', 'a2']),
             None),

            (dict(process_all_strategy=ProcessAllStrategy.INIT, custom_all=None, additional_all=['a1', 'a2']),
             ['a1', 'a2']),

            (dict(process_all_strategy=ProcessAllStrategy.AUTO, custom_all=['test1', 'test2'],
                  additional_all=['a1', 'a2']),
             ['a1', 'a2', 'test1', 'test2']),

        ]

        for kwargs, expected_result in test_cases:
            with tempfile.TemporaryDirectory() as tempdir:
                merger = PythonModuleMerger("test_modules/module1", output_dir=tempdir, **kwargs)
                merger.merge_files()
                all_names = merger.process_all()
                self.assertEqual(expected_result, all_names)

    def test_merge_nested(self):
        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module2_nested", output_dir=tempdir)
            merger.merge_files()

            with open(merger.output_file, 'r') as f:
                merged_code = f.read()
            # print(merged_code)

            functions = ['nested1_b_function', 'nested1_b_function2', 'nested2_b_function', 'nested2_b_function2',
                         'nested2_a_function1', 'nested2_aa_function', 'nested2_ab_function', 'nested2_ca_function',
                         'nested1_a_function1', 'nested1_aa_function', 'nested1_ab_function', 'nested1_ca_function', ]

            for function in functions:
                self.assertIn(f"def {function}(", merged_code)

    def test_merge_with_main(self):
        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module3_main", output_dir=tempdir)
            merger.merge_files()
            self.assertEqual(4, len(merger.processed_code))
            self.assertEqual('__main__.py', merger.processed_code[-1][1])
            self.assertTrue(os.path.exists(merger.output_file))
            with open(merger.output_file, 'r') as f:
                merged_code = f.read()
            self.assertIn("if __name__ == '__main__':", merged_code)

    def test_merge_with_tests(self):
        with tempfile.TemporaryDirectory() as tempdir:
            merger = PythonModuleMerger("test_modules/module4", output_dir=tempdir,
                                        test_scripts_dirname='module4_tests')
            merger.merge_files()
            self.assertTrue(os.path.exists(merger.output_file))
            self.assertTrue(os.path.exists(merger.test_merger.output_file))
            with open(merger.test_merger.output_file, 'r') as f:
                merged_code = f.read()

            self.assertIn("if __name__ == '__main__':", merged_code)


if __name__ == '__main__':
    unittest.main()
