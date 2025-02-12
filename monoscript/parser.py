import ast
import os
from collections import defaultdict
from typing import List, Optional


class ScriptNode:
    def __init__(self, node: ast.AST, children: Optional[List['ScriptNode']] = None,
                 parent: 'ScriptNode' = None, code_lines=None, root: 'ScriptNode' = None):
        self.parent = parent
        self.code_lines = code_lines
        if root:
            self.root = root
            self.start_line = getattr(node, 'lineno', None)
            self.start_col = getattr(node, 'col_offset', None)
            self.end_line = getattr(node, 'end_lineno', None)
            self.end_col = getattr(node, 'end_col_offset', None)
        else:
            self.root = self
            self.start_line = 1
            self.start_col = 0
            self.end_line = len(self.code_lines)
            self.end_col = len(self.code_lines[-1])
        self.node = node  # The AST node
        self._code = None
        self.children = children if children is not None else []  # Parsed children nodes
        for child in self.children:
            child.parent = self

        self.removed_parts = list()

    def __repr__(self):
        return f"ScriptNode(type={type(self.node).__name__}, code={repr(self.get_code())}, children={len(self.children)})"

    def get_code(self) -> Optional[str]:
        """Extracts the code corresponding to the given node."""

        # start_line, start_col, end_line, end_col = None, None, None, None
        if all(attrib is not None for attrib in (self.start_line, self.end_line, self.start_col, self.end_col)):
            if self.root == self:  # root element
                lines = list(self.code_lines)
            else:
                lines = self.code_lines[self.start_line - 1:self.end_line]

            # if self.end_col != len(lines[-1]):
            #     _slice_line(-1, 0, self.end_col)
            #
            # if self.start_col != 0:
            #     lines[0] = lines[0][self.start_col:]
            #     _slice_line(0, self.start_col, None)

            # generate cuts
            lines_cuts = defaultdict(list)
            # start and end col
            if self.end_col != len(lines[-1]):
                lines_cuts[self.end_line - self.start_line].append((self.end_col, len(lines[-1])))

            if self.start_col != 0:
                lines_cuts[0].append((0, self.start_col))

            # remove parts cuts
            for start_line, start_col, end_line, end_col in self.removed_parts:
                if start_line == end_line:
                    lines_cuts[start_line - self.start_line].append((start_col, end_col))
                else:

                    # start line
                    lines_cuts[start_line - self.start_line].append((start_col, len(lines[start_line - 1])))
                    # end line
                    lines_cuts[end_line - self.start_line].append((0, end_col))
                    # middle lines
                    for line_ix in range(start_line + 1, end_line):
                        lines_cuts[line_ix - self.start_line].append((0, len(lines[line_ix - 1])))
            # print(lines_cuts)

            clipped_lines = list()
            for ix in range(len(lines)):
                # print(ix, not lines[ix].strip() or not lines_cuts[ix])
                if not lines[ix].strip() or not lines_cuts[ix]:
                    # print(lines[ix], lines_cuts[ix], merge_cuts(lines_cuts[ix]))

                    clipped_lines.append(lines[ix])
                else:
                    line = apply_cuts(lines[ix], cuts=merge_cuts(lines_cuts[ix]))
                    # print(lines[ix], lines_cuts[ix], merge_cuts(lines_cuts[ix]), repr(line))
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith('#'):
                        clipped_lines.append(line)

            return '\n'.join(clipped_lines)

    def remove_child(self, child: 'ScriptNode'):
        # remove from children
        self.children.remove(child)

        # find and remove from node
        attrib = self.find_child_node(child.node)
        attrib.remove(child.node)  # must be list to remove

        # find and remove from code
        self.remove_child_parts(child)

    def remove_child_parts(self, child):
        self.removed_parts.append((child.start_line, child.start_col, child.end_line, child.end_col))
        if self.parent:
            self.parent.remove_child_parts(child)

    def find_child_node(self, child_node):
        for field_name, value in ast.iter_fields(self.node):
            if child_node == value or isinstance(value, list) and child_node in value:  # List of child nodes
                return value


