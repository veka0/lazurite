from dataclasses import dataclass

from .processing import postprocess_shader, preprocess_shader, strip_comments
from .expression_search import ExpressionSearchInput, expression_search
from .local_flag_definition import LocalFlagDeinition
from .type_aliases import ShaderCode, ShaderFlags
from .permutation import ShaderPermutation
from .encoded_shader import EncodedShader
from .expression_processing import (
    convert_to_sympy_expression,
    process_sympy_expressions,
    mark_approximated_results,
)


@dataclass
class InputVariant:
    """
    Decompiler input struct, containing code and flags.
    """

    flags: ShaderFlags
    code: ShaderCode


def restore_code(
    input_variants: list[InputVariant],
    remove_comments=True,
    process_shaders=False,
    search_timeout: float = 10,
) -> tuple[set[str], str]:
    """
    Attempts to restore original shader source, by combining variants while adding missing macros.
    """
    shader_permutations: list[ShaderPermutation] = []
    for variant in input_variants:
        code = variant.code

        if remove_comments:
            code = strip_comments(code)
        if process_shaders:
            code = preprocess_shader(code)

        permutation = ShaderPermutation()
        permutation.flags = variant.flags.copy()
        permutation.code = code
        permutation.extract_functions()

        shader_permutations.append(permutation)

    encoded_shader = EncodedShader(shader_permutations)
    diffed_shader = encoded_shader.diff()
    diffed_grouped_shader = diffed_shader.group_lines()

    local_flag_definition = LocalFlagDeinition.from_diffed_grouped_shader(
        diffed_grouped_shader
    )
    local_flag_definition.filter_and_bias_flags()
    all_flags = diffed_grouped_shader.gen_all_flags_list()

    expr_search_inputs = ExpressionSearchInput.from_diffed_grouped_shader(
        diffed_grouped_shader, local_flag_definition, all_flags
    )
    search_results = expression_search(expr_search_inputs, search_timeout)
    sympy_expressions = [
        convert_to_sympy_expression(res.token_list) for res in search_results
    ]
    macro_conditionals, used_macros = process_sympy_expressions(sympy_expressions)

    macro_conditionals = mark_approximated_results(
        macro_conditionals, search_results, expr_search_inputs
    )

    code = diffed_grouped_shader.assemble_code(
        macro_conditionals, encoded_shader.line_decode_table
    )

    if process_shaders:
        code = postprocess_shader(code)

    return used_macros, code
