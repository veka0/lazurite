import json, os
from io import BytesIO
from enum import Enum

from lazurite import util
from .precision import Precision


class BufferAccess(Enum):
    undefined = 0
    readonly = 1
    writeonly = 2
    readwrite = 3


class BufferType(Enum):
    texture2D = 0
    texture2DArray = 1
    external2D = 2  # ?
    texture3D = 3  # ?
    textureCube = 4
    textureCubeArray = 5
    structBuffer = 6
    rawBuffer = 7
    accelerationStructure = 8  # ?
    shadow2D = 9
    shadow2DArray = 10
    # unknown = 11  # ?

    # ? -> never observed in-game


class Buffer:
    class CustomTypeInfo:
        struct: str
        size: int

        def __init__(self, struct="", size=0):
            self.struct = struct
            self.size = size

    name: str
    reg1: int
    access: BufferAccess
    precision: Precision
    unordered_access: bool
    type: BufferType
    texture_format: str
    always_one: int
    reg2: int
    default_texture: str
    unknown_string: str
    custom_type_info: CustomTypeInfo | None

    def __init__(self):
        self.name = ""
        self.reg1 = 0
        self.access = BufferAccess.readonly
        self.precision = Precision.lowp
        self.unordered_access = False
        self.type = BufferType.texture2D
        self.texture_format = ""
        self.always_one = 1
        self.reg2 = 0
        self.default_texture = ""
        self.unknown_string = ""
        self.custom_type_info = None

    def read(self, file: BytesIO):
        self.name = util.read_string(file)
        self.reg1 = util.read_ushort(file)
        self.access = BufferAccess(util.read_ubyte(file))  # 1 2 3
        self.precision = Precision(util.read_ubyte(file))  # 0 2
        self.unordered_access = util.read_bool(file)
        self.type = BufferType(util.read_ubyte(file))  # 0 - 9
        # Values according to bgfx_compute.sh: (empty string) r32ui rg32ui rgba32ui r32f r16f rg16f rgba16f rgba8 rg8 r8 rgba32f
        self.texture_format = util.read_string(file)
        self.always_one = util.read_ulong(file)  # 1
        self.reg2 = util.read_ubyte(file)  # same as reg1

        if util.read_bool(file):
            self.default_texture = util.read_string(file)  # white
        else:
            self.default_texture = ""

        if util.read_bool(file):
            self.unknown_string = util.read_string(file)
            # print(self.unknown_string)  # TODO: remove

        if util.read_bool(file):  # CustomTypeInfo
            self.custom_type_info = self.CustomTypeInfo()
            self.custom_type_info.struct = util.read_string(file)
            self.custom_type_info.size = util.read_ulong(file)

        return self

    def write(self, file: BytesIO):
        util.write_string(file, self.name)
        util.write_ushort(file, self.reg1)
        util.write_ubyte(file, self.access.value)
        util.write_ubyte(file, self.precision.value)
        util.write_bool(file, self.unordered_access)
        util.write_ubyte(file, self.type.value)
        util.write_string(file, self.texture_format)
        util.write_ulong(file, self.always_one)
        util.write_ubyte(file, self.reg2)

        util.write_bool(file, self.default_texture != "")
        if self.default_texture != "":
            util.write_string(file, self.default_texture)

        util.write_bool(file, self.unknown_string != "")
        if self.unknown_string != "":
            util.write_string(file, self.unknown_string)

        util.write_bool(file, self.custom_type_info != None)
        if self.custom_type_info != None:
            util.write_string(file, self.custom_type_info.struct)
            util.write_ulong(file, self.custom_type_info.size)

        return self

    def serialize_properties(self):
        obj = {
            "name": self.name,
            "reg1": self.reg1,
            "reg2": self.reg2,
            "type": self.type.name,
            "precision": self.precision.name,
            "access": self.access.name,
            "texture_format": self.texture_format,
            "default_texture": self.default_texture,
            "unordered_access": self.unordered_access,
            "always_one": self.always_one,
            "unknown_string": self.unknown_string,
            "custom_type_info": {},
        }
        if self.custom_type_info != None:
            obj["custom_type_info"]["struct"] = self.custom_type_info.struct
            obj["custom_type_info"]["size"] = self.custom_type_info.size

        return obj

    def store(self, path: str = "."):
        with open(os.path.join(path, f"{self.name}.json"), "w") as f:
            json.dump(self.serialize_properties(), f, indent=4)

        return self

    def serialize_minimal(self):
        obj = [
            self.name,
            self.reg1,
            self.reg2,
            self.type.value,
            self.precision.value,
            self.access.value,
            self.texture_format,
            self.default_texture,
            int(self.unordered_access),
            self.always_one,
            self.unknown_string,
        ]
        if self.custom_type_info != None:
            obj.append(self.custom_type_info.struct)
            obj.append(self.custom_type_info.size)

        return obj

    def load_minimal(self, object: list):
        self.name = object[0]
        self.reg1 = object[1]
        self.reg2 = object[2]
        self.type = BufferType(object[3])
        self.precision = Precision(object[4])
        self.access = BufferAccess(object[5])
        self.texture_format = object[6]
        self.default_texture = object[7]
        self.unordered_access = bool(object[8])
        self.always_one = object[9]
        self.unknown_string = object[10]

        if len(object) > 11:
            self.custom_type_info = Buffer.CustomTypeInfo(object[11], object[12])
        return self

    def load(self, object: dict, path: str):
        self.name = object.get("name", self.name)
        self.reg1 = object.get("reg1", self.reg1)
        self.access = BufferAccess[object.get("access", self.access.name)]
        self.precision = Precision[object.get("precision", self.precision.name)]
        self.unordered_access = object.get("unordered_access", self.unordered_access)
        self.type = BufferType[object.get("type", self.type.name)]
        self.texture_format = object.get("texture_format", self.texture_format)
        self.always_one = object.get("always_one", self.always_one)
        self.unknown_string = object.get("unknown_string", self.unknown_string)
        self.reg2 = object.get("reg2", self.reg2)
        self.default_texture = object.get("default_texture", self.default_texture)

        if "custom_type_info" in object:
            if len(object["custom_type_info"]) > 0:
                if self.custom_type_info == None:
                    self.custom_type_info = self.CustomTypeInfo()

                self.custom_type_info.struct = object["custom_type_info"].get(
                    "struct", self.custom_type_info.struct
                )
                self.custom_type_info.size = object["custom_type_info"].get(
                    "size", self.custom_type_info.size
                )

            else:
                self.custom_type_info = None

        return self
