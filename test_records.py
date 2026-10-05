import pytest
import secure_record as sr
from handshake import new_signing_key, run_handshake


@pytest.fixture(scope="module")
def session_keys():
    gateway_keys, node_keys = run_handshake(
        new_signing_key(), new_signing_key()
    )
    assert gateway_keys == node_keys
    return gateway_keys, node_keys


@pytest.fixture
def endpoints(session_keys):
    gateway_keys, node_keys = session_keys
    gateway_send, gateway_receive = sr.make_states(gateway_keys, "gateway")
    node_send, node_receive = sr.make_states(node_keys, "node")
    return gateway_send, gateway_receive, node_send, node_receive


def test_valid_handshake_and_bidirectional_messages(endpoints):
    gs, gr, ns, nr = endpoints
    for sequence in range(3):
        record = sr.seal(gs, b"READ notes.txt")
        assert sr.open_record(nr, record) == (1, b"READ notes.txt")
        reply = sr.seal(ns, b"OK", message_type=2)
        assert sr.open_record(gr, reply) == (2, b"OK")
        assert gs.sequence == nr.sequence == sequence + 1
        assert ns.sequence == gr.sequence == sequence + 1


@pytest.mark.parametrize("target", ["ciphertext", "header", "iv", "tag"])
def test_tampering_rejected_before_decryption(endpoints, monkeypatch, target):
    gs, gr, ns, nr = endpoints
    original = sr.seal(gs, b"READ notes.txt")
    changed = bytearray(original)
    offsets = {
        "ciphertext": sr.HEADER.size + sr.IV_SIZE,
        "header": 10,
        "iv": sr.HEADER.size,
        "tag": len(changed) - 1,
    }
    changed[offsets[target]] ^= 1

    def forbidden_cipher(*args, **kwargs):
        pytest.fail("Decryption attempted before rejecting a bad MAC")

    with monkeypatch.context() as patch:
        patch.setattr(sr, "Cipher", forbidden_cipher)
        with pytest.raises(sr.RecordError, match="Invalid record MAC"):
            sr.open_record(nr, bytes(changed))

    assert nr.sequence == 0
    assert sr.open_record(nr, original) == (1, b"READ notes.txt")


def test_replayed_record(endpoints):
    gs, gr, ns, nr = endpoints
    record = sr.seal(gs, b"READ notes.txt")
    sr.open_record(nr, record)
    with pytest.raises(sr.RecordError, match="Unexpected sequence"):
        sr.open_record(nr, record)
    assert nr.sequence == 1


def test_reflected_record(endpoints):
    gs, gr, ns, nr = endpoints
    record = sr.seal(gs, b"READ notes.txt")
    with pytest.raises(sr.RecordError, match="Invalid record MAC"):
        sr.open_record(gr, record)
    assert gr.sequence == 0


def test_out_of_order_record(endpoints):
    gs, gr, ns, nr = endpoints
    first = sr.seal(gs, b"FIRST")
    second = sr.seal(gs, b"SECOND")
    with pytest.raises(sr.RecordError, match="Unexpected sequence"):
        sr.open_record(nr, second)
    assert nr.sequence == 0
    assert sr.open_record(nr, first) == (1, b"FIRST")
    assert sr.open_record(nr, second) == (1, b"SECOND")
