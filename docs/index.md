# Introduction

Lazurite is an unofficial shader development tool for Minecraft: Bedrock Edition with RenderDragon graphics engine, which focuses on intuitive use and powerful features.

GitHub page: <https://github.com/veka0/lazurite>

PyPi page: <https://pypi.org/project/lazurite>

## Installation

Lazurite requires to have Python 3.10+ installed, but 3.12 is recommended.

Official python installation page: <https://www.python.org/downloads>.
Windows users are recommended to install Python from Microsoft Store.

After installing python, you can install lazurite package from [pypi repository](https://pypi.org/project/lazurite), with a command

```sh
pip install lazurite
```

or

```sh
python -m pip install lazurite
```

!!!tip "Optional GLSL validator"

    If you install lazurite with a command:
    ```sh
    pip install lazurite[opengl]
    ```
    it will enable optional GLSL and ESSL shader validation capability when compiling materials. It will try to compile and verify resulting code via OpenGL API,
    which will allow you to catch errors that you wouldn't see otherwise.

    Note: this capability is not supported on Termux out of the box.

???warning "Termux installation error"

    If during Lazurite installation on Termux (Android) you encounter this error:

    ```
    aarch64-linux-android-clang++: error: unknown argument: '-fno-openmp-implicit-rpath'
          error: command '/data/data/com.termux/files/usr/bin/aarch64-linux-android-clang++' failed with exit code 1
          note: This error originates from a subprocess, and is likely not a problem with pip.

    ERROR: Failed building wheel for pyjson5
    Failed to build pycryptodome pyjson5
    ERROR: Could not build wheels for pycryptodome, pyjson5, which is required to install pyproject.toml-based projects
    ```

    It can be fixed by running the following commands (as suggested [here](<https://github.com/termux/termux-packages/issues/20039#issuecomment-2096494418>)):

    ```sh
    _file="$(find $PREFIX/lib/python3.11 -name "_sysconfigdata*.py")"
    rm -rf $PREFIX/lib/python3.11/__pycache__
    cp $_file "$_file".backup
    sed -i 's|-fno-openmp-implicit-rpath||g' "$_file"
    ```

## Next steps

Try making your [first shader](guide.md) or learn about [available commands](commands.md), [unpacked material syntax](material.md) and how [project compilation](project.md) works.
