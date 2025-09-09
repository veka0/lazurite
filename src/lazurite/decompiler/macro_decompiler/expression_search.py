import time
from enum import Enum, auto
from copy import copy

from .type_aliases import ShaderFlags, FlagDefinition, FlagName, FlagValue
from .grouped_shader import DiffedShaderWithGroupedLines, CodeLineGroup
from .local_flag_definition import LocalFlagDeinition
from .all_flags import AllFlags

FlagsOutcome = bool
"Determines whether expression should be true for a given set of flags"


class ExpressionSearchInput:
    """
    Input object for expression search algorithms
    """

    flags: list[tuple[FlagsOutcome, ShaderFlags]]
    flag_definition: FlagDefinition

    def __init__(self):
        self.flags = []
        self.flag_definition = {}

    def __eq__(self, value):
        if not isinstance(value, type(self)):
            return False
        return (
            self.flags == value.flags and self.flag_definition == value.flag_definition
        )

    @classmethod
    def from_diffed_grouped_shader(
        cls,
        shader: DiffedShaderWithGroupedLines,
        flag_def: LocalFlagDeinition,
        all_flags: AllFlags,
    ):
        calc_list: list[ExpressionSearchInput] = []
        cls._extract_search_inputs(
            shader.main_code, all_flags.main_flags, flag_def.main_shader, calc_list
        )

        for func_name, func_body in shader.functions.items():
            cls._extract_search_inputs(
                func_body,
                all_flags.function_flags[func_name],
                flag_def.functions[func_name],
                calc_list,
            )

        return calc_list

    @classmethod
    def _extract_search_inputs(
        cls,
        code_line_groups: list[CodeLineGroup],
        all_flags: list[ShaderFlags],
        flag_def: FlagDefinition,
        expr_search_input_list: list["ExpressionSearchInput"],
    ):
        for line_group in code_line_groups:
            if len(line_group.condition) == len(all_flags):
                continue
            search_input = cls()
            search_input.flag_definition = flag_def
            search_input.flags = [
                (flags in line_group.condition, flags) for flags in all_flags
            ]
            try:
                index = expr_search_input_list.index(search_input)
            except ValueError:
                index = len(expr_search_input_list)
                expr_search_input_list.append(search_input)
            line_group.expression_search_index = index


class JoinType(Enum):
    """
    Determines how expression search token should be combined with other tokens.

    - `Or` - Token is boolean ORed with the result of evaluating previous tokens
    - `And` - Token is boolean ANDed with the result of evaluating previous tokens
    - `Initial` - Current expression value is directly equal to the token value. This must only be used for the first token in the sequence

    For example, the string of tokens `[token0, token1, token2, token3]` could
    form the following expression `(token0 && token1) || token2) && token3`
    in which case tokens would have the following join types:
    - token0 - `Initial` (the first token must always have `Initial` join type)
    - token1 - `And`
    - token2 - `Or`
    - token3 - `And`
    """

    Or = auto()
    And = auto()
    Initial = auto()


class ExpressionSearchToken:
    """
    Intermediate object used in expression search algorithm.
    """

    join_type: JoinType
    "Controls how this token is combined with previous tokens in a boolean expression"
    is_negative: bool
    "Determines whether the token is negated or not"
    flag_name: FlagName
    flag_value: FlagValue

    def __init__(self):
        self.join_type = JoinType.Initial
        self.is_negative = False
        self.flag_name = ""
        self.flag_value = ""

    def __copy__(self):
        obj = ExpressionSearchToken()

        obj.join_type = self.join_type
        obj.is_negative = self.is_negative
        obj.flag_name = self.flag_name
        obj.flag_value = self.flag_value

        return obj

    def __deepcopy__(self, memo):
        obj = ExpressionSearchToken()

        obj.join_type = self.join_type
        obj.is_negative = self.is_negative
        obj.flag_name = self.flag_name
        obj.flag_value = self.flag_value

        return obj