class ScriptParser:
    def __init__(self):
        self.code_lines = None
        self.code = None

    def parse(self, code: str) -> ScriptNode:
        self.code = code
        self.code_lines = code.splitlines()

        # Parse the code into an AST
        tree = ast.parse(self.code)

        # Process the top-level nodes
        return self._parse_node(tree)

    # def _get_node_source(self, node: ast.AST, ):
    #     """Extracts the code corresponding to the given node."""
    #     # start_line, start_col, end_line, end_col = None, None, None, None
    #     # print(self.code_lines)
    #     result = None
    #     partial = True
    #     lines = None
    #     if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
    #         start_line, start_col = node.lineno, node.col_offset
    #         end_line = getattr(node, 'end_lineno', None)
    #         end_col = getattr(node, 'end_col_offset', None)
    #
    #         if end_line is not None and end_col is not None:
    #             lines = self.code_lines[start_line - 1:end_line]
    #             if start_col != 0 or end_col != len(self.code_lines[end_line - 1]):
    #                 if start_line == end_line:
    #                     result = self.code_lines[start_line - 1][start_col:end_col]
    #                     # if lines[0].lstrip() == lines[0][start_col:end_col]:
    #                     #     pass
    #                     # else:
    #                     #     print(f"{type(node)=}", start_line, start_col, end_line, end_col, )
    #                     #     print(lines, result)
    #                     #     print("---")
    #                 else:
    #                     print(f"{type(node)=}", start_line, start_col, end_line, end_col, )
    #                     print(lines, result)
    #                     print("---")
    #                     result = (
    #                             self.code_lines[start_line - 1][start_col:] + '\n' +
    #                             '\n'.join(self.code_lines[start_line:end_line - 1]) + '\n' +
    #                             self.code_lines[end_line - 1][:end_col]
    #                     )
    #
    #             else:
    #                 partial = False
    #                 result = '\n'.join(lines)
    #
    #     # if unparse_result.strip() != result.strip():
    #     #     print(f"{type(node)=}", start_line, start_col, end_line, end_col, )
    #     #     print(repr(result))
    #     #     print(repr(unparse_result))
    #     #     print('---')
    #
    #     return result, lines, partial

    # def _get_node_source(self, node: ast.AST, ) -> str:
    #     """Extracts the code corresponding to the given node."""
    #     # start_line, start_col, end_line, end_col = None, None, None, None
    #     result = None
    #     if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
    #         start_line, start_col = node.lineno, node.col_offset
    #         end_line = getattr(node, 'end_lineno', None)
    #         end_col = getattr(node, 'end_col_offset', None)
    #
    #         if end_line is not None and end_col is not None:
    #             if start_line == end_line:
    #                 result = self.code_lines[start_line - 1][start_col:end_col]
    #             else:
    #                 result = (
    #                         self.code_lines[start_line - 1][start_col:] + '\n' +
    #                         '\n'.join(self.code_lines[start_line:end_line - 1]) + '\n' +
    #                         self.code_lines[end_line - 1][:end_col]
    #                 )
    #
    #     # if unparse_result.strip() != result.strip():
    #     #     print(f"{type(node)=}", start_line, start_col, end_line, end_col, )
    #     #     print(repr(result))
    #     #     print(repr(unparse_result))
    #     #     print('---')
    #
    #     return result

    def _parse_node(self, node, parent: ScriptNode = None) -> ScriptNode:
        # Extract the source substring for this node

        root = parent.root if parent else None

        # Create a ScriptNode for this AST node
        script_node = ScriptNode(node=node, children=[], parent=parent, root=root,
                                 code_lines=self.code_lines)

        # Extract children nodes
        children = []
        for field_name, value in ast.iter_fields(node):
            if isinstance(value, list):  # List of child nodes
                for item in value:
                    if isinstance(item, ast.AST):
                        children.append(self._parse_node(item, parent=script_node))
            elif isinstance(value, ast.AST):  # Single child node
                children.append(self._parse_node(value, parent=script_node))
        script_node.children = children

        return script_node

    def parse_python_file(self, module_name, file_path):
        """Parses a Python file and extracts valid code while handling imports, '__all__', and redundant entries."""
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=os.path.basename(file_path))

        new_body = []
        explicit_all_entries = set()
        external_imports = set()
        internal_imports = set()

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):  # process top-level imports
                if is_internal_import(module_name, node):
                    internal_imports.add(node)
                else:
                    external_imports.add(node)
            elif isinstance(node, (ast.Assign, ast.AugAssign)) and any(  # process __all__
                    isinstance(target, ast.Name) and target.id == "__all__" for target in
                    (node.targets if isinstance(node, ast.Assign) else [node.target])
            ):
                explicit_all_entries.update(extract_explicit_all(node))
            else:
                new_body.append(node)

        return new_body, explicit_all_entries, external_imports, internal_imports


def is_internal_import(module_name, node):
    """Checks if an import is internal (e.g., 'from mymodule.utils import x' or 'from .utils import x')."""
    if isinstance(node, ast.Import):
        return any(alias.name.startswith(module_name + ".") for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        return node.module and (node.module.startswith(module_name + '.') or node.level > 0)
    return False


def extract_explicit_all(node):
    """Extracts explicit '__all__' assignments from a module."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value,
                                                                                      (ast.List, ast.Tuple)):
                return [elt.s for elt in node.value.elts if isinstance(elt, ast.Str)]
    return []


def merge_cuts(cuts):
    """Merges overlapping or adjacent cut definitions.

    Args:
        cuts: A list of 2-tuples representing (start_index, end_index) of cuts.

    Returns:
        A new list of 2-tuples with merged cuts.
    """

    if not cuts:
        return []

    cuts.sort()  # Sort by start index
    merged_cuts = [cuts[0]]

    for start, end in cuts[1:]:
        last_start, last_end = merged_cuts[-1]
        if start <= last_end:  # Overlapping or adjacent
            merged_cuts[-1] = (last_start, max(last_end, end))
        else:
            merged_cuts.append((start, end))

    return merged_cuts


def apply_cuts(string, cuts):
    """Applies the cuts to the string, removing the specified parts.

    Args:
        string: The input string.
        cuts: A list of 2-tuples representing (start_index, end_index) of cuts.  These should be *merged* cuts.

    Returns:
        The modified string with the cuts applied.
    """

    if not cuts:
        return string

    # Important: Process cuts in reverse order to avoid index issues after deletions.
    cuts.sort(reverse=True)  # Sort in reverse order of start index

    modified_string = list(string)  # Make it mutable
    for start, end in cuts:
        if 0 <= start < len(modified_string) and 0 <= end <= len(modified_string) and start <= end:  # handle edge cases
            modified_string[start:end] = []  # Efficient deletion using slice assignment

    return "".join(modified_string)  # back to string
