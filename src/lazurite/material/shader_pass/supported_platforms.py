from ..platform import ShaderPlatform


class SupportedPlatforms:
    platforms: dict[ShaderPlatform, bool]

    def _validate_bit_string(self, platforms_bit_string: str) -> str:
        if any(c not in "01" for c in platforms_bit_string):
            print(
                f"Warning: Invalid supported platforms bit field {platforms_bit_string}"
            )
            return "1" * len(ShaderPlatform)
        return platforms_bit_string

    def _format_bit_string(self, platforms_bit_string: str):
        # Truncate everything after 16 symbols.
        platforms_bit_string = platforms_bit_string[: len(ShaderPlatform)]

        # In case there are less than 16, add leading zeros.
        platforms_bit_string = platforms_bit_string.zfill(len(ShaderPlatform))

        return platforms_bit_string

    def __init__(self, platforms_bit_string: str = "1" * len(ShaderPlatform)) -> None:
        platforms_bit_string = self._validate_bit_string(platforms_bit_string)
        platforms_bit_string = self._format_bit_string(platforms_bit_string)

        self.platforms = {
            platform: bit == "1"
            for platform, bit in zip(ShaderPlatform, platforms_bit_string)
        }

    def get_bit_string(self) -> str:
        return "".join("1" if self.platforms[p] else "0" for p in ShaderPlatform)

    def load(self, json_data: dict[str, bool]):
        for key, value in json_data.items():
            self.platforms[ShaderPlatform[key]] = value

    def serialize(self):
        return {p.name: v for p, v in self.platforms.items()}
