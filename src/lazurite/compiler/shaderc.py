import subprocess

from lazurite.material.stage import ShaderStage
from lazurite.material.platform import ShaderPlatform
from lazurite.material.shader_pass.bgfx_shader import BgfxShader
from lazurite.tempfile import CustomTempFile

from .macro_define import MacroDefine


class ShadercCompiler:
    shaderc_path: str

    def __init__(self, shaderc_paths: list[str] | str = None) -> None:
        if shaderc_paths is None:
            shaderc_paths = ["shaderc", "./shaderc"]
        elif isinstance(shaderc_paths, str):
            shaderc_paths = [shaderc_paths]

        self.shaderc_path = ""

        for path in shaderc_paths:
            try:
                result = subprocess.run([path, "-v"], capture_output=True)
            except FileNotFoundError:
                pass
            else:
                self.shaderc_path = path
                break

        if not self.shaderc_path:
            raise Exception(
                f"Error! No valid SHADERC compiler was found in the list {shaderc_paths}"
            )

        if result.returncode:
            print(result.stdout.decode())
            print(result.stderr.decode())
            result.check_returncode()

    def compile(
        self,
        file: str,
        platform: ShaderPlatform = ShaderPlatform.ESSL_310,
        stage: ShaderStage = ShaderStage.Fragment,
        varying_def: str = None,
        include: list[str] = None,
        defines: list[MacroDefine] = None,
        options: list[str] = None,
    ):
        args = [self.shaderc_path]

        args.extend(("-f", file))

        device = ""
        if platform == ShaderPlatform.Metal:
            device = "ios"
        elif platform.name.startswith("ESSL"):
            device = "android"
        elif platform.name.startswith("GLSL"):
            device = "linux"
        elif platform.name.startswith("Direct3D"):
            device = "windows"
        if device:
            args.extend(("--platform", device))

        profile = ""
        if platform == ShaderPlatform.Direct3D_SM40:
            profile = "s_4_0"
        elif platform == ShaderPlatform.Vulkan:
            profile = "spirv"
        elif platform in {ShaderPlatform.Metal, ShaderPlatform.PSSL}:
            profile = platform.name.lower()
        elif platform.name.startswith("Direct3D_SM"):
            profile = "s_5_0"
        elif platform.name.startswith("GLSL"):
            profile = platform.name.removeprefix("GLSL_")
        elif platform.name.startswith("ESSL"):
            profile = platform.name.removeprefix("ESSL_") + "_es"
        if profile:
            args.extend(("-p", profile))

        args.append("--type")
        if stage == ShaderStage.Compute:
            args.append("compute")
        elif stage == ShaderStage.Vertex:
            args.append("vertex")
        else:
            args.append("fragment")

        if varying_def is not None:
            args.extend(("--varyingdef", varying_def))

        if include:
            for item in include:
                args.extend(("-i", item))

        if defines:
            args.extend(("--define", ";".join(d.format_bgfx() for d in defines)))

        if options:
            args.extend(options)

        with CustomTempFile() as f:
            args.extend(("-o", f.name))

            result = subprocess.run(args, capture_output=True)

            log = []
            if result.stdout:
                log.append(result.stdout.decode())
            if result.stderr:
                log.append(result.stderr.decode())

            has_log = bool(log)
            log = "\n\n".join([""] + log + ["Command: " + " ".join(args)])

            if result.returncode:
                raise Exception(log)

            if has_log:
                print(log)

            bgfx_shader = BgfxShader()
            bgfx_shader.read(f, platform, stage)

        return bgfx_shader


def generate_bgfx_defines(platform: ShaderPlatform, stage: ShaderStage):
    keys = [
        # Platform
        "BX_PLATFORM_ANDROID",
        "BX_PLATFORM_EMSCRIPTEN",
        "BX_PLATFORM_IOS",
        "BX_PLATFORM_LINUX",
        "BX_PLATFORM_OSX",
        "BX_PLATFORM_PS4",
        "BX_PLATFORM_WINDOWS",
        "BX_PLATFORM_XBOXONE",
        # Language
        "BGFX_SHADER_LANGUAGE_GLSL",
        "BGFX_SHADER_LANGUAGE_HLSL",
        "BGFX_SHADER_LANGUAGE_METAL",
        "BGFX_SHADER_LANGUAGE_PSSL",
        "BGFX_SHADER_LANGUAGE_SPIRV",
        # Stage
        "BGFX_SHADER_TYPE_COMPUTE",
        "BGFX_SHADER_TYPE_FRAGMENT",
        "BGFX_SHADER_TYPE_VERTEX",
    ]

    defines = {key: 0 for key in keys}

    # Stage
    if stage == ShaderStage.Compute:
        defines["BGFX_SHADER_TYPE_COMPUTE"] = 1
    elif stage == ShaderStage.Vertex:
        defines["BGFX_SHADER_TYPE_VERTEX"] = 1
    else:
        defines["BGFX_SHADER_TYPE_FRAGMENT"] = 1

    # Platform & language
    if platform == ShaderPlatform.Metal:
        defines["BX_PLATFORM_IOS"] = 1
        defines["BGFX_SHADER_LANGUAGE_METAL"] = 1

    elif platform.name.startswith("ESSL"):
        defines["BX_PLATFORM_ANDROID"] = 1
        defines["BGFX_SHADER_LANGUAGE_GLSL"] = int(platform.name.removeprefix("ESSL_"))

    elif platform.name.startswith("GLSL"):
        defines["BX_PLATFORM_LINUX"] = 1
        defines["BGFX_SHADER_LANGUAGE_GLSL"] = int(platform.name.removeprefix("GLSL_"))

    elif platform.name.startswith("Direct3D"):
        defines["BX_PLATFORM_WINDOWS"] = 1
        defines["BGFX_SHADER_LANGUAGE_HLSL"] = (
            400 if platform == ShaderPlatform.Direct3D_SM40 else 500
        )

    elif platform == ShaderPlatform.PSSL:
        defines["BX_PLATFORM_PS4"] = 1
        defines["BGFX_SHADER_LANGUAGE_PSSL"] = 1

    elif platform == ShaderPlatform.Vulkan:
        defines["BGFX_SHADER_LANGUAGE_SPIRV"] = 1

    return [MacroDefine(key, value) for key, value in defines.items()]


# BX_PLATFORM_ANDROID 0 1
# BX_PLATFORM_EMSCRIPTEN 0 1
# BX_PLATFORM_IOS 0 1
# BX_PLATFORM_LINUX 0 1
# BX_PLATFORM_OSX 0 1
# BX_PLATFORM_PS4 0 1
# BX_PLATFORM_WINDOWS 0 1
# BX_PLATFORM_XBOXONE 0 1

# BGFX_SHADER_LANGUAGE_GLSL (ESSL) id [120] 130 140 150 330 400 410 420 [430] 440 ESSL [100] [300] [310] 320
# BGFX_SHADER_LANGUAGE_HLSL id 300 [400] [500]
# BGFX_SHADER_LANGUAGE_METAL 0 1 for ios id for osx 1000
# BGFX_SHADER_LANGUAGE_PSSL 0 1 1000
# BGFX_SHADER_LANGUAGE_SPIRV 0 1 id [1010] 1311 1411 1512 1613

# BGFX_SHADER_TYPE_COMPUTE 0 1
# BGFX_SHADER_TYPE_FRAGMENT 0 1
# BGFX_SHADER_TYPE_VERTEX 0 1
