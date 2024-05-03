from enum import Enum
from io import BytesIO


class EncryptionType(Enum):
    NONE = "NONE"
    SIMPLE_PASSPHRASE = "SMPL"
    KEY_PAIR = "KYPR"  # Unsupported

    @classmethod
    def read(cls, file: BytesIO):
        return cls(file.read(4).decode()[::-1])

    def write(self, file: BytesIO):
        file.write(self.value[::-1].encode())
