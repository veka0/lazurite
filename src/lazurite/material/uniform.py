import struct, json, os
from enum import Enum
from io import BytesIO

from lazurite import util


class UniformType(Enum):
    vec4 = 2
    mat3 = 3
    mat4 = 4
    external = 5


class Uniform:

    name: str
    type: UniformType
    count: int
    default: list[float]

    def __init__(self):
        self.name = ""
        self.type = UniformType.vec4
        self.count = 0
        self.default = []

    def read(self, file: BytesIO, version: int):
        self.name = util.read_string(file)
        self.type = UniformType(util.read_ushort(file))

        self.default = []
        if 2 <= self.type.value <= 4:
            self.count = util.read_ulong(file)
            hasData = util.read_bool(file)

        if self.type.value == 2:  # vec4
            if hasData:
                self.default = struct.unpack("<" + 4 * "f", file.read(4 * 4))

        elif self.type.value == 3:  # mat3
            if hasData:
                self.default = struct.unpack("<" + 9 * "f", file.read(4 * 9))

        elif self.type.value == 4:  # mat4
            if hasData:
                self.default = struct.unpack("<" + 16 * "f", file.read(4 * 16))

        elif self.type.value == 5:  # external
            pass

        else:
            raise Exception(f'Urecognized type "{self.type}"')

        return self

    def write(self, file: BytesIO, version: int):
        util.write_string(file, self.name)
        util.write_ushort(file, self.type.value)

        if 2 <= self.type.value <= 4:
            util.write_ulong(file, self.count)
            util.write_bool(file, len(self.default) > 0)

        if len(self.default) > 0:
            file.write(struct.pack("<" + "f" * len(self.default), *self.default))

        return self

    def serialize_properties(self):
        obj = {}
        obj["name"] = self.name
        obj["type"] = self.type.name
        obj["count"] = self.count
        obj["default"] = self.default
        return obj

    def store(self, version: int, path: str = "."):
        with open(os.path.join(path, f"{self.name}.json"), "w") as f:
            json.dump(self.serialize_properties(), f, indent=4)

        return self

    def serialize_minimal(self):
        return [self.name, self.type.value, self.count, self.default]

    def load_minimal(self, object: dict):
        self.name = object[0]
        self.type = UniformType(object[1])
        self.count = object[2]
        self.default = object[3]
        return self

    def load(self, object: dict, path: str):
        self.name = object.get("name", self.name)
        self.type = UniformType[object.get("type", self.type.name)]
        self.count = object.get("count", self.count)
        self.default = object.get("default", self.default)
        return self
