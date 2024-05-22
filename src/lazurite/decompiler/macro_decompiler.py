from dataclasses import dataclass
import myers
import sympy
import time
import copy
import io
import re


from lazurite import util


@dataclass
class Variant:
    """
    Decompiler input struct, containing code and flags.
    """

    flags: dict[str, str]
    code: str


class Shader:
    """
    Class, responsible for storing intermediate representations of a shader.
    """

    codes: list[list[int]] | list[str]
    flags: list[set[int]]
    combined_code: list[int]
    line_conditions: list[set[int]]
    chunks: list[tuple[int, int]] | list[tuple[int, int, int]]
    is_struct: bool
    all_flags: set[int]

    def __init__(self) -> None:
        self.codes = []
        self.flags = []
        self.chunks = []
        self.is_struct = False
        self.combined_code = []
        self.line_conditions = []

    def load(
        self,
        variants: list[Variant],
        remove_comments=True,
        preprocess=True,
    ):
        """
        Loads and processes shader variants into codes and flags arrays.
        """
        self.codes = []
        self.flags = []
        for i, variant in enumerate(variants):
            code = variant.code
            if remove_comments:
                code = re.sub(r"//.*\n", "", code)
                code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
                code = re.sub(r"\n\n+", "\n", code)
            if preprocess:
                code = _preprocess_shader(code)
            self.codes.append(code)
            self.flags.append({i})

    def uniquify(self):
        """
        Removes duplicate codes and combines their flags, also creates `all_flags` array with all flags.
        """
        codes: list[str] = []
        flags: list[set[int]] = []
        all_flags = set()
        for index, code in enumerate(self.codes):
            try:
                i = codes.index(code)
            except ValueError:
                i = len(codes)
                codes.append(code)
                flags.append(set())
            flags[i].update(self.flags[index])
            all_flags.update(self.flags[index])
        self.all_flags = all_flags
        self.codes = codes
        self.flags = flags

    def encode(self, line_decode_table: dict[str, int]):
        """
        Encodes shader as an array of line indices, while saving line-index mapping in `line_decode_table`.
        """
        for i, code in enumerate(self.codes):
            lines = code.splitlines()
            encoded_shader = []
            for line in lines:
                line_index = line_decode_table.get(line)
                if line_index is None:
                    line_index = len(line_decode_table)
                    line_decode_table[line] = line_index
                encoded_shader.append(line_index)
            self.codes[i] = encoded_shader

    def diff(self):
        """
        Compute combined diff of all shader variants. Populates `combined_code` and `line_conditions`.
        """
        combined_code: list[int] = []
        line_conditions: list[set[int]] = []
        for i, code in enumerate(self.codes):
            diff = myers.diff(combined_code, code)
            combined_code = []
            new_conditions = []
            current_index = 0
            for op, val in diff:
                combined_code.append(val)
                if op == "i":
                    new_conditions.append(copy.copy(self.flags[i]))
                elif op == "r":
                    new_conditions.append(line_conditions[current_index])
                    current_index += 1
                elif op == "k":
                    condition_set = line_conditions[current_index]
                    condition_set.update(self.flags[i])
                    new_conditions.append(condition_set)
                    current_index += 1

            line_conditions = new_conditions
        self.combined_code = combined_code
        self.line_conditions = line_conditions

    def group_lines(self):
        """
        Groups lines with the same condition into chunks, populates `Shader.chunks` list.
        """
        if not self.line_conditions:
            return

        start = 0
        chunks: list[tuple[int, int]] = []
        end = len(self.line_conditions) - 1
        current_condition = self.line_conditions[0]
        for i, condition in enumerate(self.line_conditions):
            if i == end:
                if current_condition != condition:
                    chunks.append((start, i))
                    chunks.append((i, i + 1))
                else:
                    chunks.append((start, i + 1))
            elif current_condition != condition:
                chunks.append((start, i))
                start = i
                current_condition = condition
        self.chunks = chunks

    def generate_calc_list(self, calc_list: list[tuple[set[int], set[int]]]):
        """
        Populates `calc_list` with unique calculations that need to be performed, adds calculation index to each chunk.
        """
        for index, (start, end) in enumerate(self.chunks):
            condition = self.line_conditions[start]
            found = False
            try:
                calc_index = calc_list.index((self.all_flags, condition))
            except ValueError:
                calc_index = len(calc_list)
            else:
                found = True

            if len(condition) == len(self.all_flags):
                calc_index = -1  # This line is always unconditionally present.
            elif not found:
                calc_list.append((self.all_flags, condition))

            self.chunks[index] = (start, end, calc_index)

    def assemble_code(self, calc_final, line_decode_table):
        """
        Creates a final code string with macros.
        """
        string_pipe = io.StringIO()
        for start, end, calc in self.chunks:
            has_condition = calc != -1

            if has_condition:
                string_pipe.write(calc_final[calc] + "\n")

            for i in range(start, end):
                string_pipe.write(line_decode_table[self.combined_code[i]] + "\n")

            if has_condition:
                string_pipe.write("#endif\n")
        string_pipe.seek(0)
        return string_pipe.read()


