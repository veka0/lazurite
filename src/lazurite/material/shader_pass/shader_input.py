from io import BytesIO
from enum import Enum

from lazurite import util
from ..precision import Precision


class Interpolation(Enum):
    none = None
    flat = 0
    smooth = 1
    noperspective = 2
    centroid = 3


class InputType(Enum):
    float = 0
    vec2 = 1
    vec3 = 2
    vec4 = 3
    int = 4
    ivec2 = 5
    ivec3 = 6
    ivec4 = 7
    uint = 8
    uvec2 = 9
    uvec3 = 10
    uvec4 = 11
    mat4 = 12


class InputSemantic:
    TYPES = [
        # TODO: potentially remove is_range_allowed and remove 0 from input names if they have it. (check if compiles first??)
        # (semantic, variable_name, is_range_allowed)
        ("POSITION", "position", False),
        ("NORMAL", "normal", False),
        ("TANGENT", "tangent", False),
        ("BITANGENT", "bitangent", False),
        ("COLOR", "color", True),  # range 0 - 3
        ("BLENDINDICES", "indices", False),
        ("BLENDWEIGHT", "weight", False),
        ("TEXCOORD", "texcoord", True),  # range 0 - 8
        ("UNKNOWN", "unknown", True),  # TODO: figure out (potentially VPOS?).
        ("FRONTFACING", "frontFacing", False),
    ]

    index: int
    sub_index: int

    def __init__(self, index=0, sub_index=0) -> None:
        self.index = index
        self.sub_index = sub_index

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, InputSemantic):
            return False

        return self.index == __value.index and self.sub_index == __value.sub_index

    def get_name(self) -> str:
        name, _, is_ranged = self.TYPES[self.index]
        return name + (str(self.sub_index) if is_ranged else "")

    def get_variable_name(self):
        _, name, is_ranged = self.TYPES[self.index]
        if is_ranged:
            name += str(self.sub_index)
        return name

    @classmethod
    def from_name(cls, name: str):
        semantic = cls()
        for i, (attr_type, _, _) in enumerate(cls.TYPES):
            if name.startswith(attr_type):
                semantic.index = i
                semantic.sub_index = int(
                    name.removeprefix(attr_type) or semantic.sub_index
                )
                break

        return semantic


class ShaderInput:
    name: str
    type: InputType
    semantic: InputSemantic
    per_instance: bool
    precision: Precision
    interpolation: Interpolation

    def __init__(self) -> None:
        self.name = ""
        self.type = InputType.float
        self.semantic = InputSemantic()
        self.per_instance = False
        self.precision = Precision.none
        self.interpolation = Interpolation.none

    def __eq__(self, __value: object) -> bool:
        if type(__value) != ShaderInput:
            return False
        return (
            self.name == __value.name
            and self.type == __value.type
            and self.semantic == __value.semantic
            and self.per_instance == __value.per_instance
            and self.precision == __value.precision
            and self.interpolation == __value.interpolation
        )

    def read(self, file):
        self.name = util.read_string(file)
        self.type = InputType(util.read_ubyte(file))  # 0 - 4
        self.semantic = InputSemantic(util.read_ubyte(file), util.read_ubyte(file))
        self.per_instance = util.read_bool(file)

        if util.read_bool(file):
            self.precision = Precision(util.read_ubyte(file))
        else:
            self.precision = Precision.none

        if util.read_bool(file):
            self.interpolation = Interpolation(util.read_ubyte(file))  # 0-3
        else:
            self.interpolation = Interpolation.none

        return self

    def write(self, file: BytesIO):
        util.write_string(file, self.name)
        util.write_ubyte(file, self.type.value)
        util.write_ubyte(file, self.semantic.index)
        util.write_ubyte(file, self.semantic.sub_index)
        util.write_bool(file, self.per_instance)

        util.write_bool(file, self.precision != Precision.none)
        if self.precision != Precision.none:
            util.write_ubyte(file, self.precision.value)

        util.write_bool(file, self.interpolation != Interpolation.none)
        if self.interpolation != Interpolation.none:
            util.write_ubyte(file, self.interpolation.value)

        return self

    def serialize_properties(self):
        obj = {}
        obj["name"] = self.name
        obj["type"] = self.type.name
        obj["semantic"] = self.semantic.get_name()
        obj["per_instance"] = self.per_instance
        obj["precision"] = (
            self.precision.name if self.precision != Precision.none else ""
        )
        obj["interpolation"] = (
            self.interpolation.name if self.interpolation != Interpolation.none else ""
        )
        return obj

    def load(self, object: dict):
        self.name = object["name"]
        self.type = InputType[object["type"]]
        self.semantic = InputSemantic.from_name(object["semantic"])
        self.per_instance = object["per_instance"]
        self.precision = Precision[object["precision"] or "none"]
        self.interpolation = Interpolation[object["interpolation"] or "none"]
        return self
