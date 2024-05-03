from enum import Enum


class ShaderPlatform(Enum):
    Direct3D_SM40 = 0
    Direct3D_SM50 = 1
    Direct3D_SM60 = 2
    Direct3D_SM65 = 3
    Direct3D_XB1 = 4
    Direct3D_XBX = 5
    GLSL_120 = 6
    GLSL_430 = 7
    ESSL_100 = 8
    ESSL_300 = 9
    ESSL_310 = 10
    Metal = 11
    Vulkan = 12
    Nvn = 13
    PSSL = 14
    Unknown = 15

    def file_extension(self):
        if self.name.startswith("Direct3D"):
            return "dxbc"

        elif self.name.startswith("GLSL") or self.name.startswith("ESSL"):
            return "glsl"

        elif self.name == "Metal":
            return "metal"

        elif self.name == "Vulkan":
            return "spirv"

        else:
            return "bin"
