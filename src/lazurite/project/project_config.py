import os, pyjson5
from collections.abc import Callable
from typing import Any

from lazurite.material import Material
from lazurite.material.shader_pass.shader_definition import ShaderPlatform
from lazurite.compiler.macro_define import MacroDefine


class ProjectConfig:
    macros: list[MacroDefine]
    platforms: list[ShaderPlatform]
    merge_source: list[str]
    include_patterns: list[str]
    exclude_patterns: list[str]
    include_search_paths: list[str]

    def __init__(self) -> None:
        self.macros = []
        self.platforms = []
        self.merge_source = []
        self.include_patterns = ["*"]
        self.exclude_patterns = [".*", "_*"]
        self.include_search_paths = []

    def read_json_file(self, path: str, profiles: list[str]):
        if not os.path.isfile(path):
            return
        with open(path) as f:
            json_data = pyjson5.load(f)
        project_folder = os.path.split(path)[0]

        properties: list[tuple[list, str, Callable[[Any], list]]] = [
            (
                self.macros,
                "macros",
                lambda p: [MacroDefine.from_string(x) for x in p],
            ),
            (
                self.platforms,
                "platforms",
                lambda p: [ShaderPlatform[x] for x in p],
            ),
            (
                self.merge_source,
                "merge_source",
                lambda p: p,
            ),
            (
                self.include_patterns,
                "include_patterns",
                lambda p: p,
            ),
            (
                self.exclude_patterns,
                "exclude_patterns",
                lambda p: p,
            ),
            (
                self.include_search_paths,
                "include_search_paths",
                lambda p: [
                    os.path.normpath(os.path.join(project_folder, x)) for x in p
                ],
            ),
        ]
        updated_properties = {name: False for _, name, _ in properties}

        if "profiles" in json_data:
            json_profiles = json_data["profiles"]
            for profile in profiles:
                if profile not in json_profiles:
                    print(f'Warning: profile "{profile}" was not found!')
                    continue
                profile = json_profiles[profile]

                for property, property_name, value_getter in properties:
                    if property_name in profile:
                        if not updated_properties[property_name]:
                            property[:] = []
                            updated_properties[property_name] = True

                        values = value_getter(profile[property_name])
                        property.extend(
                            (item for item in values if item not in property)
                        )

        if "base_profile" in json_data:
            base_profile = json_data["base_profile"]

            for property, property_name, value_getter in properties:
                if (
                    property_name in base_profile
                    and not updated_properties[property_name]
                ):
                    property[:] = value_getter(base_profile[property_name])

        new_merge_source = []
        for merge_path in self.merge_source:
            merge_path = os.path.normpath(os.path.join(project_folder, merge_path))
            if (
                os.path.isfile(merge_path)
                and merge_path not in new_merge_source
                and merge_path.endswith((Material.EXTENSION, Material.JSON_EXTENSION))
            ):
                new_merge_source.append(merge_path)
            elif os.path.isdir(merge_path):
                for mat_dir in os.scandir(merge_path):
                    if (
                        mat_dir.is_file()
                        and mat_dir.path not in new_merge_source
                        and mat_dir.path.endswith(
                            (Material.EXTENSION, Material.JSON_EXTENSION)
                        )
                    ):
                        new_merge_source.append(mat_dir.path)
            else:
                print(f'Warning: merge path "{merge_path}" was not found')
        self.merge_source = new_merge_source
