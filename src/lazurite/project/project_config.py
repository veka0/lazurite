import os, pyjson5
from lazurite.material import Material
from lazurite.material.shader_pass.shader_definition import ShaderPlatform
from lazurite.compiler.macro_define import MacroDefine


class ProjectConfig:
    macros: list[MacroDefine]
    platforms: list[ShaderPlatform]
    merge_source: list[str]
    include_patterns: list[str]
    exclude_patterns: list[str]

    def __init__(self) -> None:
        self.macros = []
        self.platforms = []
        self.merge_source = []
        self.include_patterns = ["*"]
        self.exclude_patterns = [".*", "_*"]

    def read_json_file(self, path: str, profiles: list[str]):
        def append_unique(target: list, source: list):
            """
            Appends elements from source to target, if they aren't in target list already.
            """
            target.extend((item for item in source if item not in target))

        if not os.path.isfile(path):
            return
        with open(path) as f:
            json_data = pyjson5.load(f)
        has_macros = False
        has_platforms = False
        has_merge = False
        has_include_pattern = False
        has_exclude_pattern = False
        if "profiles" in json_data:
            json_profiles = json_data["profiles"]
            for profile in profiles:
                if profile not in json_profiles:
                    print(f'Warning: profile "{profile}" was not found!')
                    continue
                profile = json_profiles[profile]

                if "macros" in profile:
                    if not has_macros:
                        self.macros = []
                        has_macros = True
                    append_unique(
                        self.macros,
                        [MacroDefine.from_string(m) for m in profile["macros"]],
                    )

                if "platforms" in profile:
                    if not has_platforms:
                        self.platforms = []
                        has_platforms = True
                    append_unique(
                        self.platforms,
                        (ShaderPlatform[p] for p in profile["platforms"]),
                    )

                if "merge_source" in profile:
                    if not has_merge:
                        self.merge_source = []
                        has_merge = True
                    append_unique(self.merge_source, profile["merge_source"])

                if "include_patterns" in profile:
                    if not has_include_pattern:
                        self.include_patterns = []
                        has_include_pattern = True
                    patterns = profile["include_patterns"]
                    append_unique(
                        self.include_patterns,
                        [patterns] if type(patterns) == str else patterns,
                    )

                if "exclude_patterns" in profile:
                    if not has_exclude_pattern:
                        self.exclude_patterns = []
                        has_exclude_pattern = True
                    patterns = profile["exclude_patterns"]
                    append_unique(
                        self.exclude_patterns,
                        [patterns] if type(patterns) == str else patterns,
                    )

        if "base_profile" in json_data:
            base_profile = json_data["base_profile"]
            if "macros" in base_profile and not has_macros:
                self.macros = [
                    MacroDefine.from_string(m) for m in base_profile["macros"]
                ]

            if "platforms" in base_profile and not has_platforms:
                self.platforms = [ShaderPlatform[p] for p in base_profile["platforms"]]

            if "merge_source" in base_profile and not has_merge:
                self.merge_source = base_profile["merge_source"]

            if "include_patterns" in base_profile and not has_include_pattern:
                patterns = base_profile["include_patterns"]
                self.include_patterns = (
                    [patterns] if type(patterns) == str else patterns
                )

            if "exclude_patterns" in base_profile and not has_exclude_pattern:
                patterns = base_profile["exclude_patterns"]
                self.exclude_patterns = (
                    [patterns] if type(patterns) == str else patterns
                )

        new_merge_source = []
        for merge_path in self.merge_source:
            merge_path = os.path.normpath(
                os.path.join(os.path.split(path)[0], merge_path)
            )
            if (
                os.path.isfile(merge_path)
                and merge_path not in new_merge_source
                and merge_path.endswith(Material.EXTENSION)
            ):
                new_merge_source.append(merge_path)
            elif os.path.isdir(merge_path):
                for mat_dir in os.scandir(merge_path):
                    if (
                        mat_dir.is_file()
                        and mat_dir.path not in new_merge_source
                        and mat_dir.path.endswith(Material.EXTENSION)
                    ):
                        new_merge_source.append(mat_dir.path)
            else:
                print(f'Warning: merge path "{merge_path}" was not found')
        self.merge_source = new_merge_source
