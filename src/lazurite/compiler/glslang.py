import subprocess

from lazurite.material.stage import ShaderStage
from lazurite.material.platform import ShaderPlatform


class Glslang:
    glslang_path: str

    def __init__(self, glslang_paths: list[str] | str | None = None) -> None:
        if glslang_paths is None:
            glslang_paths = ["glslang", "./glslang"]
        elif isinstance(glslang_paths, str):
            glslang_paths = [glslang_paths]

        self.glslang_path = ""

        for path in glslang_paths:
            try:
                result = subprocess.run(
                    [path, "--stdin", "-S", "frag"],
                    capture_output=True,
                    input=b"",
                )
            except FileNotFoundError:
                pass
            else:
                self.glslang_path = path
                break

        if not self.glslang_path:
            raise Exception(
                f"Error! No valid GLSLANG validator was found in the list {glslang_paths}"
            )

        if result.returncode:
            print(result.stdout.decode())
            print(result.stderr.decode())
            result.check_returncode()

    def validate(
        self,
        code: str | bytes,
        platform: ShaderPlatform = ShaderPlatform.ESSL_310,
        stage: ShaderStage = ShaderStage.Fragment,
    ):
        if not platform.name.startswith(("GLSL", "ESSL")):
            raise Exception(
                f'Invalid platform "{platform.name}", only GLSL and ESSL platforms support glslang validation.'
            )

        args = [self.glslang_path, "--stdin"]

        args.append("-S")
        if stage == ShaderStage.Compute:
            args.append("comp")
        elif stage == ShaderStage.Vertex:
            args.append("vert")
        else:
            args.append("frag")

        version_string = platform.name[-3:]
        if platform in (ShaderPlatform.ESSL_300, ShaderPlatform.ESSL_310):
            version_string += "es"
        args.extend(("--glsl-version", version_string))

        if isinstance(code, str):
            code = code.encode()

        result = subprocess.run(args, capture_output=True, input=code)

        log = []
        if result.stdout:
            log.append(result.stdout.decode())
        if result.stderr:
            log.append(result.stderr.decode())

        has_log = bool(log)
        log = "\n\n".join([""] + log + ["Command: " + " ".join(args)])

        if result.returncode:
            raise Exception(log)

        return log if has_log else ""
