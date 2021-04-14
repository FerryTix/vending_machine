from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import json
import os
from base64 import b64encode
from enum import Enum
from yaml import safe_load


class MachineIdentity:
    IDENTITY_FILE = '../identity.pem'
    MACHINE_CONFIG_FILE = '../machine.config.yaml'

    class KEYS(Enum):
        API_KEY = 'api_key'
        UUID = 'uuid'

    def __init__(self):
        if not (os.path.exists(MachineIdentity.IDENTITY_FILE) and
                os.path.isfile(MachineIdentity.IDENTITY_FILE)):
            self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

            with open(MachineIdentity.IDENTITY_FILE, 'wb') as key_file:
                key_file.write(self._private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
        else:
            with open(MachineIdentity.IDENTITY_FILE, 'rb') as key_file:
                self._private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                )

        if os.path.exists(MachineIdentity.MACHINE_CONFIG_FILE) and os.path.isfile(MachineIdentity.MACHINE_CONFIG_FILE):
            with open(MachineIdentity.MACHINE_CONFIG_FILE) as config_file:
                root = safe_load(config_file)
                self.api_key = root[self.KEYS.API_KEY.value]
                self.uuid = root[self.KEYS.UUID.value]
        else:
            raise RuntimeError("No configuration detected")

    def signed_data(self, data):
        data.update({'signature': self.sign(data)})
        return data

    def sign(self, data):
        return b64encode(self._private_key.sign(
            json.dumps(data).encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA3_512()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA3_512()
        ))

    def get_public_key(self):
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.PKCS1
        ).decode()


if __name__ == '__main__':
    i = MachineIdentity()
    with open('../public_key.pem', 'w') as f:
        f.write(i.get_public_key())
