import re
import time
import random
import hashlib
from math import sqrt


from .type_aliases import (
    FlagDefinition,
    FlagName,
    FlagValue,
    FunctionName,
    ShaderCode,
    ShaderFlags,
    # ShaderLine,
    ShaderLineIndex,
)
from .permutation import ShaderPermutation, EncodedUniqufiedPermutations
from .diffing import (
    DiffedShader,
    PermutationCodeLineIndex,
    PermutationIndex,
    DiffedCode,
)
from .encoded_shader import EncodedShader
from .shared_patterns import VARIABLE_NAME_PATTERN, FUNCTION_NAME_PATTERN

VariableName = str


class UniquePermutationRef:
    flags: list[ShaderFlags]

    def __init__(self, flags: list[ShaderFlags]):
        self.flags = flags

    def __hash__(self):
        return id(self)


class ShaderVariable:
    name: VariableName
    permutation_ref: UniquePermutationRef

    def __init__(self, name="", permutation_ref: UniquePermutationRef = None):
        self.name = name
        self.permutation_ref = permutation_ref

    def __hash__(self):
        return id(self)


HashableFlags = frozenset[tuple[FlagName, FlagValue]]
CodeLineVariables = tuple[ShaderVariable]


def make_hashable_flags(d: ShaderFlags) -> HashableFlags:
    return frozenset(d.items())


class VariablesDefinition:
    global_variables: dict[HashableFlags, list[CodeLineVariables]]
    functions: dict[FunctionName, dict[HashableFlags, list[CodeLineVariables]]]

    def __init__(self):
        self.global_variables = {}
        self.functions = {}


def inline_buffers(code: str):
    """
    Inlines structured buffers, by removing new lines and excessive spaces
    """
    empty_space_pattern = re.compile(r"\s+", re.DOTALL | re.MULTILINE)
    buffer_match_pattern = re.compile(
        r"^[\t ]*layout\s*\([^)]*\)\s*buffer\s+\w+\s*{.*?}\s*_\w+\s*;",
        re.DOTALL | re.MULTILINE,
    )

    matches = [m.span() for m in re.finditer(buffer_match_pattern, code)]
    for pos_from, pos_to in reversed(matches):
        code_chunk = code[pos_from:pos_to]
        code_chunk = re.sub(empty_space_pattern, " ", code_chunk)
        code = code[:pos_from] + code_chunk + code[pos_to:]

    return code


def sort_resources(code: str):
    uniforms: list[str] = []
    new_lines: list[str] = []
    first_uniform: int = None
    for line_index, line in enumerate(code.splitlines()):
        if "uniform " in line:
            if first_uniform is None:
                first_uniform = line_index

            uniforms.append(line)
        else:
            new_lines.append(line)

    if len(uniforms) > 0:
        uniforms.sort()
        new_lines = new_lines[:first_uniform] + uniforms + new_lines[first_uniform:]

    return "\n".join(new_lines)


def _gen_per_line_variables(code: str, variables: dict[VariableName, ShaderVariable]):
    var_list: list[CodeLineVariables] = []

    for line in code.splitlines(True):
        var_list.append(
            tuple(
                variables[m.group()] for m in re.finditer(VARIABLE_NAME_PATTERN, line)
            )
        )

    return var_list


def _uniquify_permutations(permutations: list[ShaderPermutation]):
    uniquified_permutations: dict[ShaderCode, list[ShaderPermutation]] = {}

    for permutation in permutations:
        permutation_list = uniquified_permutations.get(permutation.original_code, None)

        if permutation_list is None:
            permutation_list = []
            uniquified_permutations[permutation.original_code] = permutation_list

        permutation_list.append(permutation)

    return uniquified_permutations


def _update_variable_mapping(
    code: str,
    var_mapping_dict: dict[VariableName, ShaderVariable],
    permutation_ref: UniquePermutationRef,
):
    for var_match in re.finditer(VARIABLE_NAME_PATTERN, code):
        var_name = var_match.group()

        if var_name not in var_mapping_dict:
            var = ShaderVariable(var_name, permutation_ref)
            var_mapping_dict[var_name] = var


def _replace_variables(code: str):
    return re.sub(VARIABLE_NAME_PATTERN, "|||VARIABLE|||", code)


def process_stuff(shader_permutations: list[ShaderPermutation]):
    uniquified_permutations = _uniquify_permutations(shader_permutations)

    variable_definition = VariablesDefinition()
    for _, permutation_list in uniquified_permutations.items():
        flag_list: list[ShaderFlags] = []
        for permutation in permutation_list:
            flag_list.append(permutation.flags)

        permutation_ref = UniquePermutationRef(flag_list)
        global_variable_mapping: dict[VariableName, ShaderVariable] = {}
        _update_variable_mapping(
            permutation_list[0].code, global_variable_mapping, permutation_ref
        )

        global_variables = _gen_per_line_variables(
            permutation_list[0].code, global_variable_mapping
        )

        func_variables: dict[FunctionName, list[CodeLineVariables]] = {}
        for func_name, func in permutation_list[0].functions.items():
            func_variable_mapping = global_variable_mapping.copy()
            _update_variable_mapping(func.code, func_variable_mapping, permutation_ref)

            func_variables[func_name] = _gen_per_line_variables(
                func.code, func_variable_mapping
            )

        global_code = _replace_variables(permutation_list[0].code)
        func_codes = {
            name: _replace_variables(func.code)
            for name, func in permutation_list[0].functions.items()
        }

        for permutation in permutation_list:
            hashable_flags = make_hashable_flags(permutation.flags)

            variable_definition.global_variables[hashable_flags] = global_variables
            permutation.code = global_code

            for func_name, var_list in func_variables.items():
                permutation.functions[func_name].code = func_codes[func_name]

                func_flag_mapping = variable_definition.functions.get(func_name, None)

                if func_flag_mapping is None:
                    func_flag_mapping = {}
                    variable_definition.functions[func_name] = func_flag_mapping

                func_flag_mapping[hashable_flags] = var_list

    return variable_definition


