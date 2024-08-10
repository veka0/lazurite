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
    ESSL_300 = 8
    ESSL_310 = 9
    Metal = 10
    Vulkan = 11
    Nvn = 12
    PSSL = 13
    Unknown = 14

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
