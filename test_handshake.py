import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
import handshake as hs


@pytest.fixture(scope="module")
def exchange():
    group_file = Path(hs.__file__).with_name("ffdhe3072.pem")
    parameters = serialization.load_pem_parameters(group_file.read_bytes())
    public_values = [
        parameters.generate_private_key().public_key().public_numbers().y
        for _ in range(2)
    ]
    fields = [
        hs.LABEL, hs.GROUP, b"gateway", b"node",
        public_values[0].to_bytes(hs.WIDTH, "big"),
        public_values[1].to_bytes(hs.WIDTH, "big"),
        os.urandom(16), os.urandom(16),
    ]
    key = hs.new_signing_key()
    transcript = hs.encode_fields(fields)
    signature = hs.sign_transcript(key, b"gateway", transcript)
    return key, fields, transcript, signature


def test_valid_signature(exchange):
    key, fields, transcript, signature = exchange
    hs.verify_transcript(
        key.public_key(), b"gateway", transcript, signature
    )


def test_incorrect_rsa_key(exchange):
    key, fields, transcript, signature = exchange
    wrong_key = hs.new_signing_key().public_key()
    with pytest.raises(hs.HandshakeError, match="Invalid handshake signature"):
        hs.verify_transcript(wrong_key, b"gateway", transcript, signature)


def test_invalid_signature(exchange):
    key, fields, transcript, signature = exchange
    changed = bytes([signature[0] ^ 1]) + signature[1:]
    with pytest.raises(hs.HandshakeError, match="Invalid handshake signature"):
        hs.verify_transcript(key.public_key(), b"gateway", transcript, changed)


@pytest.mark.parametrize("index", [4, 5, 6, 7])
def test_changed_public_value_or_nonce(exchange, index):
    key, fields, transcript, signature = exchange
    changed = list(fields)
    value = bytearray(changed[index])
    value[-1] ^= 1
    changed[index] = bytes(value)
    with pytest.raises(hs.HandshakeError, match="Invalid handshake signature"):
        hs.verify_transcript(
            key.public_key(), b"gateway",
            hs.encode_fields(changed), signature
        )


def test_unexpected_identity(exchange):
    key, fields, transcript, signature = exchange
    changed = list(fields)
    changed[3] = b"stranger"
    transcript = hs.encode_fields(changed)
    signature = hs.sign_transcript(key, b"gateway", transcript)
    with pytest.raises(hs.HandshakeError, match="Unexpected peer identity"):
        hs.verify_transcript(
            key.public_key(), b"gateway", transcript, signature
        )


def test_reflected_handshake_role(exchange):
    key, fields, transcript, signature = exchange
    # Even with the same key, a gateway signature cannot act as a node.
    with pytest.raises(hs.HandshakeError, match="Invalid handshake signature"):
        hs.verify_transcript(key.public_key(), b"node", transcript, signature)


@pytest.mark.parametrize("damage", ["length", "truncate", "trailing"])
def test_malformed_transcript_rejected_before_hashing(exchange, monkeypatch, damage):
    key, fields, transcript, signature = exchange
    if damage == "length":
        malformed = b"\xff\xff\xff\xff" + transcript[4:]
        expected = "Truncated field"
    elif damage == "truncate":
        malformed = transcript[:-1]
        expected = "Truncated field"
    else:
        malformed = transcript + b"extra"
        expected = "Unexpected trailing bytes"

    def forbidden_hash(data):
        pytest.fail("Malformed transcript reached hashing")

    monkeypatch.setattr(hs, "sha256", forbidden_hash)
    with pytest.raises(hs.HandshakeError, match=expected):
        hs.verify_transcript(
            key.public_key(), b"gateway", malformed, signature
        )