LineVariableIndex = int


class ShaderLine:
    code: str
    permutation_flags: list[ShaderFlags]
    variables: tuple[list[ShaderVariable]]
    origin_list: list["ShaderLine"]
    group: list["ShaderLine"] | None

    def __init__(self):
        self.code = ""
        self.permutation_flags = []
        self.variables = tuple()
        self.origin_list = []
        self.group = None

    def __hash__(self):
        return id(self)


class ProcessedDiffedShader:
    lines: list[ShaderLine]
    function_lines: dict[FunctionName, list[ShaderLine]]

    def __init__(self):
        self.lines = []
        self.function_lines = {}

    def populate(
        self,
        diffed_shader: DiffedShader,
        encoded_shader: EncodedShader,
        variable_definition: VariablesDefinition,
    ):
        self.lines = self._populate_context(
            diffed_shader.main_code,
            encoded_shader.main_shader,
            variable_definition.global_variables,
            encoded_shader.line_decode_table,
        )

        for func_name, encoded_func in encoded_shader.functions.items():
            func_variable_def = variable_definition.functions[func_name]
            diffed_func = diffed_shader.functions[func_name]
            self.function_lines[func_name] = self._populate_context(
                diffed_func,
                encoded_func,
                func_variable_def,
                encoded_shader.line_decode_table,
            )

    @staticmethod
    def _populate_context(
        diffed_code: DiffedCode,
        permutations: EncodedUniqufiedPermutations,
        variables: dict[HashableFlags, list[CodeLineVariables]],
        line_decode_table: list[ShaderLine],
    ):
        line_variables: list[ShaderLine] = []
        for metadata_list, encoded_line, condition_list in zip(
            diffed_code.line_metadata,
            diffed_code.encoded_lines,
            diffed_code.line_conditions,
        ):
            permutation_index, line_index = metadata_list[0]
            var_count = len(
                variables[
                    make_hashable_flags(permutations.flags[permutation_index][0])
                ][line_index]
            )

            current_line = ShaderLine()
            current_line.variables = tuple([] for _ in range(var_count))
            current_line.code = line_decode_table[encoded_line]
            current_line.permutation_flags = condition_list
            current_line.origin_list = line_variables

            for permutation_index, line_index in metadata_list:
                for flags in permutations.flags[permutation_index]:
                    flags = make_hashable_flags(flags)

                    for i, variable in enumerate(variables[flags][line_index]):
                        if variable not in current_line.variables[i]:
                            current_line.variables[i].append(variable)

            line_variables.append(current_line)

        return line_variables

    # def filter_equivalent_variables(self):
    #     variable_mapping: dict[
    #         ShaderVariable, set[tuple[ShaderLine, LineVariableIndex]]
    #     ] = {}
    #     self._gather_equivalent_variables(variable_mapping, self.lines)

    #     for lines in self.function_lines.values():
    #         self._gather_equivalent_variables(variable_mapping, lines)

    #     equivalent_variables: dict[
    #         frozenset[tuple[ShaderLine, LineVariableIndex]], ShaderVariable
    #     ] = {}

    #     for variable, usage_set in variable_mapping.items():
    #         usage_set = frozenset(usage_set)
    #         dominant_variable = equivalent_variables.get(usage_set, None)

    #         if dominant_variable is None:
    #             equivalent_variables[usage_set] = variable
    #         else:
    #             for line, slot_idx in usage_set:
    #                 line.variables[slot_idx].remove(variable)

    # def _gather_equivalent_variables(
    #     self,
    #     variable_mapping: dict[
    #         ShaderVariable, set[tuple[ShaderLine, LineVariableIndex]]
    #     ],
    #     lines: list[ShaderLine],
    # ):
    #     for line in lines:
    #         for slot_idx, variables_in_slot in enumerate(line.variables):
    #             for variable in variables_in_slot:
    #                 var_set = variable_mapping.get(variable, None)

    #                 if var_set is None:
    #                     var_set = set()
    #                     variable_mapping[variable] = var_set

    #                 var_set.add((line, slot_idx))


class VariableNode:
    variable_ref: ShaderVariable

    connects: list["ConnectionNode"]

    def __init__(self, variable: ShaderVariable = None):
        self.variable_ref = variable
        self.connects = []

    def __hash__(self):
        return id(self)


class ConnectionNode:
    line_ref: ShaderLine
    nodes_in_group: list["ConnectionNode"]
    index: int

    connects: list[VariableNode]

    def __init__(self, line: ShaderLine = None, index=0):
        self.line_ref = line
        self.connects = []
        self.nodes_in_group = []
        self.index = index

    def __hash__(self):
        return id(self)


