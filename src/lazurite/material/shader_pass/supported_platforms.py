from ..platform import ShaderPlatform


class SupportedPlatforms:
    platforms: dict[ShaderPlatform, bool]

    def __init__(self) -> None:
        self.platforms = {platform: True for platform in ShaderPlatform}

    def _validate_bit_string(self, platforms_bit_string: str, length: int) -> str:
        if any(c not in "01" for c in platforms_bit_string):
            print(
                f"Warning: Invalid supported platforms bit field {platforms_bit_string}"
            )
            return "1" * length
        return platforms_bit_string

    def _format_bit_string(self, platforms_bit_string: str, length: int):
        # Truncate at the end if platform string is too long.
        platforms_bit_string = platforms_bit_string[:length]

        # In case the length is less than required, add leading zeros.
        platforms_bit_string = platforms_bit_string.zfill(length)

        return platforms_bit_string

    def parse_bit_string(self, platforms_bit_string: str, version: int):
        platform_list = ShaderPlatform.get_list(version)
        length = len(platform_list)

        platforms_bit_string = self._validate_bit_string(platforms_bit_string, length)
        platforms_bit_string = self._format_bit_string(platforms_bit_string, length)

        for platform, bit in zip(platform_list, platforms_bit_string):
            self.platforms[platform] = bit == "1"

        return self

    def get_bit_string(self, version: int) -> str:
        return "".join(
            "1" if self.platforms[p] else "0" for p in ShaderPlatform.get_list(version)
        )

    def load(self, json_data: dict[str, bool]):
        for key, value in json_data.items():
            self.platforms[ShaderPlatform[key]] = value

    def serialize(self, version: int):
        return {p.name: self.platforms[p] for p in ShaderPlatform.get_list(version)}
