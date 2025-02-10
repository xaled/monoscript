import os
import ast


class PythonModuleMerger:
    def __init__(self, module_path, output_dir='dist', process_all="auto", custom_all=None, organize_imports=True):
        self.module_path = module_path
        self.module_name = os.path.basename(module_path)
        self.output_dir = output_dir
        self.output_file = os.path.join(output_dir, f"{self.module_name}.py")
        self.process_all = process_all  # "none", "auto", "remove"
        self.custom_all = custom_all if custom_all is not None else []
        self.organize_imports = organize_imports

        self.all_explicit_entries = []
        self.all_external_imports = set()
        self.processed_code = []
        self.merged_code = []
        self.processed_files = set()

    def is_internal_import(self, node):
        """Checks if an import is internal (e.g., 'from mymodule.utils import x' or 'from .utils import x')."""
        if isinstance(node, ast.Import):
            return any(alias.name.startswith(self.module_name + ".") for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            return node.module and (node.module.startswith(self.module_name + '.') or node.level > 0)
        return False

    def extract_explicit_all(self, node):
        """Extracts explicit '__all__' assignments from a module."""
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value,
                                                                                          (ast.List, ast.Tuple)):
                    return [elt.s for elt in node.value.elts if isinstance(elt, ast.Str)]
        return []

    def parse_python_file(self, file_path):
        """Parses a Python file and extracts valid code while handling imports, '__all__', and redundant entries."""
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)

        new_body = []
        explicit_all_entries = set()
        external_imports = set()
        internal_imports = set()

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):  # process top-level imports
                if self.is_internal_import(node):
                    internal_imports.add(node)
                else:
                    external_imports.add(node)
            elif isinstance(node, (ast.Assign, ast.AugAssign)) and any(  # process __all__
                    isinstance(target, ast.Name) and target.id == "__all__" for target in
                    (node.targets if isinstance(node, ast.Assign) else [node.target])
            ):
                explicit_all_entries.update(self.extract_explicit_all(node))
            else:
                new_body.append(node)

        return new_body, explicit_all_entries, external_imports, internal_imports

    def iter_files(self):
        for root, _, files in os.walk(self.module_path):
            for filename in sorted(files):
                if filename.endswith(".py"):
                    file_path = os.path.join(root, filename)
                    if file_path in self.processed_files:
                        continue
                    yield file_path

    def merge_files(self):
        """Merges all Python files into a single file while handling imports and '__all__'."""
        # Process __init__.py first (to extract __all__)
        init_file = os.path.join(self.module_path, "__init__.py")
        if os.path.exists(init_file):
            body, explicit_all, external_imports = self.parse_python_file(init_file)
            if self.process_all == "auto":
                self.all_explicit_entries.extend(explicit_all)
            self.all_external_imports.update(external_imports)
            self.merged_code.append(f"# --- __init__.py ---\n")
            self.merged_code.extend([ast.unparse(node) + "\n" for node in body])
            self.merged_code.append("\n")

            for file_path in self.iter_files():
                self.process_file(file_path)

        # Add cleaned-up external imports at the top
        final_code = self.process_top_level_imports()

        # Handle final __all__ statement
        if self.process_all != "none":
            merged_all = sorted(set(self.all_explicit_entries + self.custom_all))
            if merged_all:
                final_code += f"__all__ = {merged_all}\n"

        # Write to output file
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(final_code)

        print(f"Module merged successfully into {self.output_file}!")

    def process_top_level_imports(self):
        final_code = ""
        if self.organize_imports:
            final_code += "\n".join(sorted(self.all_external_imports)) + "\n\n"
        final_code += "".join(self.merged_code)
        return final_code

    def process_file(self, file_path):

        rel_path = os.path.relpath(file_path, self.module_path)

        body, explicit_all, external_imports, internal_imports = self.parse_python_file(file_path)
        if self.process_all == "auto":
            self.all_explicit_entries.extend(explicit_all)
        self.all_external_imports.update(external_imports)
        self.processed_code.append((body, rel_path))
        self.processed_files.add(file_path)
        # self.merged_code.append(f"# --- {rel_path} ---\n")
        # self.merged_code.extend([ast.unparse(node) + "\n" for node in body])
        # self.merged_code.append("\n")

        # process imported files

    def process_internal_imports(self, current_path, import_node):
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