AnyNode = VariableNode | ConnectionNode


def make_variable_signature(line: str, index: int):
    line = line.replace("|||VARIABLE|||", "|||OTHER|||", index)
    line = line.replace("|||VARIABLE|||", "|||THIS|||", 1)
    line = line.replace("|||VARIABLE|||", "|||OTHER|||")
    line = re.sub(FUNCTION_NAME_PATTERN, "|||FUNCTION CALL|||", line)
    return line


class IntermediateNode:
    flags: list[ShaderFlags]

    def __init__(self):
        self.flags = []

    def __hash__(self):
        return id(self)


# Random, 50% accurate
def node_search_random(
    nodes: list[IntermediateNode],
    overlaps: list[tuple[IntermediateNode, IntermediateNode]],
):
    list_a: list[IntermediateNode] = []
    list_b: list[IntermediateNode] = []

    overlap_nodes: set[IntermediateNode] = set()

    for node in nodes:
        if bool(random.randint(0, 1)):
            list_a.append(node)
        else:
            list_b.append(node)

    if len(list_a) == 0:
        list_a.append(list_b.pop())
    elif len(list_b) == 0:
        list_b.append(list_a.pop())

    return list_a, list_b


# 100% accurate, but algorithmic complexity is too high (exponential)
def node_search_brute_force(
    nodes: list[IntermediateNode],
    overlaps: list[tuple[IntermediateNode, IntermediateNode]],
):
    overlap_nodes: set[IntermediateNode] = set()

    for node_a, node_b in overlaps:
        overlap_nodes.update((node_a, node_b))

    overlap_node_list = list(overlap_nodes)
    best_score = 0
    solutions: list[int] = []

    for bits in range(2 ** len(overlap_node_list)):
        temp_list_a = []
        temp_list_b = []
        for i, node in enumerate(overlap_node_list):
            if bool((bits >> i) & 1):
                temp_list_a.append(node)
            else:
                temp_list_b.append(node)

        score = 0
        for a, b in overlaps:
            a_check = a in temp_list_a
            b_check = b in temp_list_a

            if a_check != b_check:
                score += 1

        if score > best_score:
            best_score = score
            solutions = []

        if score == best_score:
            solutions.append(bits)

    list_a: list[IntermediateNode] = []
    list_b: list[IntermediateNode] = []
    for i, node in enumerate(overlap_node_list):
        if bool((solutions[0] >> i) & 1):
            list_a.append(node)
        else:
            list_b.append(node)

    list_a.extend(set(nodes).difference(overlap_nodes))

    return list_a, list_b


# DIY determenistic algorithm
# Idea: (I forgot what was the idea :/ )
def node_search_smart(
    nodes: list[IntermediateNode],
    overlaps: list[tuple[IntermediateNode, IntermediateNode]],
):
    overlaps = overlaps.copy()
    list_a: list[IntermediateNode] = [overlaps[0][0]]
    list_b: list[IntermediateNode] = [overlaps[0][1]]
    overlaps.pop(0)

    # Build dependencies
    while True:
        for a, b in overlaps.copy():
            if a in list_a:
                a_in = 1
            elif a in list_b:
                a_in = 2
            else:
                a_in = 0

            if b in list_a:
                b_in = 1
            elif b in list_b:
                b_in = 2
            else:
                b_in = 0

            if (a_in == 0) != (b_in == 0):
                if a_in == 0:
                    if b_in == 1:
                        list_b.append(a)
                    else:
                        list_a.append(a)
                else:
                    if a_in == 1:
                        list_b.append(b)
                    else:
                        list_a.append(b)


# Start from random partition, then move one vertex at a time
def node_search_iterative(
    nodes: list[IntermediateNode],
    overlaps: list[tuple[IntermediateNode, IntermediateNode]],
):
    overlap_nodes: dict[IntermediateNode, bool] = {}

    for node_a, node_b in overlaps:
        overlap_nodes[node_a] = False
        overlap_nodes[node_b] = False

    overlap_nodes = {k: False for k in nodes if k in overlap_nodes}

    best_score = 0
    best_solution = overlap_nodes.copy()
    for a, b in overlaps:
        if best_solution[a] != best_solution[b]:
            best_score += 1
    improving = True
    while improving:
        improving = False
        for node, list_choice in overlap_nodes.items():
            overlap_nodes[node] = not list_choice

            score = 0
            for a, b in overlaps:
                if overlap_nodes[a] != overlap_nodes[b]:
                    score += 1

            if score > best_score:
                best_score = score
                best_solution = overlap_nodes.copy()
                improving = True

            overlap_nodes[node] = list_choice

        overlap_nodes = best_solution

    list_a: list[IntermediateNode] = []
    list_b: list[IntermediateNode] = []

    for node, list_choice in best_solution.items():
        if list_choice:
            list_a.append(node)
        else:
            list_b.append(node)

    # list_a.extend(n for n in nodes if n not in list(overlap_nodes.keys()))
    nodes_to_assign = [n for n in nodes if n not in list(overlap_nodes.keys())]
    while nodes_to_assign:
        scores = [
            (node, *calculate_assignment_score(list_a, list_b, node))
            for node in nodes_to_assign
        ]
        max_score = max(max(a, b) for _, a, b in scores)
        node, assign_a = next(
            (node, a == max_score)
            for node, a, b in scores
            if a == max_score or b == max_score
        )
        if assign_a:
            list_a.append(node)
        else:
            list_b.append(node)
        nodes_to_assign.remove(node)

    # if best_score != len(overlaps):
    #     l_a, l_b = node_search_brute_force(nodes, overlaps)
    #     score = 0
    #     for a, b in overlaps:
    #         if (a in l_a) != (b in l_a):
    #             score += 1

    #     if best_score != score:
    #         print(
    #             f"{best_score} / {len(overlaps)} ({round(100*best_score / len(overlaps))}%) max {score} ({round(100*score / len(overlaps))}%)"
    #         )

    return list_a, list_b