def _extract_functions(
    code: str, functions: dict[str, tuple[bool, Shader]], flags: set[int]
):
    """
    Extracts functions and structs from shader, storing them as separate individual shaders and replacing them in main shader.
    """
    re_func_start = re.compile(
        r"^[\s]*?([^#\s][\w]+)[\s]+([\w]+)[\s]*\(([^;]*?)\)[\s]*{",
        re.DOTALL | re.MULTILINE,
    )
    func_start = re.search(re_func_start, code)
    modified_text = ""

    # Extract functions.
    while func_start:
        groups = func_start.groups()
        args = groups[2].replace("\n", "")
        name = f"{groups[0]} {groups[1]}({args})"

        modified_text += code[: func_start.start()]

        bracket_balance = 1
        for i in range(func_start.end(), len(code)):
            c = code[i]
            if c == "{":
                bracket_balance += 1
            elif c == "}":
                bracket_balance -= 1

            if not bracket_balance:
                content = code[func_start.end() : i]
                code = code[i + 1 :]
                break
        if bracket_balance:
            break

        func = functions.get(name)

        if not func:
            func = Shader()
            functions[name] = func

        modified_text += f"START_NAME|||{name}|||END_NAME\n"

        func.codes.append(content)
        func.flags.append(copy.copy(flags))

        func_start = re.search(re_func_start, code)

    code = modified_text + code

    # Extract structs.
    match: re.Match
    for match in re.finditer(
        r"^[\s]*?struct[\s]+([\w]+)[\s]*{(.*?)};", code, re.DOTALL | re.MULTILINE
    ):
        name, contents = match.groups()
        name = "struct " + name

        struct = functions.get(name)
        if not struct:
            struct = Shader()
            struct.is_struct = True
            functions[name] = struct

        struct.codes.append(contents)
        struct.flags.append(copy.copy(flags))

        code = code.replace(match.group(), f"START_NAME|||{name}|||END_NAME\n")

    return code


def _evaluate_condition(condition: list[set[bool, bool, int, int]], flag: list[int]):
    value = False
    for c in condition:
        a = flag[c[2]] == c[3]
        if c[0]:
            a = not a
        if c[1]:
            value = value and a
        else:
            value = value or a

    return value


def _calculate_condition_score(
    expr: list[set[bool, bool, int, int]],
    conditions: tuple[set[int], set[int]],
    flags: list[list[int]],
):
    score = 0
    for flag in conditions[0]:
        goal = flag in conditions[1]

        score += 1 if goal == _evaluate_condition(expr, flags[flag]) else -1

    return score


