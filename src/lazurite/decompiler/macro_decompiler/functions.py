import re, hashlib, math


from .shared_patterns import VARIABLE_NAME_PATTERN, FUNCTION_NAME_PATTERN
from .type_aliases import FunctionName

FunctionBody = str
FunctionArguments = str

IsGlobal = bool
VariableBeginIndex = int
VariableType = str
VariableDefinition = dict[str, tuple[VariableType, VariableBeginIndex, IsGlobal]]

FunctionDefinition = dict[FunctionName, tuple[FunctionArguments, FunctionBody]]


def _generate_function_name(
    func_body: str,
    arguments: str,
    variable_definition: VariableDefinition,
    function_table: FunctionDefinition,
):
    replaced_variables: set[str] = set()
    original_func_body = func_body
    for match in re.finditer(VARIABLE_NAME_PATTERN, func_body):
        var_name = match.group()
        if var_name in replaced_variables:
            continue
        replaced_variables.add(var_name)

        var_type, _, _ = variable_definition[var_name]

        func_body = re.sub(rf"(?<!\w){var_name}(?!\w)", f"|||{var_type}|||", func_body)

    func_body = re.sub(FUNCTION_NAME_PATTERN, "|||FUNCTION CALL|||", func_body)

    hash_obj = hashlib.sha224((arguments + func_body).encode())
    while True:
        func_name = f"func_{hash_obj.hexdigest()[:5]}"
        if func_name not in function_table or function_table[func_name] == (
            arguments,
            original_func_body,
        ):
            break
        hash_obj.update(b"\nCOLLISION RESOLVING PADDING")

    return func_name


def _resolve_function_variables(
    func_body: str, variable_definition: VariableDefinition, func_start_index: int
):
    new_func_body = func_body
    arguments: list[str] = []
    argument_values: list[str] = []
    replaced_variables: set[str] = set()
    occupied_variable_names: set[str] = set()

    func_lines = re.sub(
        FUNCTION_NAME_PATTERN, "|||FUNCTION CALL|||", func_body
    ).splitlines()

    for match in re.finditer(VARIABLE_NAME_PATTERN, func_body):
        var_name = match.group()
        if var_name in replaced_variables:
            continue
        replaced_variables.add(var_name)

        var_type, var_begin_index, is_global = variable_definition[var_name]

        if is_global:
            continue

        var_name_pattern = re.compile(rf"(?<!\w){var_name}(?!\w)")
        var_signature: list[str] = []
        for line in func_lines:
            replaced_line = re.sub(var_name_pattern, "|||THIS|||", line)

            if replaced_line == line:
                continue

            replaced_line = re.sub(VARIABLE_NAME_PATTERN, "|||OTHER|||", replaced_line)
            var_signature.append(replaced_line)

        hash_obj = hashlib.sha224("\n".join(var_signature).encode())
        while True:
            hash_var_name = hash_obj.hexdigest()[:5]
            if hash_var_name not in occupied_variable_names:
                break
            hash_obj.update(b"\nCOLLISION RESOLVING PADDING")
        occupied_variable_names.add(hash_var_name)

        is_local = func_start_index < var_begin_index
        if is_local:
            new_func_body = re.sub(
                var_name_pattern, f"loc_{hash_var_name}", new_func_body
            )
        else:
            new_func_body = re.sub(
                var_name_pattern, f"arg_{hash_var_name}", new_func_body
            )
            arguments.append(f"inout {var_type} arg_{hash_var_name}")
            argument_values.append(var_name)

    return new_func_body, arguments, argument_values


def _find_closing_bracket(text: str, brackets: str, start_pos=0, balance=1):
    OPENING_BRACKET = brackets[0]
    CLOSING_BRACKET = brackets[1]

    for i in range(start_pos, len(text)):
        char = text[i]

        if char == OPENING_BRACKET:
            balance += 1
        elif char == CLOSING_BRACKET:
            balance -= 1

        if balance == 0:
            return True, i

    return False, len(text)


