import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MESSAGE = b'{"action":"READ","path":"notes.txt"}'


def encrypt(key, iv, plaintext):
    worker = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    return worker.update(plaintext) + worker.finalize()


def receive(key, iv, ciphertext):
    worker = Cipher(algorithms.AES(key), modes.CTR(iv)).decryptor()
    plaintext = worker.update(ciphertext) + worker.finalize()
    print("Receiver processed:", plaintext.decode())
    return plaintext


def relay(ciphertext, offset, original, replacement):
    # The relay knows the command format, but receives no key.
    changed = bytearray(ciphertext)
    for i in range(len(original)):
        changed[offset + i] ^= original[i] ^ replacement[i]
    return bytes(changed)


def main():
    key = os.urandom(32)
    iv = os.urandom(16)
    ciphertext = encrypt(key, iv, MESSAGE)

    print("=== Original command ===")
    assert receive(key, iv, ciphertext) == MESSAGE

    original = b"READ"
    replacement = b"LIST"
    offset = MESSAGE.index(original)
    modified = relay(ciphertext, offset, original, replacement)

    print("\n=== Relay changes READ to LIST without the key ===")
    delta = bytes(a ^ b for a, b in zip(original, replacement))
    print("READ bytes:          ", original.hex())
    print("LIST bytes:          ", replacement.hex())
    print("READ XOR LIST:       ", delta.hex())
    print("Original cipher bytes:", ciphertext[offset:offset + 4].hex())
    print("Modified cipher bytes:", modified[offset:offset + 4].hex())
    print("Relation: C' = C XOR READ XOR LIST")
    assert receive(key, iv, modified) == MESSAGE.replace(original, replacement)

    print("\n=== Replay: identical ciphertext accepted twice ===")
    first = receive(key, iv, ciphertext)
    second = receive(key, iv, ciphertext)
    assert first == second == MESSAGE
    print("Replay accepted: no sequence tracking or replay detection.")


if __name__ == "__main__":
    main()