# Note: Goemans-Williamso approximation (at least 88% accurate) was also tested
# but it was non-determenistic (due to using randomness) and performed worse than iterative search


def calculate_assignment_score(
    list_a: list[IntermediateNode],
    list_b: list[IntermediateNode],
    input_node: IntermediateNode,
):
    all_properties: dict[FlagName, set[FlagValue]] = {}

    for node_list in (list_a, list_b, [input_node]):
        for node in node_list:
            for flags in node.flags:
                for k, v in flags.items():
                    value_set = all_properties.get(k, None)

                    if value_set is None:
                        value_set: set[FlagValue] = set()
                        all_properties[k] = value_set

                    value_set.add(v)

    target_sig = {k: {f: 0 for f in v} for k, v in all_properties.items()}
    for node_list, sign in ((list_a, 1), (list_b, -1)):
        for node in node_list:
            for flags in node.flags:
                for name, value in flags.items():
                    target_sig[name][value] += sign

    sig_a = {k: v.copy() for k, v in target_sig.items()}
    sig_b = {k: v.copy() for k, v in target_sig.items()}
    for flags in input_node.flags:
        for name, value in flags.items():
            sig_a[name][value] += 1
            sig_b[name][value] -= 1

    func = 2  # 0, 1, 2, 11 are the best. 0, 1, 11 are about the same whereas 2 is somehow different
    score_a = 0
    score_b = 0

    if func == 0:
        # Expanding as vectors and computing dot product
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]
            for value_name, score in values.items():
                score_a += positive_values[value_name] * score
                score_b += negative_values[value_name] * score
    elif func == 1:
        # Computing dot product between each component, then summing together their roots
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]
            local_score_a = 0
            local_score_b = 0
            for value_name, score in values.items():
                local_score_a += positive_values[value_name] * score
                local_score_b += negative_values[value_name] * score
            score_a += sqrt(abs(local_score_a)) * (1 if local_score_a >= 0 else -1)
            score_b += sqrt(abs(local_score_b)) * (1 if local_score_b >= 0 else -1)
    elif func == 2:
        # Computing dot product between each component, then summing together their squares
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]
            local_score_a = 0
            local_score_b = 0
            for value_name, score in values.items():
                local_score_a += positive_values[value_name] * score
                local_score_b += negative_values[value_name] * score
            score_a += (-1 if local_score_a < 0 else 1) * local_score_a**2
            score_b += (-1 if local_score_b < 0 else 1) * local_score_b**2
    elif func == 3:
        # Sum of absolute differences
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]
            for value_name, score in values.items():
                score_a += abs(positive_values[value_name] - score)
                score_b += abs(negative_values[value_name] - score)
        # Swap scores
        score_a, score_b = score_b, score_a
    elif func == 4:
        # Sum of absolute squared differences
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]
            for value_name, score in values.items():
                score_a += abs(positive_values[value_name] - score) ** 2
                score_b += abs(negative_values[value_name] - score) ** 2
        # Swap scores
        score_a, score_b = score_b, score_a
    elif func == 5:
        # Sum of squared local sums of differences
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]
            local_a = 0
            local_b = 0
            for value_name, score in values.items():
                local_a += abs(positive_values[value_name] - score)
                local_b += abs(negative_values[value_name] - score)
            score_a += local_a**2
            score_b += local_b**2
        # Swap scores
        score_a, score_b = score_b, score_a
    elif func == 6:
        # Normalize local vectors, then compute dot product, then sum dot products
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]

            local_vec_ref = list(values.values())
            local_vec_a = list(positive_values.values())
            local_vec_b = list(negative_values.values())

            # Normalize vectors
            d = sqrt(sum(x * x for x in local_vec_ref))
            if d:
                local_vec_ref = [x / d for x in local_vec_ref]

            d = sqrt(sum(x * x for x in local_vec_a))
            if d:
                local_vec_a = [x / d for x in local_vec_a]

            d = sqrt(sum(x * x for x in local_vec_b))
            if d:
                local_vec_b = [x / d for x in local_vec_b]

            dot_a = sum(a * b for a, b in zip(local_vec_ref, local_vec_a))
            dot_b = sum(a * b for a, b in zip(local_vec_ref, local_vec_b))

            score_a += dot_a
            score_b += dot_b
    elif func == 7:
        # Normalize local vectors, then compute dot product, then sum squared dot products
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]

            local_vec_ref = list(values.values())
            local_vec_a = list(positive_values.values())
            local_vec_b = list(negative_values.values())

            # Normalize vectors
            d = sqrt(sum(x * x for x in local_vec_ref))
            if d:
                local_vec_ref = [x / d for x in local_vec_ref]

            d = sqrt(sum(x * x for x in local_vec_a))
            if d:
                local_vec_a = [x / d for x in local_vec_a]

            d = sqrt(sum(x * x for x in local_vec_b))
            if d:
                local_vec_b = [x / d for x in local_vec_b]

            dot_a = sum(a * b for a, b in zip(local_vec_ref, local_vec_a))
            dot_b = sum(a * b for a, b in zip(local_vec_ref, local_vec_b))

            score_a += dot_a**2
            score_b += dot_b**2
    elif func == 8:
        # Normalize local vectors, then compute dot product, then sum sqrt dot products
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]

            local_vec_ref = list(values.values())
            local_vec_a = list(positive_values.values())
            local_vec_b = list(negative_values.values())

            # Normalize vectors
            d = sqrt(sum(x * x for x in local_vec_ref))
            if d:
                local_vec_ref = [x / d for x in local_vec_ref]

            d = sqrt(sum(x * x for x in local_vec_a))
            if d:
                local_vec_a = [x / d for x in local_vec_a]

            d = sqrt(sum(x * x for x in local_vec_b))
            if d:
                local_vec_b = [x / d for x in local_vec_b]

            dot_a = sum(a * b for a, b in zip(local_vec_ref, local_vec_a))
            dot_b = sum(a * b for a, b in zip(local_vec_ref, local_vec_b))

            score_a += sqrt(abs(dot_a)) * (1 if dot_a >= 0 else -1)
            score_b += sqrt(abs(dot_b)) * (1 if dot_b >= 0 else -1)
    elif func == 9:
        # Normalize local vectors, then compute and add absolute difference
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]

            local_vec_ref = list(values.values())
            local_vec_a = list(positive_values.values())
            local_vec_b = list(negative_values.values())

            # Normalize vectors
            d = sqrt(sum(x * x for x in local_vec_ref))
            if d:
                local_vec_ref = [x / d for x in local_vec_ref]

            d = sqrt(sum(x * x for x in local_vec_a))
            if d:
                local_vec_a = [x / d for x in local_vec_a]

            d = sqrt(sum(x * x for x in local_vec_b))
            if d:
                local_vec_b = [x / d for x in local_vec_b]

            score_a += sum(abs(x - y) for x, y in zip(local_vec_ref, local_vec_a))
            score_b += sum(abs(x - y) for x, y in zip(local_vec_ref, local_vec_b))
        # Swap scores
        score_a, score_b = score_b, score_a
    elif func == 10:
        # Normalize local vectors, then compute and add absolute squared differences
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]

            local_vec_ref = list(values.values())
            local_vec_a = list(positive_values.values())
            local_vec_b = list(negative_values.values())

            # Normalize vectors
            d = sqrt(sum(x * x for x in local_vec_ref))
            if d:
                local_vec_ref = [x / d for x in local_vec_ref]

            d = sqrt(sum(x * x for x in local_vec_a))
            if d:
                local_vec_a = [x / d for x in local_vec_a]

            d = sqrt(sum(x * x for x in local_vec_b))
            if d:
                local_vec_b = [x / d for x in local_vec_b]

            score_a += sum(abs(x - y) ** 2 for x, y in zip(local_vec_ref, local_vec_a))
            score_b += sum(abs(x - y) ** 2 for x, y in zip(local_vec_ref, local_vec_b))
        # Swap scores
        score_a, score_b = score_b, score_a
    elif func == 11:
        # Normalize local vectors, then compute and add absolute rooted differences
        for name, values in target_sig.items():
            positive_values = sig_a[name]
            negative_values = sig_b[name]

            local_vec_ref = list(values.values())
            local_vec_a = list(positive_values.values())
            local_vec_b = list(negative_values.values())

            # Normalize vectors
            d = sqrt(sum(x * x for x in local_vec_ref))
            if d:
                local_vec_ref = [x / d for x in local_vec_ref]

            d = sqrt(sum(x * x for x in local_vec_a))
            if d:
                local_vec_a = [x / d for x in local_vec_a]

            d = sqrt(sum(x * x for x in local_vec_b))
            if d:
                local_vec_b = [x / d for x in local_vec_b]

            score_a += sum(sqrt(abs(x - y)) for x, y in zip(local_vec_ref, local_vec_a))
            score_b += sum(sqrt(abs(x - y)) for x, y in zip(local_vec_ref, local_vec_b))
        # Swap scores
        score_a, score_b = score_b, score_a

    return score_a, score_b


