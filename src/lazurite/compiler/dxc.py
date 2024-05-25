import subprocess
from lazurite.material.stage import ShaderStage
from lazurite.material.platform import ShaderPlatform
from lazurite.tempfile import CustomTempFile

from .macro_define import MacroDefine


class DxcCompiler:
    dxc_path: str

    def __init__(self, dxc_paths: list[str] | str = None) -> None:
        if dxc_paths is None:
            dxc_paths = ["dxc", "./dxc"]
        elif isinstance(dxc_paths, str):
            dxc_paths = [dxc_paths]

        self.dxc_path = ""

        for path in dxc_paths:
            try:
                result = subprocess.run([path, "-help"], capture_output=True)
            except FileNotFoundError:
                pass
            else:
                self.dxc_path = path
                break

        if not self.dxc_path:
            raise Exception(
                f"Error! No valid DXC compiler was found in the list {dxc_paths}"
            )

        if result.returncode:
            print(result.stdout.decode())
            print(result.stderr.decode())
            result.check_returncode()

    def compile(
        self,
        file: str,
        platform: ShaderPlatform = ShaderPlatform.Direct3D_SM65,
        stage: ShaderStage = ShaderStage.Compute,
        entry_point: str = None,
        include: list[str] = None,
        defines: list[MacroDefine] = None,
        options: list[str] = None,
    ):
        if not platform.name.startswith("Direct3D_SM"):
            raise Exception(
                f"{platform.name} shaders cannot be compiled with DXC compiler!"
            )

        args = [self.dxc_path, file]

        if stage == ShaderStage.Compute:
            profile = "cs"  # Compute Shader
        elif stage == ShaderStage.Vertex:
            profile = "vs"  # Vertex Shader
        else:
            profile = "ps"  # Pixel Shader
        version = platform.name.removeprefix("Direct3D_SM")
        args.extend(("-T", "_".join((profile, *version))))

        if entry_point:
            args.extend(("-E", entry_point))

        if include:
            for item in include:
                args.extend(("-I", item))

        if defines:
            for define in defines:
                args.extend(("-D", define.format_dxc()))

        if options:
            args.extend(options)

        with CustomTempFile() as f:
            f.close()
            args.extend(("-Fo", f.name))

            result = subprocess.run(args)

            if result.stderr:
                print(result.stderr.decode())
            if result.stdout:
                print(result.stdout.decode())

            result.check_returncode()

            with open(f.name, "rb") as f:
                return f.read()