def _increment_expr(expr: list[list[bool, bool, int, int]], flag_def: list[int]):
    for i, val in enumerate(expr):
        if not val[1] and i:
            val[1] = True
            return
        val[1] = False

        if val[3] + 1 < flag_def[val[2]]:
            val[3] += 1
            return
        val[3] = 0

        if not val[0]:
            val[0] = True
            return
        val[0] = False

        if val[2] + 1 < len(flag_def):
            val[2] += 1
            return
        val[2] = 0

    expr.append([False, False, 0, 0])


def _slow_search(
    conditions: tuple[set[int], set[int]],
    flags: list[list[int]],
    flag_def: list[int],
    timeout: float = 10,
):
    """
    Slow brute-force search that scores all possible expression combinations.
    """
    # (bool NOT, bool AND/OR, flag_index, flag_value)

    expression = [[False, False, 0, 0]]
    best_score = -10000
    best_expr = []

    t = time.perf_counter()
    while len(expression) <= len(flag_def) + 5:
        score = _calculate_condition_score(expression, conditions, flags)

        if score > best_score:
            best_score = score
            best_expr = copy.deepcopy(expression)

        if score == len(conditions[0]):
            return True, expression, score

        _increment_expr(expression, flag_def)

        if time.perf_counter() - t > timeout:
            break

    return False, best_expr, best_score


def _fast_search(
    conditions: tuple[set[int], set[int]], flags: list[list[int]], flag_def: list[int]
) -> tuple[bool, list, int]:
    """
    Fast search that calculates best score for each new token.
    """
    # (bool NOT, bool AND/OR, flag_index, flag_value)

    best = -10000
    best_expr = []
    local_best_expr = []
    expression = []
    for _ in range(len(flag_def) + 5):
        expression = copy.deepcopy(local_best_expr)
        expression.append([False, False, 0, 0])

        local_best = -10000
        local_best_expr = []

        for i in range(4):
            if len(expression) == 1 and i >= 2:
                break
            expression[-1][0] = i % 2 == 1
            expression[-1][1] = i / 2 >= 1
            for flag_index, flag in enumerate(flag_def):
                expression[-1][2] = flag_index
                for value in range(flag):
                    expression[-1][3] = value

                    score = _calculate_condition_score(expression, conditions, flags)
                    if score > local_best:
                        local_best = score
                        local_best_expr = copy.deepcopy(expression)

        if local_best > best:
            best = local_best
            best_expr = copy.deepcopy(local_best_expr)
            if best == len(conditions[0]):
                return True, best_expr, best
    return False, best_expr, best


def _convert_to_sympy_expression(
    expression: list[set[bool, bool, int, int]],
    inverse_flag_def: list[tuple[str, list[str]]],
):
    expr = sympy.false
    for e in expression:
        flag, values = inverse_flag_def[e[2]]
        value = values[e[3]]
        is_pass = flag == "pass"
        if is_pass:
            flag = util.generate_pass_name_macro(value)
        else:
            is_bool = False
            # is_bool = set(values) in [
            #     {"On", "Off"},
            #     {"Enabled", "Disabled"},
            # ]
            if flag.startswith("f_"):
                flag = flag.removeprefix("f_")
                flag = util.generate_flag_name_macro(flag, value, is_bool)
            else:
                flag = util.format_definition_name(flag + value)

        a = sympy.symbols(flag)

        # if not is_pass and is_bool and value in {"Off", "Disabled"}:
        #     a = ~a

        if e[0]:
            a = ~a
        if e[1]:
            expr = expr & a
        else:
            expr = expr | a

    return expr


def _format_expression(expr: str):
    """
    Formats stringified sympy expression according to GLSL macro format.
    """
    expr = expr.replace("~", "!").replace("|", "||").replace("&", "&&")
    expr = re.sub(r"(\w+)", r"defined(\1)", expr)
    return expr