class VariableGraph:
    """
    Graph object representing equivalence between variables in code.

    A graph is considered solved when all disconnection constraints between variable nodes are satisfied.
    Once a graph is solved, all variables that are part of the same subgraphs can be safely replaced with a single variable.

    Connection nodes represent lines with competing variables. Connection nodes may be "split" where a new node
    is created and some of the connections from an existing node transfer over to it. This is reflected in code by duplicating
    a line of code and transferring some of its flags into a duplicate line.

    Lines of code with multiple variable references create multiple connection nodes, however nodes
    from the same line are considered to be grouped together and must be split together (as you can't duplicate only part of the line,
    the entire line must be duplicated, including all connection nodes).
    """

    constraints: list[tuple[VariableNode, VariableNode]]
    "Variable node pairs that mustn't have a path in the graph connecting them together"

    variable_mapping: dict[ShaderVariable, VariableNode]
    variable_node_groups: list[list[VariableNode]]

    _shader: ProcessedDiffedShader
    _all_nodes: list[AnyNode]

    def __init__(self, shader: ProcessedDiffedShader):
        self.constraints = []
        self.variable_mapping = {}
        self.variable_node_groups = []
        self._shader = shader
        self._all_nodes = []

    def resolve(self):
        while True:
            new_constraints: list[tuple[VariableNode, VariableNode]] = []
            overlaps: dict[ConnectionNode, list[tuple[VariableNode, VariableNode]]] = {}
            for a, b in self.constraints:
                paths = self.find_shortest_paths(a, b)

                if len(paths) == 0:
                    continue

                new_constraints.append((a, b))
                for path in paths:
                    for node_idx in range(1, len(path), 2):
                        node = path[node_idx]
                        # if not isinstance(node, ConnectionNode):
                        #     continue

                        constraint_list = overlaps.get(node, None)

                        if constraint_list is None:
                            constraint_list = []
                            overlaps[node] = constraint_list

                        constraint_list.append((path[node_idx - 1], path[node_idx + 1]))

            self.constraints = new_constraints
            if len(new_constraints) == 0:
                break

            max_overlap_count = max(len(x) for x in overlaps.values())
            best_node_candidates = (
                k for k, v in overlaps.items() if len(v) == max_overlap_count
            )
            best_node_candidates = [
                (x, x.line_ref.origin_list.index(x.line_ref))
                for x in best_node_candidates
            ]
            best_node_candidates.sort(key=lambda x: x[1])
            best_node_candidates = [x[0] for x in best_node_candidates]

            node_to_split = best_node_candidates[0]
            line = node_to_split.line_ref

            # Disconnect nodes
            for node in node_to_split.nodes_in_group:
                for connection in node.connects:
                    connection.connects.remove(node)

            # Resolve overlaps for all nodes in group, while prioritising the current chosen node
            nodes_in_group = node_to_split.nodes_in_group.copy()
            nodes_in_group.remove(node_to_split)
            nodes_in_group.insert(0, node_to_split)

            node_mapping: dict[frozenset[HashableFlags], IntermediateNode] = {}
            for node in nodes_in_group:
                for var in node.connects:
                    flags = var.variable_ref.permutation_ref.flags
                    hashable_flags = frozenset(make_hashable_flags(f) for f in flags)

                    if hashable_flags not in node_mapping:
                        nd = IntermediateNode()
                        nd.flags = sorted(flags, key=lambda x: str(x))
                        node_mapping[hashable_flags] = nd

            overlaps_to_resolve: list[tuple[IntermediateNode, IntermediateNode]] = []
            for node in nodes_in_group:
                for var1, var2 in overlaps.get(node, []):
                    f1 = frozenset(
                        make_hashable_flags(f)
                        for f in var1.variable_ref.permutation_ref.flags
                    )
                    f2 = frozenset(
                        make_hashable_flags(f)
                        for f in var2.variable_ref.permutation_ref.flags
                    )
                    overlaps_to_resolve.append((node_mapping[f1], node_mapping[f2]))

            # list_a, list_b = node_search_random(
            #     list(node_mapping.values()), overlaps_to_resolve
            # )
            # list_a, list_b = node_search_brute_force(
            #     list(node_mapping.values()), overlaps_to_resolve
            # )
            list_a, list_b = node_search_iterative(
                sorted(node_mapping.values(), key=lambda x: str(x.flags)),
                overlaps_to_resolve,
            )

            connections_a: list[ShaderFlags] = []
            connections_b: list[ShaderFlags] = []

            for node in list_a:
                connections_a.extend(node.flags)

            for node in list_b:
                connections_b.extend(node.flags)

            new_line = ShaderLine()
            new_line.code = line.code
            new_line.origin_list = line.origin_list
            new_line.variables = tuple(x.copy() for x in line.variables)

            if line.group is None:
                line.group = [line]
                self.variable_node_groups.append(line.group)
            line.group.append(new_line)
            new_line.group = line.group

            line.permutation_flags = connections_a
            new_line.permutation_flags = connections_b

            index = line.origin_list.index(line)
            line.origin_list.insert(index + 1, new_line)

            new_group: list[ConnectionNode] = []
            for node in node_to_split.nodes_in_group:
                new_node = ConnectionNode(new_line, node.index)
                new_group.append(new_node)
                self._all_nodes.append(new_node)

                new_node.nodes_in_group = new_group
                new_node.connects = []

                new_connects: list[VariableNode] = []
                for connection in node.connects:
                    flags = connection.variable_ref.permutation_ref.flags

                    if any(f in connections_a for f in flags):
                        new_connects.append(connection)
                    else:
                        new_node.connects.append(connection)

                node.connects = new_connects

            # re-link variable nodes to connection nodes
            for node in new_group:
                for connection in node.connects:
                    connection.connects.append(node)
                node.line_ref.variables[node.index][:] = [
                    n.variable_ref for n in node.connects
                ]

            for node in node_to_split.nodes_in_group:
                for connection in node.connects:
                    connection.connects.append(node)
                node.line_ref.variables[node.index][:] = [
                    n.variable_ref for n in node.connects
                ]

    def apply(self):
        groups = self.discover_related_variables()
        variable_map: dict[ShaderVariable, ShaderVariable] = {}
        for group in groups:
            new_variable_ref = ShaderVariable()

            for variable in group:
                variable_map[variable.variable_ref] = new_variable_ref

        list_of_lines = list(self._shader.function_lines.values())
        list_of_lines.append(self._shader.lines)

        variable_signatures: dict[ShaderVariable, list[str]] = {}

        for lines in list_of_lines:
            for line in lines:
                line.permutation_flags.sort(key=lambda x: str(x))
                # if line.group is not None:
                #     line.code = line.code + "// In group"
                for index, variable_list in enumerate(line.variables):
                    variable = variable_list[0]
                    variable = variable_map[variable]
                    variable_list[:] = [variable]

            new_lines: list[ShaderLine] = []
            line_index = 0
            while line_index < len(lines):
                line = lines[line_index]
                if line.group is not None:
                    unique_lines: dict[
                        tuple[str, tuple[ShaderVariable]], ShaderLine
                    ] = {}
                    for line_in_group in line.group:
                        key = (
                            line_in_group.code,
                            tuple(v[0] for v in line_in_group.variables),
                        )
                        unique_line: ShaderLine = unique_lines.get(key, None)

                        if unique_line is None:
                            unique_lines[key] = line_in_group
                            continue

                        unique_line.permutation_flags.extend(
                            line_in_group.permutation_flags
                        )

                    unique_lines_list: list[ShaderLine] = [
                        l for l in unique_lines.values()
                    ]
                    unique_lines_list.sort(key=lambda x: str(x.permutation_flags))

                    if line_index - 1 >= 0:
                        prev_line_flags = lines[line_index - 1].permutation_flags
                    else:
                        prev_line_flags = []

                    if line_index + len(line.group) < len(lines):
                        next_line_flags = lines[
                            line_index + len(line.group)
                        ].permutation_flags
                    else:
                        next_line_flags = []

                    for unique_line in unique_lines_list.copy():
                        if unique_line.permutation_flags == next_line_flags:
                            unique_lines_list.remove(unique_line)
                            unique_lines_list.append(unique_line)
                        elif unique_line.permutation_flags == prev_line_flags:
                            unique_lines_list.remove(unique_line)
                            unique_lines_list.insert(0, unique_line)

                    new_lines.extend(unique_lines_list)
                    line_index += len(line.group)
                else:
                    new_lines.append(line)
                    line_index += 1

            lines[:] = new_lines

            # Generate signatures
            for line in lines:
                for index, variable_list in enumerate(line.variables):
                    variable = variable_list[0]

                    line_list = variable_signatures.get(variable, None)

                    if line_list is None:
                        line_list = []
                        variable_signatures[variable] = line_list

                    line_list.append(make_variable_signature(line.code, index))

        # Generate names
        hashes: set[str] = set()
        for variable, signature in variable_signatures.items():
            signature = "\n".join(signature)
            hash_obj = hashlib.sha224(signature.encode())
            while True:
                name_hash = hash_obj.hexdigest()[:5]
                if name_hash not in hashes:
                    hashes.add(name_hash)
                    break
                hash_obj.update(b"\nCOLLISION RESOLVING PADDING")

            variable.name = f"var_{name_hash}"

    def discover_related_variables(self):
        all_variables = {
            node for node in self._all_nodes if isinstance(node, VariableNode)
        }
        related_groups: list[list[VariableNode]] = []

        while all_variables:
            variable = next(x for x in all_variables)
            related_variables = self.discover_subgraph(variable)
            all_variables.difference_update(related_variables)
            related_groups.append(list(related_variables))

        return related_groups

    def discover_subgraph(self, variable_node: VariableNode):
        prohibited_nodes: set[AnyNode] = set(variable_node.connects).union(
            {variable_node}
        )
        related_variables: set[VariableNode] = {variable_node}
        nodes_to_visit: list[AnyNode] = variable_node.connects

        while nodes_to_visit:
            new_nodes_to_visit: list[AnyNode] = []
            for node in nodes_to_visit:
                for connection in node.connects:
                    if connection in prohibited_nodes:
                        continue

                    if isinstance(connection, VariableNode):
                        related_variables.add(connection)

                    new_nodes_to_visit.append(connection)
                    prohibited_nodes.add(connection)

            nodes_to_visit = new_nodes_to_visit

        return related_variables

    def find_shortest_paths(
        self, a: VariableNode, b: VariableNode
    ) -> list[list[AnyNode]]:
        queue: set[AnyNode] = {a}
        explored: set[AnyNode] = {a}
        queue_paths: dict[AnyNode, list[list[AnyNode]]] = {a: [[a]]}

        found = False
        while True:
            new_queue: set[AnyNode] = set()
            new_queue_paths: dict[AnyNode, list[list[AnyNode]]] = {}

            for current_node in queue:
                if current_node is b:
                    found = True
                    break

                current_node_paths = queue_paths[current_node]
                if isinstance(current_node, ConnectionNode):
                    equivalent_variables: dict[
                        frozenset[ConnectionNode], list[VariableNode]
                    ] = {}
                    for future_node in current_node.connects:
                        key = frozenset(future_node.connects)
                        var_list = equivalent_variables.get(key, None)
                        if var_list is None:
                            var_list = []
                            equivalent_variables[key] = var_list
                        var_list.append(future_node)

                    filtered_connects: list[VariableNode] = []
                    for var_list in equivalent_variables.values():
                        if b in var_list:
                            filtered_connects.append(b)
                        else:
                            var_list.sort(
                                key=lambda x: str(x.variable_ref.permutation_ref.flags)
                            )
                            filtered_connects.append(var_list[0])
                else:
                    filtered_connects = current_node.connects

                for future_node in filtered_connects:
                    if future_node in explored:
                        continue

                    new_queue.add(future_node)
                    future_node_paths = new_queue_paths.get(future_node, None)

                    if future_node_paths is None:
                        future_node_paths = []
                        new_queue_paths[future_node] = future_node_paths

                    for path in current_node_paths:
                        future_node_paths.append(path + [future_node])

            if found or len(new_queue) == 0:
                break

            explored.update(new_queue)
            queue = new_queue
            queue_paths = new_queue_paths

        if not found:
            return []

        return queue_paths[b]

    def populate(self):
        shader = self._shader

        self.variable_mapping = {}
        self._create_variable_nodes(shader.lines)
        for lines in shader.function_lines.values():
            self._create_variable_nodes(lines)

        self._create_connection_nodes(shader.lines)
        for lines in shader.function_lines.values():
            self._create_connection_nodes(lines)

        self._gen_constraints()

    def _create_connection_nodes(
        self,
        lines: list[ShaderLine],
    ):
        """
        Creates connetion nodes between variable nodes.
        """
        for line in lines:
            # Skip lines with no variables at all or with fully determined variables
            if len(line.variables) == 0 or all(len(v) == 1 for v in line.variables):
                continue

            line_nodes = [
                ConnectionNode(line, idx) for idx in range(len(line.variables))
            ]

            self._all_nodes.extend(line_nodes)

            for connection_node, variable_list in zip(line_nodes, line.variables):
                connection_node.nodes_in_group = line_nodes
                connection_node.connects = [
                    self.variable_mapping[v] for v in variable_list
                ]

                for variable_node in connection_node.connects:
                    variable_node.connects.append(connection_node)

    def _create_variable_nodes(
        self,
        lines: list[ShaderLine],
    ):
        """
        Creates variable nodes from ShaderVariable objects
        """
        for line in lines:
            for variable_list in line.variables:
                for variable in variable_list:
                    if variable not in self.variable_mapping:
                        node = VariableNode(variable)
                        self.variable_mapping[variable] = node
                        self._all_nodes.append(node)

    def _gen_constraints(self):
        """
        Creates disconnection constraints between variable nodes.

        Variables within the same unique permutation mustn't have a path between them in the graph,
        as these variables are distinct and cannot be merged into a single variable.
        """
        self.constraints = []
        groups = self.discover_related_variables()
        for group in groups:
            variable_groups: dict[UniquePermutationRef, set[ShaderVariable]] = {}
            for node in group:
                variable = node.variable_ref
                variable_set = variable_groups.get(variable.permutation_ref, None)

                if variable_set is None:
                    variable_set: set[ShaderVariable] = set()
                    variable_groups[variable.permutation_ref] = variable_set

                variable_set.add(variable)

            for variable_set in variable_groups.values():
                count = len(variable_set)
                if count <= 1:
                    continue

                variable_node_list = [self.variable_mapping[v] for v in variable_set]
                for a_idx in range(count - 1):
                    var_a = variable_node_list[a_idx]
                    for b_idx in range(a_idx + 1, count):
                        var_b = variable_node_list[b_idx]
                        self.constraints.append((var_a, var_b))

    def __del__(self):
        """
        Destructor. Gets rid of circular references and allows python to do proper garbage collection.
        """
        for node in self._all_nodes:
            node.connects.clear()

            if isinstance(node, ConnectionNode):
                node.nodes_in_group.clear()

        for group in self.variable_node_groups:
            group.clear()


def resolve_variables(
    diffed_shader: DiffedShader,
    encoded_shader: EncodedShader,
    variable_definition: VariablesDefinition,
):
    processed_shader = ProcessedDiffedShader()
    processed_shader.populate(diffed_shader, encoded_shader, variable_definition)
    # processed_shader.filter_equivalent_variables()

    graph = VariableGraph(processed_shader)
    graph.populate()
    graph.resolve()
    graph.apply()

    diffed_shader.main_code.line_conditions = []
    diffed_shader.main_code.lines = []
    for line in processed_shader.lines:
        diffed_shader.main_code.line_conditions.append(line.permutation_flags)
        for var_list in line.variables:
            var = var_list[0]
            line.code = line.code.replace("|||VARIABLE|||", var.name, 1)
        diffed_shader.main_code.lines.append(line.code)

    for func_name, func in diffed_shader.functions.items():
        func.line_conditions = []
        func.lines = []
        for line in processed_shader.function_lines[func_name]:
            func.line_conditions.append(line.permutation_flags)
            for var_list in line.variables:
                var = var_list[0]
                line.code = line.code.replace("|||VARIABLE|||", var.name, 1)
            func.lines.append(line.code)

    # return processed_shader
