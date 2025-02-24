import datetime
import os
import subprocess
import sys
from collections import defaultdict
from os.path import join, dirname, basename, abspath, exists, relpath, isfile, isdir, normpath
import ast
from dataclasses import dataclass
from enum import Enum
from typing import Union, Optional
from .color_print import info, error, warning, success
from .parser import ScriptParser, ScriptNode


class ProcessAllStrategy(Enum):
    NONE = 0
    AUTO = 1
    INIT = 2


class PythonModuleMerger:
    def __init__(self, module_path, output_dir='dist',
                 process_all_strategy: ProcessAllStrategy = ProcessAllStrategy.AUTO, custom_all=None,
                 additional_all=None,
                 organize_imports=True,
                 module_name=None,
                 # metadata
                 module_version='',
                 module_description='', author='', license='', project_website=None,
                 additional_headers: dict[str, str] = None,
                 requirements: Optional[list[str]] = None,
                 requirements_filename: str = 'requirements.txt',

                 # test scripts
                 test_scripts_dirname='tests',
                 test_scripts_dirpath=None,  # or join(module_parent, test_scripts_dirname)
                 merge_test_scripts=False,  # True, False;
                 run_test_scripts=None,  # True, False or None (Auto: if test_scripts_dirpath exists);

                 ):
        self.module_path = abspath(module_path)
        self.module_parent = dirname(self.module_path)
        self.module_name = module_name or basename(module_path)
        self.output_dir = output_dir
        self.output_file = join(output_dir, f"{self.module_name}.py")
        self.process_all_strategy = process_all_strategy  # "none", "auto", "remove"
        self.custom_all = custom_all if custom_all is not None else []
        self.additional_all = additional_all or []
        self.organize_imports = organize_imports

        self.all_other_explicit_entries = set()
        self.all_init_explicit_entries = set()
        self.all_init_implicit_entries = set()
        self.all_external_imports = set()
        self.processed_code: list[tuple[FileParseResult, str]] = []
        self.processed_files = set()

        # metadata
        self.module_description = module_description
        self.module_version = module_version
        self.author = author
        self.license = license
        self.project_website = project_website
        self.additional_headers = additional_headers
        self.requirements = requirements
        self.requirements_filename = requirements_filename

        # test scripts
        self.test_scripts_dirpath = test_scripts_dirpath or join(self.module_parent, test_scripts_dirname)
        self.run_test_scripts = isdir(self.test_scripts_dirpath) if run_test_scripts is None \
            else run_test_scripts
        self.merge_test_scripts = merge_test_scripts
        self.test_merger = None

        # global names
        self.global_context = {}
        self.global_context_conflicts = defaultdict(set)

    def iter_files(self):
        for root, _, files in os.walk(self.module_path):
            for filename in sorted(files):
                if filename.endswith(".py"):
                    file_path = join(root, filename)
                    rel_path = relpath(file_path, self.module_path)
                    if rel_path in self.processed_files:
                        continue
                    yield file_path

    def merge_files(self):
        """Merges all Python files into a single file while handling imports and '__all__'."""
        # Process __init__.py first (to extract __all__)
        info(f"Started processing files in {self.module_path}...")
        init_file = join(self.module_path, "__init__.py")
        main_file = join(self.module_path, "__main__.py")

        if exists(main_file):
            self.process_file(main_file)

        if exists(init_file) and "__init__.py" not in self.processed_files:
            self.process_file(init_file)

        for file_path in self.iter_files():
            self.process_file(file_path, append=True)

        success(f"Successfully processed {len(self.processed_files)} python files.")
        final_code = self.generate_code()

        # Write to output file
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(final_code)

        success(f"Module merged successfully into {self.output_file}!")

        # generate and run tests
        if self.run_test_scripts:
            return self.generate_and_run_tests()
        return True

    def generate_code(self):
        # header and metadata
        merged_code = [self.generate_module_docstring()]

        # __all__
        all_node = self.generate_all_node()
        if all_node:
            merged_code.append(ast.unparse(ast.fix_missing_locations(all_node)))
            merged_code.append("\n\n")

        # top level imports if organized
        if self.organize_imports:
            try:
                top_level_imports = self.organize_to_level_imports()
                if top_level_imports:
                    merged_code.extend([ast.unparse(node) + "\n" for node in top_level_imports])
                    merged_code.append("\n\n")
            except ImportConflictException as e:
                error(str(e))
                raise

        # TODO: some code reordering

        # code
        for parse_result, rel_path in self.processed_code:
            # TODO replace internal_imports_all as with assignment

            # remove some elements
            elements_to_remove = parse_result.internal_imports_all + parse_result.all_nodes
            if self.organize_imports:
                elements_to_remove += parse_result.external_imports_nodes

            for node in set(elements_to_remove):
                node.remove()

            merged_code.append(f"# --- Start of {rel_path} ---\n")
            code = parse_result.root_node.get_code() if parse_result.root_node else None
            if not code or not code.strip():
                # merged_code.append("# --- empty file")
                pass
            else:
                merged_code.append(code)
            merged_code.append(f"\n# --- End of {rel_path} ---\n")
            merged_code.append("\n\n")

        return ''.join(merged_code)

    def parse_python_file(self, file_path) -> 'FileParseResult':
        """Parses a Python file and extracts valid code while handling imports, '__all__', and redundant entries."""
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        explicit_all_entries = set()
        all_nodes = list()
        external_imports_nodes = list()
        internal_imports_nodes = list()
        internal_imports_all = list()

        if not code or not code.strip():
            return FileParseResult(root_node=None, explicit_all_entries=explicit_all_entries, all_nodes=all_nodes,
                                   external_imports_nodes=external_imports_nodes,
                                   internal_imports_nodes=internal_imports_nodes,
                                   internal_imports_all=internal_imports_all)

        parser = ScriptParser(code)
        root_node = parser.parse()

        # look for __all__ & imports in top level statements
        for node in root_node.children:
            if isinstance(node.node, (ast.Import, ast.ImportFrom)):  # process top-level imports
                if node.is_internal_import(self.module_name):
                    internal_imports_nodes.append(node)
                else:
                    external_imports_nodes.append(node)
            extracted_all_names = node.extract_all_names()
            if extracted_all_names is not None:
                explicit_all_entries.update(extracted_all_names)
                all_nodes.append(node)

        # remove internal imports
        for node in root_node.walk():
            if node.is_internal_import(self.module_name):
                internal_imports_all.append(node)

        return FileParseResult(root_node=root_node, explicit_all_entries=explicit_all_entries, all_nodes=all_nodes,
                               external_imports_nodes=external_imports_nodes,
                               internal_imports_nodes=internal_imports_nodes, internal_imports_all=internal_imports_all)

    def process_file(self, file_path, append=False):
        rel_path = relpath(file_path, self.module_path)
        parse_result: FileParseResult = self.parse_python_file(file_path)
        import_paths, imported_names = self.process_internal_imports(file_path, parse_result.internal_imports_nodes)
        if rel_path == '__init__.py':
            self.all_init_explicit_entries.update(parse_result.explicit_all_entries)
            self.all_init_implicit_entries = imported_names
        else:
            self.all_other_explicit_entries.update(parse_result.explicit_all_entries)

        self.all_external_imports.update(script_node.node for script_node in parse_result.external_imports_nodes)

        # global names warnings
        self.check_global_names(parse_result, rel_path)

        # processed code
        if append:
            self.processed_code.append((parse_result, rel_path))
        else:
            self.processed_code.insert(0, (parse_result, rel_path))
        self.processed_files.add(rel_path)

        # process next paths:
        # TODO: some code reordering??
        for path in import_paths:
            rel_path = relpath(path, self.module_path)
            if rel_path not in self.processed_files:
                self.process_file(path)

    def check_global_names(self, parse_result, rel_path):
        if parse_result.root_node and parse_result.root_node.context:
            for name, script_node in parse_result.root_node.context.items():
                # ignore _
                if name == '_':
                    continue

                # ignore internal imports
                if script_node.is_internal_import(self.module_name):
                    continue

                # ignore external imports without asname
                if isinstance(script_node.node, (ast.Import, ast.ImportFrom)):
                    # find which alias
                    alias = None
                    for alias in script_node.node.names:
                        if (alias.asname or alias.name) == name:
                            break

                    # check asname
                    if not alias or not alias.asname:
                        continue

                if name in self.global_context:
                    other_rel_path, other_script_node = self.global_context[name]
                    warning(
                        f"Global alias conflict {name} exists in two files {rel_path} and {other_rel_path}.")
                    self.global_context_conflicts[name].update((rel_path, other_rel_path))
                else:
                    self.global_context[name] = rel_path, script_node

    def process_internal_imports(self, current_path, internal_imports: list[ScriptNode]):
        imported_names = set()
        import_paths = set()
        for import_node in internal_imports:
            node_import_paths, node_imported_names = self.process_internal_import(current_path, import_node.node)
            import_paths.update(node_import_paths)
            if node_imported_names:
                imported_names.update(node_imported_names)
        return import_paths, imported_names

    def process_internal_import(self, current_path, import_node: ast.AST):
        imported_names = None
        import_paths = list()

        def _find_module_file(_sub_module_parent, _sub_module_name):
            for path in (
                    join(_sub_module_parent, _sub_module_name, "__init__.py"),
                    join(_sub_module_parent, f"{_sub_module_name}.py"),
            ):
                if isfile(path):
                    return path
            return None

        if isinstance(import_node, ast.Import):
            for alias in import_node.names:
                assert ScriptNode.is_local_module(self.module_name, alias.name)
                sub_module_import_path_parts = alias.name.split('.')
                sub_module_parent_dir = join(self.module_path, *sub_module_import_path_parts[1:-1])
                sub_module_file_path = _find_module_file(sub_module_parent_dir, sub_module_import_path_parts[-1])
                if sub_module_file_path:
                    import_paths.append(sub_module_file_path)
        elif isinstance(import_node, ast.ImportFrom):
            # Relative or absolute import (e.g., from .utils import x or from mymodule.utils import x)

            assert import_node.level > 0 or ScriptNode.is_local_module(self.module_name, import_node.module)

            if import_node.level > 0:  # relative
                start_path = normpath(join(current_path, '../' * import_node.level))
                if import_node.module:
                    sub_module_import_path_parts = import_node.module.split('.')
                    sub_module_parent_dir = join(start_path, *sub_module_import_path_parts[:-1])
                    sub_module_file_path = _find_module_file(sub_module_parent_dir, sub_module_import_path_parts[-1])
                else:  # Handle 'from . import x'
                    start_path, sub_module_name = dirname(start_path), basename(start_path)
                    sub_module_file_path = _find_module_file(start_path, sub_module_name)
            else:  # absolute
                sub_module_import_path_parts = import_node.module.split('.')
                sub_module_parent_dir = join(self.module_path, *sub_module_import_path_parts[1:-1])
                sub_module_file_path = _find_module_file(sub_module_parent_dir, sub_module_import_path_parts[-1])

            if sub_module_file_path:
                import_paths.append(sub_module_file_path)

            # Find imported names
            imported_names = [alias.name for alias in import_node.names]

        return import_paths, imported_names

    def organize_to_level_imports(self) -> list[Union[ast.Import, ast.ImportFrom]]:
        imports = {}
        from_imports = {}
        names = {}

        def raise_conflict(_name, _new_pointer):
            if isinstance(names[_name], ast.Import):
                _existing_pointer = names[_name].names[0].name
            else:
                _existing_pointer = names[_name]
            raise ImportConflictException(_name, _existing_pointer, _new_pointer)

        for node in self.all_external_imports:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    if name not in names:
                        new_node = ast.Import(names=[ast.alias(name=alias.name, asname=alias.asname)])
                        imports[name] = new_node
                        names[name] = new_node
                    elif not isinstance(names[name], ast.Import) or names[name].names[0].name != alias.name:
                        raise_conflict(name, alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module not in from_imports:
                    from_imports[node.module] = ast.ImportFrom(module=node.module, names=[], level=0)

                existing_node = from_imports[node.module]
                for alias in node.names:  # merge only ImportFrom
                    name = alias.asname or alias.name
                    fullname = f"{node.module}.{alias.name}"
                    if name not in names:
                        existing_node.names.append(alias)
                        names[name] = fullname
                    elif not isinstance(names[name], str) or names[name] != fullname:
                        raise_conflict(name, fullname)

        # sort from imports
        for from_import in from_imports.values():
            from_import.names.sort(key=lambda _alias: _alias.name)

        # sort imports
        imports_lst: list[ast.Import] = list(imports.values())
        imports_lst.sort(key=lambda _node: _node.names[0].name)
        from_imports_lst: list[ast.ImportFrom] = list(from_imports.values())
        from_imports_lst.sort(key=lambda _node: _node.module)
        final_list: list[Union[ast.Import, ast.ImportFrom]] = list()

        final_list.extend(imports_lst)
        final_list.extend(from_imports_lst)

        return final_list

    def generate_all_node(self):
        all_names = self.process_all()
        if all_names:
            return ast.Assign(
                targets=[ast.Name(id="__all__")],
                value=ast.List(elts=[ast.Constant(value=item) for item in all_names], )
            )
        return None

    def process_all(self):
        if self.process_all_strategy == ProcessAllStrategy.NONE:
            return None

        if self.process_all_strategy == ProcessAllStrategy.AUTO:
            if self.custom_all:
                all_names = list(self.custom_all)
            else:  # explicit * + implicit __init__
                all_names = list(self.all_init_implicit_entries.union(self.all_init_explicit_entries).union(
                    self.all_other_explicit_entries))

        else:  # self.process_all_strategy == ProcessAllStrategy.INIT:
            all_names = list(self.all_init_explicit_entries)

        all_names.extend(self.additional_all)
        return sorted(set(all_names))

    def generate_module_docstring(self, ):
        docstring_parts = [
            f'"""',
            'This module was automatically generated By Monoscript (https://github.com/xaled/monoscript).',
            f"Module Name: {self.module_name}",
            f"Description: {self.module_description}",
            f"Version: {self.module_version}",
            f"Author: {self.author}", f"License: {self.license}"
        ]
        if self.requirements is None:
            req_filepath = join(self.module_parent, self.requirements_filename)
            try:
                with open(req_filepath) as fou:
                    requirements = [req.strip() for req in fou.readlines()]
            except Exception as e:
                error(f"Could not load requirements file {req_filepath}: {e}")
                requirements = None
        else:
            requirements = self.requirements

        if requirements:
            docstring_parts.append(f"Requirements: {', '.join(requirements)}")

        if self.project_website:
            docstring_parts.append(f"Website: {self.project_website}")

        generation_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current time
        docstring_parts.append(f"Generated On: {generation_time}")

        if self.additional_headers:
            docstring_parts.append("\nAdditional Metadata:")
            for key, value in self.additional_headers.items():
                docstring_parts.append(f"  {key}: {value}")

        docstring_parts.append('"""\n')  # Close the docstring

        return '\n'.join(docstring_parts)

    def generate_and_run_tests(self):
        info(f"Started merging test scripts...")

        if self.merge_test_scripts:
            self.test_merger = PythonModuleMerger(
                self.test_scripts_dirpath, output_dir=join(self.output_dir, 'tests'),
                process_all_strategy=ProcessAllStrategy.NONE,
                module_name=f"test_{self.module_name}",
                module_description=f'Test script for {self.module_name}', author=self.author,
                license=self.license,
                run_test_scripts=False,
                merge_test_scripts=False,
            )
            self.test_merger.merge_files()
            test_dir = self.test_merger.output_dir
            test_files = [self.test_merger.output_file]
        else:
            test_dir = self.test_scripts_dirpath
            test_files = [join(self.test_scripts_dirpath, fn) for fn in os.listdir(self.test_scripts_dirpath) if
                          fn.endswith('.py') and fn.startswith('test_')]

        env = self._get_run_tests_env()
        test_results = [self._run_test_script(test_file, env=env, cwd=test_dir) for test_file in test_files]
        return all(test_results)

    @staticmethod
    def _run_test_script(filepath, env, cwd):
        info(f"Running test script {filepath}...")
        result = subprocess.run([sys.executable, abspath(filepath)], cwd=cwd,
                                env=env)
        if result.returncode == 0:
            success(f"Test script {filepath} finished successfully")
        else:
            error(f"Test script {filepath} returned errors.")
        return result.returncode == 0

    def _get_run_tests_env(self):
        env = os.environ.copy()
        # print(env.get('PYTHONPATH', ''))
        python_paths = env.get('PYTHONPATH', '').split(os.pathsep)
        module_parent = abspath(self.module_parent)

        # remove module parent script
        if module_parent in python_paths:
            python_paths.remove(module_parent)

        # add module output path
        python_paths.insert(0, abspath(self.output_dir))

        env['PYTHONPATH'] = os.pathsep.join(python_paths)
        # print(env['PYTHONPATH'])
        return env


class ImportConflictException(Exception):

    def __init__(self, alias_name, existing_pointer, new_pointer):
        super(ImportConflictException, self).__init__(
            f"Import conflict alias {alias_name} points to two different objects: "
            f"{repr(existing_pointer)} and {repr(new_pointer)}!")
        self.alias_name = alias_name
        self.existing_pointer = existing_pointer
        self.new_pointer = new_pointer


def unparse_node(node):
    if isinstance(node, ast.AST):
        module = node
    else:
        module = ast.Module(body=[node], type_ignores=[])

    return ast.unparse(module)


@dataclass
class FileParseResult:
    root_node: Optional[ScriptNode]
    explicit_all_entries: set[str]
    all_nodes: list[ScriptNode]
    external_imports_nodes: list[ScriptNode]
    internal_imports_nodes: list[ScriptNode]
    internal_imports_all: list[ScriptNode]