def _convert_from_dict_to_list(line_decode_table: dict[str, int]):
    l = [""] * len(line_decode_table)
    for line, i in line_decode_table.items():
        l[i] = line
    return l


def restore_code(
    variants: list[Variant],
    remove_comments=True,
    process_shaders=False,
    search_timeout: float = 10,
) -> tuple[set[str], str]:
    """
    Attempts to restore original shader source, by combining variants while adding missing macros.
    """
    main_shader = Shader()
    main_shader.load(variants, remove_comments, process_shaders)
    main_shader.uniquify()

    functions: dict[str, Shader] = {}
    for i, (code, flags) in enumerate(zip(main_shader.codes, main_shader.flags)):
        main_shader.codes[i] = _extract_functions(code, functions, flags)

    for _, func in functions.items():
        func.uniquify()

    code_flag_list = [copy.copy(v.flags) for v in variants]

    line_decode_table = {}
    main_shader.encode(line_decode_table)

    for _, func in functions.items():
        func.encode(line_decode_table)

    line_decode_table = _convert_from_dict_to_list(line_decode_table)

    # { name: (index, [values]) }
    flag_definition: dict[str, tuple[int, list[str]]] = {}
    for variant in variants:
        for name, value in variant.flags.items():
            definition = flag_definition.get(name)
            if definition is None:
                flag_definition[name] = (len(flag_definition), [value])
            else:
                value_list = definition[1]
                if value not in value_list:
                    value_list.append(value)

    keys_to_remove = []
    for name, (_, value_list) in flag_definition.items():
        # Remove flags with a single value.
        if len(value_list) <= 1:
            keys_to_remove.append(name)
        # Bias against disabling
        for i in {"Off", "Disabled"}:
            if i in value_list:
                value_list.remove(i)
                value_list.append(i)
        # Bias towards enabling
        for i in {"On", "Enabled"}:
            if i in value_list:
                value_list.remove(i)
                value_list.insert(0, i)
    for key in keys_to_remove:
        flag_definition.pop(key)
    for flags in code_flag_list:
        for key in keys_to_remove:
            flags.pop(key)

    # Re-populate flag indices.
    for index, (flag, (_, values)) in enumerate(flag_definition.items()):
        flag_definition[flag] = (index, values)

    main_shader.diff()
    main_shader.group_lines()

    for _, func in functions.items():
        func.diff()
        func.group_lines()

    calc_list: list[tuple[set[int], set[int]]] = []
    main_shader.generate_calc_list(calc_list)
    for _, func in functions.items():
        func.generate_calc_list(calc_list)

    encoded_flags: list[list[int]] = []
    for flags in code_flag_list:
        encoded_flag = [-1] * len(flag_definition)
        for name, value in flags.items():
            name_index, value_list = flag_definition[name]
            encoded_flag[name_index] = value_list.index(value)
        encoded_flags.append(encoded_flag)

    encoded_flag_def = [0] * len(flag_definition)
    for _, (index, values) in flag_definition.items():
        encoded_flag_def[index] = len(values)

    inverse_flag_def: list[tuple[str, list[str]]] = [0] * len(flag_definition)
    for flag, (index, values) in flag_definition.items():
        inverse_flag_def[index] = (flag, values)

    macro_pattern = re.compile(r"\w+")
    macro_set = set()
    calc_result = []
    calc_result_formatted = []
    calc_final = []
    for i, calc in enumerate(calc_list):
        success, expr, score = _fast_search(calc, encoded_flags, encoded_flag_def)
        if not success:
            print("slow search")
            success, expr_slow, score_slow = _slow_search(
                calc, encoded_flags, encoded_flag_def, search_timeout
            )
            if not success:
                print("not found")
            if success or score_slow > score:
                expr = expr_slow
                score = score_slow

        result = _convert_to_sympy_expression(expr, inverse_flag_def)
        try:
            index = calc_result.index(result)
        except ValueError:
            index = len(calc_result)
            calc_result.append(result)
            result = sympy.simplify_logic(result, force=True)
            str_result = str(result)
            macro_set.update(set(re.findall(macro_pattern, str_result)))
            if len(result.atoms()) == 1:
                if str_result.startswith("~"):
                    str_result = "#ifndef " + str_result.removeprefix("~")
                else:
                    str_result = "#ifdef " + str_result
            else:
                str_result = "#if " + _format_expression(str_result)
            if not success:
                str_result = f"// Approximation, matches {score} cases out of {len(calc[0])}\n{str_result}"

            calc_result_formatted.append(str_result)

        calc_final.append(calc_result_formatted[index])

    main_code = main_shader.assemble_code(calc_final, line_decode_table)

    for name, func in functions.items():
        code = func.assemble_code(calc_final, line_decode_table)
        if not code.startswith("\n"):
            code = "\n" + code

        main_code = main_code.replace(
            f"START_NAME|||{name}|||END_NAME",
            f"{name} {{{code}}}" + (";" if func.is_struct else ""),
        )

    if process_shaders:
        main_code = _postprocess_shader(main_code)

    return macro_set, main_code


