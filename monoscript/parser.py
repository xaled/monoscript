import ast
import os
from collections import defaultdict
from typing import List, Optional, Generator


class ScriptNode:
    def __init__(self, node: ast.AST, children: Optional[List['ScriptNode']] = None,
                 parent: 'ScriptNode' = None, code_lines=None, root: 'ScriptNode' = None):
        self.parent: Optional[ScriptNode] = parent
        self.code_lines = code_lines
        self.node: ast.AST = node  # The AST node
        self.removed_parts = list()

        # root and coords
        if root:
            self.root = root
            self.start_line = getattr(self.node, 'lineno', None)
            self.start_col = getattr(self.node, 'col_offset', None)
            self.end_line = getattr(self.node, 'end_lineno', None)
            self.end_col = getattr(self.node, 'end_col_offset', None)
        else:
            self.root = self
            self.start_line = 1
            self.start_col = 0
            self.end_line = len(self.code_lines)
            self.end_col = len(self.code_lines[-1])

        # children
        self.children = children if children is not None else []  # Parsed children nodes
        for child in self.children:
            child.parent = self

        # context
        if self.parent is None or isinstance(self.node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self.context = list()
        else:
            self.context = self.parent.context

        self._extract_context_names()

    def _extract_context_names(self):
        def _process_assign_targets(_targets):
            for _target in _targets:
                if isinstance(_target, ast.Name):
                    self.context.append(_target.id)
                elif isinstance(_target, ast.Tuple):
                    _process_assign_targets(_target.elts)

        if isinstance(self.node, (ast.Import, ast.ImportFrom)):
            for alias in self.node.names:
                self.context.append(alias.asname or alias.name)
        elif isinstance(self.node, ast.Assign):
            _process_assign_targets(self.node.targets)
        elif isinstance(self.node, (ast.AnnAssign, ast.For)):
            _process_assign_targets([self.node.target])
        elif isinstance(self.node, ast.withitem):
            if self.node.optional_vars:
                _process_assign_targets([self.node.optional_vars])
        elif isinstance(self.node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if self.parent:
                self.parent.context.append(self.node.name)
            else:
                self.context.append(self.node.name)
            # TODO: function & async function parameter names
        elif isinstance(self.node, (ast.Global, ast.Nonlocal)):
            self.context.extend(self.node.names)

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

    def find_node_in_children(self, node):
        for child in self.children:
            if child.node == node:
                return child

    def is_internal_import(self, module_name):
        """Checks if an import is internal (e.g., 'from mymodule.utils import x' or 'from .utils import x')."""
        if isinstance(self.node, ast.Import):
            # TODO: Fix any by extracting imports or adding a warning if not all
            return any(self.is_local_module(module_name, alias.name) for alias in self.node.names)
        elif isinstance(self.node, ast.ImportFrom):
            return self.node.level > 0 or self.is_local_module(module_name, self.node.module)
        return False

    @staticmethod
    def is_local_module(module_name, module_path):
        return module_path == module_name or module_path.startswith(module_name + ".")

    def extract_all_names(self) -> Optional[List[str]]:
        if not isinstance(self.node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            return

        # accept only += AugAssign
        if isinstance(self.node, ast.AugAssign) and not isinstance(self.node.op, ast.Add):
            return

        targets = self.node.targets if isinstance(self.node, ast.Assign) else [self.node.target]

        # __all__ is target
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            return

        # find string literals in the value expression
        # value_script_node = self.find_node_in_children(self.node.value)
        # all_names = [n.s for n in value_script_node.walk() if isinstance(n, ast.Str)]

        all_names = [elt.s for elt in getattr(self.node.value, 'elts', []) if isinstance(elt, ast.Str)]
        return all_names

    @staticmethod
    def parse_node(node, code_lines, parent: 'ScriptNode' = None) -> 'ScriptNode':
        # Extract the source substring for this node

        root = parent.root if parent else None

        # Create a ScriptNode for this AST node
        script_node = ScriptNode(node=node, children=[], parent=parent, root=root,
                                 code_lines=code_lines)

        # Extract children nodes
        children = []
        for field_name, value in ast.iter_fields(node):
            if isinstance(value, list):  # List of child nodes
                for item in value:
                    if isinstance(item, ast.AST):
                        children.append(ScriptNode.parse_node(item, code_lines, parent=script_node))
            elif isinstance(value, ast.AST):  # Single child node
                children.append(ScriptNode.parse_node(value, code_lines, parent=script_node))
        script_node.children = children

        return script_node

    def walk(self) -> Generator['ScriptNode', None, None]:
        for child in self.children:
            yield from child.walk()
        yield self

    def remove(self):
        self.parent.remove_child(self)


class ScriptParser:
    def __init__(self, code):
        self.code = code
        self.code_lines = None

    def parse(self) -> ScriptNode:
        self.code_lines = self.code.splitlines()

        # Parse the code into an AST
        tree = ast.parse(self.code)

        # Process the top-level nodes
        return ScriptNode.parse_node(tree, self.code_lines)


# def is_internal_import(module_name, node):
#     """Checks if an import is internal (e.g., 'from mymodule.utils import x' or 'from .utils import x')."""
#     if isinstance(node, ast.Import):
#         return any(alias.name.startswith(module_name + ".") for alias in node.names)
#     elif isinstance(node, ast.ImportFrom):
#         return node.module and (node.module.startswith(module_name + '.') or node.level > 0)
#     return False


# def extract_explicit_all(node):
#     """Extracts explicit '__all__' assignments from a module."""
#     if isinstance(node, ast.Assign):
#         for target in node.targets:
#             if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value,
#                                                                                       (ast.List, ast.Tuple)):
#                 return [elt.s for elt in node.value.elts if isinstance(elt, ast.Str)]
#     return []


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
