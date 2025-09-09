import myers
from copy import copy

from .grouped_shader import CodeLineGroup, DiffedShaderWithGroupedLines
from .type_aliases import FunctionName, ShaderFlags, ShaderLineIndex
from .permutation import EncodedUniqufiedPermutations


class DiffedCode:
    lines: list[ShaderLineIndex]
    line_conditions: list[list[ShaderFlags]]

    def __init__(self):
        self.lines = []
        self.line_conditions = []

    def group_lines(self):
        """
        Groups consecutive lines with identical conditions into line group objects
        """
        line_groups: list[CodeLineGroup] = []

        if len(self.lines) == 0:
            return line_groups

        current_group = CodeLineGroup()
        current_group.condition = self.line_conditions[0]
        for line, condition in zip(self.lines, self.line_conditions):
            if condition != current_group.condition:
                line_groups.append(current_group)
                current_group = CodeLineGroup()
                current_group.condition = condition

            current_group.lines.append(line)

        line_groups.append(current_group)
        return line_groups


class DiffedShader:
    main_code: DiffedCode
    functions: dict[FunctionName, DiffedCode]

    def __init__(self):
        self.main_code = DiffedCode()
        self.functions = {}

    def group_lines(self):
        grouped_shader = DiffedShaderWithGroupedLines()

        grouped_shader.main_code = self.main_code.group_lines()
        for func_name, func in self.functions.items():
            grouped_shader.functions[func_name] = func.group_lines()

        return grouped_shader


def diff_permutations(encoded_permutations: EncodedUniqufiedPermutations):
    """
    Combines (by diffing) permutations of code together into one `DiffedCode` object
    """
    lines: list[ShaderLineIndex] = []
    new_conditions: list[list[ShaderFlags]]
    line_conditions: list[list[ShaderFlags]] = []
    for code, flag_list in zip(encoded_permutations.codes, encoded_permutations.flags):
        diff = myers.diff(lines, code)
        lines = []
        new_conditions = []
        current_index = 0
        for op, val in diff:
            lines.append(val)
            if op == "i":
                new_conditions.append(copy(flag_list))
            elif op == "r":
                new_conditions.append(line_conditions[current_index])
                current_index += 1
            elif op == "k":
                condition = line_conditions[current_index]
                condition.extend(flag_list)
                new_conditions.append(condition)
                current_index += 1
        line_conditions = new_conditions

    diffed_shader = DiffedCode()
    diffed_shader.lines = lines
    diffed_shader.line_conditions = line_conditions

    return diffed_shader
