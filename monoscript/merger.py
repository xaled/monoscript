import os
import ast
from dataclasses import dataclass
from enum import Enum
from typing import Union

from monoscript.parser import ScriptParser, ScriptNode


class ProcessAllStrategy(Enum):
    NONE = 0
    AUTO = 1
    INIT = 2


class PythonModuleMerger:
    def __init__(self, module_path, output_dir='dist',
                 process_all_strategy: ProcessAllStrategy = ProcessAllStrategy.AUTO, custom_all=None,
                 additional_all=None,
                 organize_imports=True):
        self.module_path = os.path.abspath(module_path)
        self.module_name = os.path.basename(module_path)
        self.output_dir = output_dir
        self.output_file = os.path.join(output_dir, f"{self.module_name}.py")
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

    def iter_files(self):
        for root, _, files in os.walk(self.module_path):
            for filename in sorted(files):
                if filename.endswith(".py"):
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, self.module_path)
                    if rel_path in self.processed_files:
                        continue
                    yield file_path

    def merge_files(self):
        """Merges all Python files into a single file while handling imports and '__all__'."""
        # Process __init__.py first (to extract __all__)
        init_file = os.path.join(self.module_path, "__init__.py")
        if os.path.exists(init_file):
            self.process_file(init_file)

            for file_path in self.iter_files():
                self.process_file(file_path, append=True)

        final_code = self.generate_code()

        # Write to output file
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(final_code)

        print(f"Module merged successfully into {self.output_file}!")

    def generate_code(self):
        merged_code = []

        # header and metadata # TODO

        # __all__
        all_node = self.process_all()
        if all_node:
            merged_code.append(ast.unparse(ast.fix_missing_locations(all_node)))
            merged_code.append("\n\n")

        # top level imports if organized
        if self.organize_imports:
            top_level_imports = self.organize_to_level_imports()
            merged_code.extend([ast.unparse(node) + "\n" for node in top_level_imports])
            merged_code.append("\n\n")

        # code
        for parse_result, rel_path in self.processed_code:
            # remove some elements
            elements_to_remove = parse_result.internal_imports_all + parse_result.all_nodes
            if self.organize_imports:
                elements_to_remove += parse_result.external_imports_nodes

            for node in set(elements_to_remove):
                node.remove()

            merged_code.append(f"# --- {rel_path} ---\n")
            merged_code.extend(parse_result.root_node.get_code())
            merged_code.append("\n\n")

        return ''.join(merged_code)

    def parse_python_file(self, file_path) -> 'FileParseResult':
        """Parses a Python file and extracts valid code while handling imports, '__all__', and redundant entries."""
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        parser = ScriptParser(code)
        root_node = parser.parse()

        explicit_all_entries = set()
        all_nodes = list()
        external_imports_nodes = list()
        internal_imports_nodes = list()
        internal_imports_all = list()

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

        rel_path = os.path.relpath(file_path, self.module_path)
        parse_result: FileParseResult = self.parse_python_file(file_path)
        import_paths, imported_names = self.process_internal_imports(file_path, parse_result.internal_imports_nodes)
        if rel_path == '__init__.py':
            self.all_init_explicit_entries.update(parse_result.explicit_all_entries)
            self.all_init_implicit_entries = imported_names
        else:
            self.all_other_explicit_entries.update(parse_result.explicit_all_entries)

        self.all_external_imports.update(script_node.node for script_node in parse_result.external_imports_nodes)

        # processed code
        if append:
            self.processed_code.append((parse_result, rel_path))
        else:
            self.processed_code.insert(0, (parse_result, rel_path))
        self.processed_files.add(rel_path)

        # process next paths:
        for path in import_paths:
            rel_path = os.path.relpath(path, self.module_path)
            if rel_path not in self.processed_files:
                self.process_file(path)

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
                    os.path.join(_sub_module_parent, _sub_module_name, "__init__.py"),
                    os.path.join(_sub_module_parent, f"{_sub_module_name}.py"),
            ):
                if os.path.isfile(path):
                    return path
            return None

        if isinstance(import_node, ast.Import):
            for alias in import_node.names:
                assert alias.name.startswith(self.module_name + ".")
                sub_module_import_path_parts = alias.name.split('.')
                sub_module_parent_dir = os.path.join(self.module_path, *sub_module_import_path_parts[1:-1])
                sub_module_file_path = _find_module_file(sub_module_parent_dir, sub_module_import_path_parts[-1])
                if sub_module_file_path:
                    import_paths.append(sub_module_file_path)
        elif isinstance(import_node, ast.ImportFrom):
            # Relative or absolute import (e.g., from .utils import x or from mymodule.utils import x)

            assert import_node.level > 0 or import_node.module.startswith(self.module_name + ".")

            if import_node.level > 0:  # relative
                start_path = os.path.normpath(os.path.join(current_path, '../' * import_node.level))
                if import_node.module:
                    sub_module_import_path_parts = import_node.module.split('.')
                    sub_module_parent_dir = os.path.join(start_path, *sub_module_import_path_parts[:-1])
                    sub_module_file_path = _find_module_file(sub_module_parent_dir, sub_module_import_path_parts[-1])
                else:  # Handle 'from . import x'
                    start_path, sub_module_name = os.path.dirname(start_path), os.path.basename(start_path)
                    sub_module_file_path = _find_module_file(start_path, sub_module_name)
            else:  # absolute
                sub_module_import_path_parts = import_node.module.split('.')
                sub_module_parent_dir = os.path.join(self.module_path, *sub_module_import_path_parts[1:-1])
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
        return ast.Assign(
            targets=[ast.Name(id="__all__")],
            value=ast.List(elts=[ast.Constant(value=item) for item in sorted(all_names)], )
        )


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
    root_node: ScriptNode
    explicit_all_entries: set[str]
    all_nodes: list[ScriptNode]
    external_imports_nodes: list[ScriptNode]
    internal_imports_nodes: list[ScriptNode]
    internal_imports_all: list[ScriptNode]
