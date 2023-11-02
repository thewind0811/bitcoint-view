import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from errors.misc import UnableToDecryptRemoteData

AES_BLOCK_SIZE = 16


def encrypt(key: bytes, source: bytes) -> bytes:
    assert isinstance(key, bytes), "key must be bytes"
    assert isinstance(source, bytes), "source must be bytes"
    digest = hashes.Hash(hashes.SHA256())
    digest.update(key)
    key = digest.finalize()
    iv = os.urandom(AES_BLOCK_SIZE)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padding = AES_BLOCK_SIZE - len(source) % AES_BLOCK_SIZE
    source += bytes([padding]) * padding
    data = iv + (encryptor.update(source) + encryptor.finalize())
    return data

def decrypt(key: bytes, source: bytes) -> bytes:
    assert isinstance(key, bytes), "key must be bytes"
    assert isinstance(source, bytes), "source must be bytes"
    digest = hashes.Hash(hashes.SHA256())
    digest.update(key)
    key = digest.finalize()
    iv = source[:AES_BLOCK_SIZE]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()

    data = source[AES_BLOCK_SIZE:]
    data = decryptor.update(data)
    padding = data[-1]
    if data[-padding:] != bytes([padding]) * padding:
        raise UnableToDecryptRemoteData(
            'Invalid padding when decrypting the DB data we received from the server. '
            'Are you using a new user and if yes have you used the same password as before? '
            'If you have then please open a bug report.',
        )

def sha3(data: bytes) -> bytes:
    digest = hashes.Hash(hashes.SHA3_256())
    digest.update(data)
    return digest.finalize()



