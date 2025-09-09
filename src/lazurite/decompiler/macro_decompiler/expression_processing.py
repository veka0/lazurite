import sympy
import re

from lazurite import util

from .expression_search import (
    ExpressionSearchToken,
    JoinType,
    ExpressionSearchOutput,
    ExpressionSearchInput,
)


def convert_to_sympy_expression(tokens: list[ExpressionSearchToken]):
    expression: sympy.Symbol = sympy.false

    for token in tokens:
        if token.flag_name == "pass":
            macro = util.generate_pass_name_macro(token.flag_value)
        else:
            # TODO: refactor and/or better document the f_ thing
            if token.flag_name.startswith("f_"):
                flag_name = token.flag_name.removeprefix("f_")
                macro = util.generate_flag_name_macro(flag_name, token.flag_value)
            else:
                macro = util.format_definition_name(token.flag_name + token.flag_value)

        macro: sympy.Symbol = sympy.symbols(macro)

        if token.is_negative:
            macro = ~macro

        if token.join_type is JoinType.Initial:
            expression = macro
        elif token.join_type is JoinType.And:
            expression = expression & macro
        elif token.join_type is JoinType.Or:
            expression = expression | macro

    return expression


def _format_expression(expr: str):
    """
    Formats stringified sympy expression according to GLSL macro format.
    """
    expr = expr.replace("~", "!").replace("|", "||").replace("&", "&&")
    expr = re.sub(r"(\w+)", r"defined(\1)", expr)
    return expr


def process_sympy_expressions(expressions: list[sympy.Symbol]):
    """
    Processes a list of sympy expressions. The following logic is executed:
    - Simplifies sympy expressions
    - Converts simplified expressions into macro condition strings
    - Creates a set of macros that were referenced in simplified expressions
    """
    macros: set[str] = set()
    unique_results: list[str] = []
    unique_expressions = list(set(expressions))

    # Operate on unique expressions, in order to reduce compute workload (simplify_logic compute time grows exponentially)
    for expression in unique_expressions:
        expression = sympy.simplify_logic(expression, force=True)
        macro_condition = str(expression)
        macros.update(str(s) for s in expression.atoms())
        if len(expression.atoms()) == 1:
            # Special case handling of macro expressions with only 1 defined macro
            if macro_condition.startswith("~"):
                macro_condition = "#ifndef " + macro_condition.removeprefix("~")
            else:
                macro_condition = "#ifdef " + macro_condition
        else:
            macro_condition = "#if " + _format_expression(macro_condition)

        unique_results.append(macro_condition)

    return [
        unique_results[unique_expressions.index(expr)] for expr in expressions
    ], macros


def mark_approximated_results(
    macro_conditionals: list[str],
    search_results: list[ExpressionSearchOutput],
    search_inputs: list[ExpressionSearchInput],
):
    """
    This function adds the `// Approximation, matches X cases out of Y` comment to macro conditional expressions
    """
    output: list[str] = []
    for input, result, macro in zip(search_inputs, search_results, macro_conditionals):
        if result.score != len(input.flags):
            macro = f"// Approximation, matches {result.score} cases out of {len(input.flags)}\n{macro}"
        output.append(macro)

    return output
