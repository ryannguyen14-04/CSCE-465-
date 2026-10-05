import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

VERSION = 1
G2N = 0
N2G = 1
HEADER = struct.Struct(">BBQBI")
TAG_SIZE = 32
IV_SIZE = 16
MAX_SEQUENCE = (1 << 64) - 1


class RecordError(ValueError):
    pass


@dataclass
class RecordState:
    enc_key: bytes
    mac_key: bytes
    session_id: bytes
    direction: int
    sequence: int = 0

    def __post_init__(self):
        if len(self.enc_key) != 32 or len(self.mac_key) != 32:
            raise RecordError("Keys must be 32 bytes")
        if len(self.session_id) != 8:
            raise RecordError("Session ID must be 8 bytes")
        if self.direction not in (G2N, N2G):
            raise RecordError("Invalid direction")


def make_states(keys, role):
    # Return separate sending and receiving states for this endpoint.
    if role == "gateway":
        outgoing, incoming = ("g2n", G2N), ("n2g", N2G)
    elif role == "node":
        outgoing, incoming = ("n2g", N2G), ("g2n", G2N)
    else:
        raise RecordError("Unknown role")

    def build(spec):
        prefix, direction = spec
        return RecordState(
            keys[prefix + "_enc"],
            keys[prefix + "_mac"],
            keys["session_id"],
            direction,
        )

    return build(outgoing), build(incoming)


def seal(state, plaintext, message_type=1):
    if not isinstance(plaintext, bytes):
        raise RecordError("Plaintext must be bytes")
    if not 0 <= message_type <= 255:
        raise RecordError("Invalid message type")
    if len(plaintext) > 0xffffffff:
        raise RecordError("Message too long")
    if not 0 <= state.sequence <= MAX_SEQUENCE:
        raise RecordError("Sequence exhausted; establish a new session")

    sequence = state.sequence
    # Reserve the sequence before encryption so errors cannot reuse it.
    state.sequence += 1
    iv = state.session_id + sequence.to_bytes(8, "big")
    header = HEADER.pack(
        VERSION, state.direction, sequence, message_type, len(plaintext)
    )

    worker = Cipher(
        algorithms.AES(state.enc_key), modes.CTR(iv)
    ).encryptor()
    ciphertext = worker.update(plaintext) + worker.finalize()

    signer = hmac.HMAC(state.mac_key, hashes.SHA256())
    signer.update(header + iv + ciphertext)
    tag = signer.finalize()
    return header + iv + ciphertext + tag


def open_record(state, record):
    if not isinstance(record, bytes):
        raise RecordError("Record must be bytes")

    minimum = HEADER.size + IV_SIZE + TAG_SIZE
    if len(record) < minimum:
        raise RecordError("Truncated record")

    header = record[:HEADER.size]
    version, direction, sequence, message_type, length = HEADER.unpack(header)

    if len(record) != minimum + length:
        raise RecordError("Record length mismatch")

    iv = record[HEADER.size:HEADER.size + IV_SIZE]
    ciphertext = record[HEADER.size + IV_SIZE:-TAG_SIZE]
    tag = record[-TAG_SIZE:]

    # Authenticate all transmitted fields before any decryption.
    verifier = hmac.HMAC(state.mac_key, hashes.SHA256())
    verifier.update(header + iv + ciphertext)
    try:
        verifier.verify(tag)
    except InvalidSignature as error:
        raise RecordError("Invalid record MAC") from error

    if version != VERSION:
        raise RecordError("Unsupported version")
    if direction != state.direction:
        raise RecordError("Wrong direction")
    if not 0 <= state.sequence <= MAX_SEQUENCE:
        raise RecordError("Sequence exhausted")
    if sequence != state.sequence:
        raise RecordError("Unexpected sequence: replay or out-of-order record")

    expected_iv = state.session_id + sequence.to_bytes(8, "big")
    if iv != expected_iv:
        raise RecordError("Unexpected IV")

    worker = Cipher(
        algorithms.AES(state.enc_key), modes.CTR(iv)
    ).decryptor()
    plaintext = worker.update(ciphertext) + worker.finalize()
    state.sequence += 1
    return message_type, plaintext
