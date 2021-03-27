from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import json
import os
from base64 import b64encode


class MachineIdentity:
    IDENTIFY_FILE = './identity.pem'
    API_KEY_FILE = './api.key'

    def __init__(self):
        if not (os.path.exists(MachineIdentity.IDENTIFY_FILE) and
                os.path.isfile(MachineIdentity.IDENTIFY_FILE)):
            self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

            with open(MachineIdentity.IDENTIFY_FILE, 'wb') as key_file:
                key_file.write(self._private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
        else:
            with open(MachineIdentity.IDENTIFY_FILE, 'rb') as key_file:
                self._private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                )

        if os.path.exists(MachineIdentity.API_KEY_FILE) and os.path.isfile(MachineIdentity.API_KEY_FILE):
            with open(MachineIdentity.API_KEY_FILE) as api_key_file:
                self.api_key = api_key_file.read()
        else:
            raise RuntimeError("No API Key has been configured for this machine.\n'"
                               "'Please add the api key in the specified file.",
                               MachineIdentity.API_KEY_FILE)

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
