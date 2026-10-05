import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import dh, padding, rsa

LABEL = b"CSCE465-HS-v2"
GROUP = b"ffdhe3072"
WIDTH = 384


class HandshakeError(ValueError):
    pass


def sha256(data):
    worker = hashes.Hash(hashes.SHA256())
    worker.update(data)
    return worker.finalize()


def mac(key, data):
    worker = hmac.HMAC(key, hashes.SHA256())
    worker.update(data)
    return worker.finalize()


def encode_fields(fields):
    return b"".join(
        len(field).to_bytes(4, "big") + field
        for field in fields
    )


def parse_transcript(data):
    # Exactly eight fields; reject truncation and trailing bytes.
    fields = []
    position = 0
    for _ in range(8):
        if position + 4 > len(data):
            raise HandshakeError("Missing field length")
        size = int.from_bytes(data[position:position + 4], "big")
        position += 4
        if position + size > len(data):
            raise HandshakeError("Truncated field")
        fields.append(data[position:position + size])
        position += size

    if position != len(data):
        raise HandshakeError("Unexpected trailing bytes")
    if fields[0] != LABEL or fields[1] != GROUP:
        raise HandshakeError("Wrong protocol or group")
    if not fields[2] or not fields[3]:
        raise HandshakeError("Missing identity")
    if len(fields[4]) != WIDTH or len(fields[5]) != WIDTH:
        raise HandshakeError("Wrong DH public value length")
    if len(fields[6]) != 16 or len(fields[7]) != 16:
        raise HandshakeError("Wrong nonce length")
    return fields


def signature_padding():
    return padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,
    )


def sign_transcript(signing_key, role, transcript):
    parse_transcript(transcript)
    if role not in (b"gateway", b"node"):
        raise HandshakeError("Unknown signing role")
    return signing_key.sign(
        role + sha256(transcript),
        signature_padding(),
        hashes.SHA256(),
    )


def verify_transcript(peer_key, peer_role, transcript, signature,
                      expected_gateway=b"gateway", expected_node=b"node"):
    fields = parse_transcript(transcript)
    if fields[2] != expected_gateway or fields[3] != expected_node:
        raise HandshakeError("Unexpected peer identity")
    if peer_role not in (b"gateway", b"node"):
        raise HandshakeError("Unexpected peer role")
    try:
        peer_key.verify(
            signature,
            peer_role + sha256(transcript),
            signature_padding(),
            hashes.SHA256(),
        )
    except InvalidSignature as error:
        raise HandshakeError("Invalid handshake signature") from error


def derive_keys(shared_secret, transcript):
    parse_transcript(transcript)
    if len(shared_secret) > WIDTH:
        raise HandshakeError("Invalid shared secret length")
    z = shared_secret.rjust(WIDTH, b"\x00")
    th = sha256(transcript)
    master = sha256(b"CSCE465-KDF-v1" + z + th)
    return {
        "g2n_enc": mac(master, b"gateway-to-node encryption" + th),
        "g2n_mac": mac(master, b"gateway-to-node MAC" + th),
        "n2g_enc": mac(master, b"node-to-gateway encryption" + th),
        "n2g_mac": mac(master, b"node-to-gateway MAC" + th),
        "session_id": mac(master, b"session identifier" + th)[:8],
    }


def new_signing_key():
    return rsa.generate_private_key(
        public_exponent=65537, key_size=3072
    )


def run_handshake(gateway_signing_key, node_signing_key):
    group_file = Path(__file__).with_name("ffdhe3072.pem")
    parameters = serialization.load_pem_parameters(group_file.read_bytes())
    if not isinstance(parameters, dh.DHParameters):
        raise HandshakeError("Expected DH parameters")
    numbers = parameters.parameter_numbers()
    if numbers.p.bit_length() != 3072:
        raise HandshakeError("Expected a 3072-bit group")

    # Trusted identity-to-key bindings, provisioned before the exchange.
    trusted_node_key = node_signing_key.public_key()
    trusted_gateway_key = gateway_signing_key.public_key()

    # New ephemeral keys and nonces for every session.
    gateway_private = parameters.generate_private_key()
    node_private = parameters.generate_private_key()
    gateway_nonce = os.urandom(16)
    node_nonce = os.urandom(16)

    gateway_public = gateway_private.public_key().public_numbers().y
    node_public = node_private.public_key().public_numbers().y

    transcript = encode_fields([
        LABEL,
        GROUP,
        b"gateway",
        b"node",
        gateway_public.to_bytes(WIDTH, "big"),
        node_public.to_bytes(WIDTH, "big"),
        gateway_nonce,
        node_nonce,
    ])
    fields = parse_transcript(transcript)

    gateway_signature = sign_transcript(
        gateway_signing_key, b"gateway", transcript
    )
    node_signature = sign_transcript(
        node_signing_key, b"node", transcript
    )

    # Each side verifies the peer against its expected role and identity.
    verify_transcript(
        trusted_node_key, b"node", transcript, node_signature
    )
    verify_transcript(
        trusted_gateway_key, b"gateway", transcript, gateway_signature
    )

    # Use only the authenticated public values for key establishment.
    try:
        received_node_public = dh.DHPublicNumbers(
            int.from_bytes(fields[5], "big"), numbers
        ).public_key()
        received_gateway_public = dh.DHPublicNumbers(
            int.from_bytes(fields[4], "big"), numbers
        ).public_key()
        gateway_secret = gateway_private.exchange(received_node_public)
        node_secret = node_private.exchange(received_gateway_public)
    except ValueError as error:
        raise HandshakeError("Invalid DH public value") from error

    gateway_keys = derive_keys(gateway_secret, transcript)
    node_keys = derive_keys(node_secret, transcript)
    if gateway_keys != node_keys:
        raise HandshakeError("Session keys do not match")
    return gateway_keys, node_keys


def main():
    # These identity keys persist across both simulated sessions.
    gateway_signing_key = new_signing_key()
    node_signing_key = new_signing_key()

    gateway_keys, node_keys = run_handshake(
        gateway_signing_key, node_signing_key
    )
    print("Both peer signatures verified.")
    print("Gateway and node derived identical keys:", gateway_keys == node_keys)
    print("Session ID:", gateway_keys["session_id"].hex())

    names = ("g2n_enc", "g2n_mac", "n2g_enc", "n2g_mac")
    distinct = len({gateway_keys[name] for name in names}) == 4
    assert distinct
    print("Four distinct encryption/MAC keys:", distinct)

    next_keys, _ = run_handshake(gateway_signing_key, node_signing_key)
    fresh = next_keys["session_id"] != gateway_keys["session_id"]
    assert fresh
    print("Second session has a fresh session ID:", fresh)


if __name__ == "__main__":
    main()