class ExpressionSearchOutput:
    """
    Object representing the results of expression search algorithm - it holds
    the best found expression token sequence, along with its score
    """

    token_list: list[ExpressionSearchToken]
    score: int

    def __init__(self):
        self.token_list = []
        self.score = 0


def _evaluate_expression(
    expression_token_list: list[ExpressionSearchToken], flags: ShaderFlags
) -> bool:
    """
    Evaluates expression token sequence for a given set of flags.
    """
    # Evaluation is in reverse order, as that allows to perform short-circuiting
    for token in reversed(expression_token_list):
        token_value = flags.get(token.flag_name, None) == token.flag_value

        if token.is_negative:
            token_value = not token_value

        if token.join_type is JoinType.And:
            if not token_value:
                return False
        elif token.join_type is JoinType.Or:
            if token_value:
                return True
        elif token.join_type is JoinType.Initial:
            return token_value


def _calc_score(
    expression_token_list: list[ExpressionSearchToken],
    flag_outcomes: list[tuple[FlagsOutcome, ShaderFlags]],
):
    """
    Calculates the score of a sequence, which is equal to the number of sets of flags that it can correctly match
    """
    score = 0
    for outcome, flags in flag_outcomes:
        score += (
            1 if _evaluate_expression(expression_token_list, flags) == outcome else 0
        )

    return score


def _fast_search(input: ExpressionSearchInput):
    """
    This algorithm attempts to find a sequence of expression tokens that correctly executes for all sets of flags.
    It works by testing one token at a time - finding a configuration of a token that yields the highest score, then
    moving on to the next token and doing the same.

    This function is fast because it has linear complexity in the token sequence length, but it's not guaranteed to find an exact solution.
    """
    best_expression: list[ExpressionSearchToken] = []
    best_expression_score = 0

    current_expression: list[ExpressionSearchToken] = []

    for _ in range(len(input.flag_definition) + 5):
        best_token = ExpressionSearchToken()
        best_token_score = 0
        current_expression.append(copy(best_token))

        join_list = (
            (JoinType.Initial,)
            if len(current_expression) == 1
            else (JoinType.Or, JoinType.And)
        )
        token = current_expression[-1]
        for is_negative in (False, True):
            token.is_negative = is_negative
            for join_type in join_list:
                token.join_type = join_type
                for flag_name, flag_values in input.flag_definition.items():
                    token.flag_name = flag_name
                    for flag_value in flag_values:
                        token.flag_value = flag_value

                        score = _calc_score(current_expression, input.flags)

                        if score > best_token_score:
                            best_token_score = score
                            best_token = copy(token)

        current_expression[-1] = best_token

        if best_token_score > best_expression_score:
            best_expression = current_expression[:]
            best_expression_score = best_token_score

        if best_expression_score >= len(input.flags):
            break

    return best_expression_score, best_expression


def _increment_expression(
    expression: list[ExpressionSearchToken], flag_def: FlagDefinition
):
    """
    This function cycles through all possible sequences of tokens.
    Given a sequence of tokens, it creates the next sequence by changing some of the properties of tokens or appending a new token at the end.
    """
    for token in expression:
        # Increment flag value
        flag_value_list = flag_def[token.flag_name]
        new_value_index = flag_value_list.index(token.flag_value) + 1

        if new_value_index != len(flag_value_list):
            token.flag_value = flag_value_list[new_value_index]
            return

        # Increment flag name
        flag_name_list = list(flag_def.keys())
        new_name_index = flag_name_list.index(token.flag_name) + 1

        if new_name_index != len(flag_name_list):
            token.flag_name = flag_name_list[new_name_index]
            token.flag_value = flag_def[token.flag_name][0]
            return

        token.flag_name = flag_name_list[0]
        token.flag_value = flag_def[token.flag_name][0]

        # Increment join type
        if token.join_type != JoinType.Initial:
            if token.join_type == JoinType.Or:
                token.join_type = JoinType.And
                return
            token.join_type = JoinType.Or

        # Increment is_negative
        if not token.is_negative:
            token.is_negative = True
            return
        token.is_negative = False

    # If all values of all tokens were reset, add a new token at the end
    token = ExpressionSearchToken()
    token.flag_name = list(flag_def.keys())[0]
    token.flag_value = flag_def[token.flag_name][0]
    token.is_negative = False
    token.join_type = JoinType.Initial if len(expression) == 0 else JoinType.Or

    expression.append(token)


