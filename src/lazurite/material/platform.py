from enum import Enum, auto


class ShaderPlatform(Enum):
    Direct3D_SM40 = auto()
    Direct3D_SM50 = auto()
    Direct3D_SM60 = auto()
    Direct3D_SM65 = auto()
    Direct3D_XB1 = auto()
    Direct3D_XBX = auto()
    GLSL_120 = auto()
    GLSL_430 = auto()
    ESSL_300 = auto()  # Removed in format version 25
    ESSL_310 = auto()
    Metal = auto()
    Vulkan = auto()
    Nvn = auto()
    PSSL = auto()
    Unknown = auto()

    @classmethod
    def _platform_mapping(cls, version: int):
        if version >= 25:
            return {
                cls.Direct3D_SM40: 0,
                cls.Direct3D_SM50: 1,
                cls.Direct3D_SM60: 2,
                cls.Direct3D_SM65: 3,
                cls.Direct3D_XB1: 4,
                cls.Direct3D_XBX: 5,
                cls.GLSL_120: 6,
                cls.GLSL_430: 7,
                cls.ESSL_310: 8,
                cls.Metal: 9,
                cls.Vulkan: 10,
                cls.Nvn: 11,
                cls.PSSL: 12,
                cls.Unknown: 13,
                # Platform conversion
                cls.ESSL_300: cls.ESSL_310,
            }
        else:
            return {
                cls.Direct3D_SM40: 0,
                cls.Direct3D_SM50: 1,
                cls.Direct3D_SM60: 2,
                cls.Direct3D_SM65: 3,
                cls.Direct3D_XB1: 4,
                cls.Direct3D_XBX: 5,
                cls.GLSL_120: 6,
                cls.GLSL_430: 7,
                cls.ESSL_300: 8,
                cls.ESSL_310: 9,
                cls.Metal: 10,
                cls.Vulkan: 11,
                cls.Nvn: 12,
                cls.PSSL: 13,
                cls.Unknown: 14,
            }

    def get_value(self, version: int) -> int:
        mapping = self._platform_mapping(version)
        value = mapping.get(self, None)

        if isinstance(value, ShaderPlatform):
            value = mapping.get(value, None)

        if value is None:
            raise Exception(
                "Platform {self} is not supported in version {version} or there are no conversions available!"
            )

        return value

    def get_name(self, version: int) -> int:
        mapping = self._platform_mapping(version)
        platform = mapping.get(self, None)

        if isinstance(platform, int):
            platform = self
        elif platform is None:
            raise Exception(
                "Platform {self} is not supported in version {version} or there are no conversions available!"
            )

        return platform.name

    @classmethod
    def get_list(cls, version: int):
        platform_list: list[ShaderPlatform] = []

        for platform, value in cls._platform_mapping(version).items():
            if isinstance(value, int):
                platform_list.append(platform)

        return platform_list

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
