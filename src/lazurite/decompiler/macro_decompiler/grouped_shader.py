from .processing import format_function_name
from .type_aliases import ShaderLineIndex, ShaderFlags, FunctionName
from .all_flags import AllFlags


class CodeLineGroup:
    """
    A group of consecutive lines of code that share the same condition (appear when the same flags are set)
    """

    lines: list[ShaderLineIndex]
    condition: list[ShaderFlags]
    expression_search_index: int | None

    def __init__(self):
        self.lines = []
        self.condition = []
        self.expression_search_index = None

    def assemble(self, line_decode_table: list[str], macro_expressions: list[str]):
        code = "\n".join(line_decode_table[i] for i in self.lines)
        if self.expression_search_index is not None:
            code = f"{macro_expressions[self.expression_search_index]}\n{code}\n#endif"
        return code


class DiffedShaderWithGroupedLines:
    main_code: list[CodeLineGroup]
    functions: dict[FunctionName, list[CodeLineGroup]]

    def __init__(self):
        self.main_code = []
        self.functions = {}

    def gen_all_flags_list(self):
        """
        Generates a list of all flags, per context (main code or individual functions)
        """
        all_flags = AllFlags()

        all_flags.main_flags = self._gen_flag_list_from_line_groups(self.main_code)

        for function_name, function_line_groups in self.functions.items():
            all_flags.function_flags[function_name] = (
                self._gen_flag_list_from_line_groups(function_line_groups)
            )

        return all_flags

    @staticmethod
    def _gen_flag_list_from_line_groups(code_line_groups: list[CodeLineGroup]):
        flag_list: list[ShaderFlags] = []
        for line_group in code_line_groups:
            for flags in line_group.condition:
                if flags not in flag_list:
                    flag_list.append(flags)

        return flag_list

    def assemble_code(
        self,
        macro_expressions: list[str],
        line_decode_table: list[str],
    ):
        """
        Assembles shader back into its source code form
        """
        shader_code = self.assemble_line_groups(
            self.main_code, line_decode_table, macro_expressions
        )

        for func_name, func_body in self.functions.items():
            func_body = self.assemble_line_groups(
                func_body, line_decode_table, macro_expressions
            )
            if not func_body.startswith("\n"):
                func_body = "\n" + func_body

            if not func_body.endswith("\n"):
                func_body = func_body + "\n"

            is_struct = func_name.startswith("struct ")
            shader_code = shader_code.replace(
                format_function_name(func_name),
                f"{func_name} {{{func_body}}}" + (";" if is_struct else ""),
            )

        return shader_code

    @staticmethod
    def assemble_line_groups(
        code: list[CodeLineGroup],
        line_decode_table: list[str],
        macro_expressions: list[str],
    ):
        return "\n".join(
            group.assemble(line_decode_table, macro_expressions) for group in code
        )
