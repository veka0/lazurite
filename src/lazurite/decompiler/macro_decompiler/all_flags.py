from .type_aliases import FunctionName, ShaderFlags


class AllFlags:
    """
    This object stores all permutations of flags separately for each context (main code + functions)
    """

    main_flags: list[ShaderFlags]
    function_flags: dict[FunctionName, list[ShaderFlags]]

    def __init__(self):
        self.main_flags = []
        self.function_flags = {}