def _format_function_body(func_body: str):
    match = re.search(r"( *)\w", func_body, re.MULTILINE)
    if match is not None:
        ident = len(match.group(1))
        if ident > 4:
            func_body = re.sub(
                "^" + (ident - 4) * " ", "", func_body, flags=re.MULTILINE
            )
    func_body = re.sub(r"^\s*", "", func_body)
    func_body = re.sub(r"\s*$", "", func_body)
    func_body = 4 * " " + func_body

    # Get rid of trailing break/return
    func_body = re.sub(r"\s*\Wbreak;$", "", func_body, 1)

    # Replace break with return
    BREAK_PATTERN = re.compile(r"(?<!\w)break(?!\w)")
    FOR_PATTERN = re.compile(r"(?<!\w)for\s*\(")
    WHILE_PATTERN = re.compile(r"(?<!\w)while\s*\(")
    DO_PATTERN = re.compile(r"(?<!\w)do(?!\w)")
    SWITCH_PATTERN = re.compile(r"(?<!\w)switch\s*\(")
    SCOPE_BLOCK_PATTERN = re.compile(r"^\s*{")

    PATTERNS = [FOR_PATTERN, WHILE_PATTERN, DO_PATTERN, SWITCH_PATTERN]

    new_func_body = ""

    while True:
        break_match = re.search(BREAK_PATTERN, func_body)

        if break_match is None:
            break

        closest_match = break_match

        for pattern in PATTERNS:
            match = re.search(pattern, func_body)
            if match is None:
                continue
            if match.start() < closest_match.start():
                closest_match = match

        if closest_match is break_match:
            new_func_body += func_body[: closest_match.start()] + "return"
            func_body = func_body[closest_match.end() :]
        elif closest_match.re in (FOR_PATTERN, WHILE_PATTERN, SWITCH_PATTERN):
            _, index = _find_closing_bracket(func_body, "()", closest_match.end())
            new_func_body += func_body[: index + 1]
            func_body = func_body[index + 1 :]

            scope_match = re.match(SCOPE_BLOCK_PATTERN, func_body)

            if scope_match is None:
                index = func_body.find(";")
            else:
                _, index = _find_closing_bracket(func_body, "{}", scope_match.end())
            new_func_body += func_body[: index + 1]
            func_body = func_body[index + 1 :]
        elif closest_match.re is DO_PATTERN:
            scope_match = re.match(SCOPE_BLOCK_PATTERN, func_body)

            if scope_match is None:
                index = func_body.find(";")
            else:
                _, index = _find_closing_bracket(func_body, "{}", scope_match.end())
            new_func_body += func_body[: index + 1]
            func_body = func_body[index + 1 :]

    return new_func_body + func_body


# test = """
#     for (aga;g;ag) break;
#     for (arg;ag;af;g) {ag ag break; agag}
#     for (gfg;aga;afg);

#     while (aga) break;
#     while (argdg) {ag ag break; agag}
#     while (gfgagg);

#     do break; while (aga) break;
#     do {ag ag break; agag}; while (argdg);
#     do; while (gfgagg);

#     switch(gagaga) {gagag break;}

#     if (agga) {
#     break;
#     }
#     break;

# """
# # test = " for (aga;g;ag) break; "

# print(_format_function_body(test))
# exit()

# Cases:
# for (...) break;
# for (...) { ... break; }
# do break; while(...);
# do { ... break; }
# while(...) break;
# while(...) { ... break; }
# switch(...) {... break; }


