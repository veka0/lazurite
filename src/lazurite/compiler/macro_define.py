class MacroDefine:
    name: str
    value: int | None

    def __init__(self, name: str = "", value: int = None) -> None:
        self.name = name
        self.value = value

    def format_bgfx(self):
        if self.value is None:
            return self.name
        return f"{self.name}={self.value}"

    def format_dxc(self):
        if self.value is None:
            return self.name
        return f"{self.name}={self.value}"

    def format_cpp(self):
        if self.value is None:
            return self.name
        return f"{self.name} {self.value}"

    @classmethod
    def from_string(cls, string: str):
        elements = string.split(" ", 1)
        return cls(elements[0], elements[1] if len(elements) > 1 else None)