def _slow_search(input: ExpressionSearchInput, timeout: float = 10):
    """
    This algorithm attempts to find a sequence of expression tokens that correctly executes for all sets of flags.

    It's a brute-force algorithm that checks every possible combination of tokens. Given infinite time it is guaranteed to find the exact solution,
    but because it has an exponential complexity in the number of tokens in a sequence, it can be quite slow, which is why a timeout parameter is necessary.
    """
    best_expression: list[ExpressionSearchToken] = []
    best_expression_score = 0

    current_expression: list[ExpressionSearchToken] = []
    t = time.perf_counter()
    while True:
        score = _calc_score(current_expression, input.flags)

        if score > best_expression_score:
            best_expression_score = score
            best_expression = [copy(token) for token in current_expression]

        if (
            best_expression_score == len(input.flags)
            or time.perf_counter() - t >= timeout
        ):
            break

        _increment_expression(current_expression, input.flag_definition)

    return best_expression_score, best_expression


# This is a work-in-progress new search algorithm,
# although I might remove it because it kinda sucks in comparison to a combination of fast + slow search
def _hybrid_search(input: ExpressionSearchInput, timeout: float = 10):
    best_expression: list[ExpressionSearchToken] = []
    best_expression_score = 0

    INITIAL_TOKEN = ExpressionSearchToken()
    INITIAL_TOKEN.is_negative = False
    INITIAL_TOKEN.join_type = JoinType.Or
    INITIAL_TOKEN.flag_name = list(input.flag_definition.keys())[0]
    INITIAL_TOKEN.flag_value = input.flag_definition[INITIAL_TOKEN.flag_name][0]

    reached_timeout = False

    t = time.perf_counter()
    # for search_width in range(1, 100):
    for search_width in (1, 2, 4, 8, 16, 32):
        expression: list[ExpressionSearchToken] = []
        expression_score = 0

        while len(expression) < len(input.flag_definition) + 5:
            expression_extension: list[ExpressionSearchToken] = [copy(INITIAL_TOKEN)]
            best_extension: list[ExpressionSearchToken] = [copy(INITIAL_TOKEN)]
            best_extension_score = 0

            while True:
                score = _calc_score(expression + expression_extension, input.flags)

                if score == len(input.flags):
                    return score, expression + expression_extension

                if score > best_extension_score:
                    best_extension_score = score
                    best_extension = [copy(token) for token in expression_extension]

                _increment_expression(expression_extension, input.flag_definition)

                reached_timeout = time.perf_counter() - t >= timeout
                if len(expression_extension) > search_width or reached_timeout:
                    break

            expression = expression + best_extension
            expression_score = best_extension_score

            if reached_timeout:
                break

        if expression_score > best_expression_score:
            best_expression_score = expression_score
            best_expression = expression

        if reached_timeout:
            break

    return best_expression_score, best_expression


def expression_search(inputs: list[ExpressionSearchInput], timeout: float = 10):
    """
    This function applies search algorithms in order to find a boolean expression that would correctly match all sets of flags.
    """
    output_list: list[ExpressionSearchOutput] = []
    for input in inputs:
        score, result = _fast_search(input)
        # score, result = _hybrid_search(input, timeout)

        if score != len(input.flags):
            print("Slow Search")

            slow_score, slow_result = _slow_search(input, timeout)

            if slow_score > score or (
                slow_score == score and len(slow_result) < len(result)
            ):
                score = slow_score
                result = slow_result

            if score < len(input.flags):
                print("Not Found")

        search_output = ExpressionSearchOutput()
        search_output.score = score
        search_output.token_list = result

        output_list.append(search_output)

    return output_list