def _emit_functions(
    code: str,
    original_code: str,
    function_table: FunctionDefinition,
    variable_definition: VariableDefinition,
    start_index: int = 0,
) -> str:
    function_pattern = re.compile(r"\Wdo\s*{", re.MULTILINE)
    while_pattern = re.compile(r"\s*while\s*\(false\);", re.MULTILINE)

    new_code = ""

    while True:
        match = re.search(function_pattern, code)
        if match is None:
            break

        found, index = _find_closing_bracket(code, "{}", match.end())

        if not found:
            break

        while_match = re.search(while_pattern, code[index + 1 :])
        if while_match is None:
            new_code += code[: index + 1]
            code = code[index + 1 :]
            start_index += index + 1
        else:
            func_start_index = start_index + match.end()
            func_body = code[match.end() : index - 1]
            func_body = _emit_functions(
                func_body,
                original_code,
                function_table,
                variable_definition,
                func_start_index,
            )
            func_body = _format_function_body(func_body)
            func_body, arguments, argument_values = _resolve_function_variables(
                func_body, variable_definition, func_start_index
            )
            arguments = ", ".join(arguments)

            func_name = _generate_function_name(
                func_body, arguments, variable_definition, function_table
            )

            if func_name not in function_table:
                function_table[func_name] = (arguments, func_body)
                # print(func_name + parameters + "\n" + func_body)

            new_code += (
                code[: match.start() + 1]
                + f"{func_name}({', '.join(argument_values)});"
            )
            code = code[index + 1 + while_match.end() :]
            start_index += index + 1 + while_match.end()

            # print(f"{func_name}({arguments}) {{")
            # print(func_body)
            # print("}")

    return new_code + code


def _extract_variable_definition(code: str):
    variable_definitions: VariableDefinition = {}
    reversed_code = code[::-1]
    main_start_index = code.find("void main()")

    type_pattern = re.compile(r"\w+\s+(\w+[\s\w]*)", re.MULTILINE | re.DOTALL)
    empty_space_pattern = re.compile(r"^\s*(.+)$", re.MULTILINE | re.DOTALL)
    space_replace_pattern = re.compile(r"\s\s+", re.MULTILINE)

    for variable_match in re.finditer(VARIABLE_NAME_PATTERN, code):
        variable_name = variable_match.group()
        if variable_name in variable_definitions:
            continue

        reversed_index = len(code) - variable_match.end()
        truncated_reversed_code = reversed_code[reversed_index:]

        bracket_index = truncated_reversed_code.find("}")

        while True:
            variable_type_match = re.search(type_pattern, truncated_reversed_code)
            if bracket_index != -1 and variable_type_match.start() > bracket_index:
                bracket_balance = -1
                for i in range(bracket_index + 1, len(truncated_reversed_code)):
                    char = truncated_reversed_code[i]
                    if char == "{":
                        bracket_balance += 1
                    elif char == "}":
                        bracket_balance -= 1

                    if bracket_balance == 0:
                        truncated_reversed_code = (
                            truncated_reversed_code[:bracket_index]
                            + truncated_reversed_code[i + 1 :]
                        )
                        break

                bracket_index = truncated_reversed_code.find("}")
            else:
                break
        variable_type = variable_type_match.group(1)[::-1]
        variable_type = re.match(empty_space_pattern, variable_type).group(1)
        variable_type = re.sub(space_replace_pattern, " ", variable_type)
        variable_definitions[variable_name] = (
            variable_type,
            variable_match.start(),
            variable_match.start() < main_start_index,
        )

    return variable_definitions


def emit_functions(code: str):
    # Extract variable definition

    variable_definitions = _extract_variable_definition(code)

    # Look for functions

    # {name: (function parameters, function body)}
    function_table: FunctionDefinition = {}
    code = _emit_functions(code, code, function_table, variable_definitions)

    all_function_code = ""
    for name, (arguments, body) in function_table.items():
        all_function_code += f"void {name}({arguments}) {{\n{body}\n}}\n"

    main_start_index = code.find("void main()")
    code = code[:main_start_index] + all_function_code + code[main_start_index:]
    return code

    # Resolve sub-functions first
    # Then analyze current function
    # - resolve arguments vs local variables, by checking function variable types in function body
    # - rename arguments to arg_0 and local variables to var_0, leave global variables as is
    # - all arguments are inout, for now
    # - Generate function name by hashing function body, while replacing global variables with their type. If there is conflict with existing function, change function name
    # - If function already exists, use existing definition (need to fully resolve first and compare function body)
    # Paste all functions before void main()