def _preprocess_shader(shader: str):
    """
    Pre-processes plain text shader code to convert it from GLSL to BGFX SC.\n
    Removes built-in `u_` uniforms, replaces `gl_FragColor` and `gl_FragData`,
    replaces attributes and varyings with `$input` and `$output`, removes macros,
    replaces samplers with BGFX AUTOREG macros, adds NUM_THREADS to compute shaders.
    """
    shader = re.sub(r"^uniform\s+\w+\s+u_[\w[\]]+;\n", "", shader, flags=re.MULTILINE)

    shader = re.sub(r"(\W)bgfx_FragColor(\W)", r"\1gl_FragColor\2", shader)
    shader = re.sub(r"(\W)bgfx_FragData(\W)", r"\1gl_FragData\2", shader)

    shader = re.sub(r"^out\s.+?;\n", "", shader, flags=re.MULTILINE)

    is_vertex_stage = bool(
        re.search(r"^#define varying out$", shader, flags=re.MULTILINE)
    )

    shader = re.sub(r"^#define\s.+?\n", "", shader, flags=re.MULTILINE)
    shader = re.sub(r"^#if\s.+?#endif\n", "", shader, flags=re.MULTILINE | re.DOTALL)
    shader = re.sub(r"^#extension\s.+?\n", "", shader, flags=re.MULTILINE)

    shader = re.sub(
        r"^[\s\w]*?varying\s.+? (\w+);$",
        r"$output \1" if is_vertex_stage else r"$input \1",
        shader,
        flags=re.MULTILINE,
    )
    shader = re.sub(
        r"^[\s\w]*?attribute\s.+? (\w+);$", r"$input \1", shader, flags=re.MULTILINE
    )

    shader = re.sub(r"^#version\s.+?\n", "", shader)

    samplers = [
        (r"lowp sampler2D", r"SAMPLER2D"),
        (r"highp sampler2DMS", r"SAMPLER2DMS"),
        (r"highp sampler3D", r"SAMPLER3D"),
        (r"lowp samplerCube", r"SAMPLERCUBE"),
        (r"highp sampler2DShadow", r"SAMPLER2DSHADOW"),
        (r"highp sampler2D", r"SAMPLER2D_HIGHP"),
        (r"highp samplerCube", r"SAMPLERCUBE_HIGHP"),
        (r"highp sampler2DArray", r"SAMPLER2DARRAY"),
        (r"highp sampler2DMSArray", r"SAMPLER2DMSARRAY"),
        (r"highp samplerCubeArray", r"SAMPLERCUBEARRAY"),
        (r"highp sampler2DArrayShadow", r"SAMPLER2DARRAYSHADOW"),
        (r"highp isampler2D", r"ISAMPLER2D"),
        (r"highp usampler2D", r"USAMPLER2D"),
        (r"highp isampler3D", r"ISAMPLER3D"),
    ]

    for pattern, repl in samplers:
        pattern = r"^uniform " + pattern + r" (\w+);"
        repl = repl + r"_AUTOREG(\1);"
        shader = shader = re.sub(pattern, repl, shader, flags=re.MULTILINE)

    shader = shader = re.sub(
        r"^layout\(std430, .+?\) readonly buffer (\w+) { (\w+) .+? }",
        r"BUFFER_RO_AUTOREG(\1, \2);",
        shader,
        flags=re.MULTILINE,
    )
    shader = shader = re.sub(
        r"^layout\(std430, .+?\) writeonly buffer (\w+) { (\w+) .+? }",
        r"BUFFER_WR_AUTOREG(\1, \2);",
        shader,
        flags=re.MULTILINE,
    )
    shader = shader = re.sub(
        r"^layout\(std430, .+?\) buffer (\w+) { (\w+) .+? }",
        r"BUFFER_RW_AUTOREG(\1, \2)",
        shader,
        flags=re.MULTILINE,
    )

    for i, access in enumerate(("readonly ", "writeonly ", "")):
        for prefix in "iu":
            prefix = "u" if prefix == "u" else ""
            access_id = ("RO", "WR", "RW")[i]

            name = f"{prefix.upper()}IMAGE2D_{access_id}_AUTOREG"
            shader = re.sub(
                r"^layout\((.+?), .+?\) "
                + access
                + "uniform highp "
                + prefix
                + r"image2D (\w+)",
                name + r"(\2, \1)",
                shader,
                flags=re.MULTILINE,
            )

            name = f"{prefix.upper()}IMAGE2D_ARRAY_{access_id}_AUTOREG"
            shader = re.sub(
                r"^layout\((.+?), .+?\) "
                + access
                + "uniform highp "
                + prefix
                + r"image2DArray (\w+)",
                name + r"(\2, \1)",
                shader,
                flags=re.MULTILINE,
            )

            name = f"{prefix.upper()}IMAGE3D_{access_id}_AUTOREG"
            shader = re.sub(
                r"^layout\((.+?), .+?\) "
                + access
                + "uniform highp "
                + prefix
                + r"image3D (\w+)",
                name + r"(\2, \1)",
                shader,
                flags=re.MULTILINE,
            )

    shader = re.sub(
        r"^layout \(local_size_x = (\d+), local_size_y = (\d+), local_size_z = (\d+)\) in;",
        r"NUM_THREADS(\1, \2, \3)",
        shader,
        flags=re.MULTILINE,
    )

    return shader


def _postprocess_shader(shader: str):
    """
    Post-processes plain text shader code to convert it from GLSL to BGFX SC.\n
    Merges `$input` and `$output` declarations together and adds `// Attention!`
    comment to potential array access and matrix multiplication operations.
    """
    shader = shader.splitlines(keepends=True)

    new_shader = []
    args = []
    line_type = 0  # 0 - none, 1 - input, 2 = output
    line_prefix = ""
    for line in shader:
        if line.startswith("$input "):
            current_line_type = 1
            line_prefix = "$input "
        elif line.startswith("$output "):
            current_line_type = 2
            line_prefix = "$output "
        else:
            current_line_type = 0

        if line_type:
            if line_type == current_line_type:
                args.append(line.removeprefix(line_prefix).removesuffix("\n"))
            else:
                new_shader.append(", ".join(args) + "\n")
        if not line_type or line_type != current_line_type:
            if current_line_type:
                args = [line.removesuffix("\n")]
            else:
                new_shader.append(line)

        line_type = current_line_type
    shader = new_shader

    for i, line in enumerate(shader):
        if ") * (" in line or "][" in line:
            line = line[:-1] + " // Attention!\n"
            shader[i] = line

    shader = "".join(shader)

    return shader
