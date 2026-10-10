import shutil
import subprocess

import pytest

from openpicture import ed25519

# RFC 8032 §7.1 test vectors.
_VECTORS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
]


@pytest.mark.parametrize("sk,pk,msg,sig", _VECTORS)
def test_rfc8032_vectors_pure_python(sk, pk, msg, sig):
    sk_b, pk_b, msg_b, sig_b = (bytes.fromhex(x) for x in (sk, pk, msg, sig))
    assert ed25519._py_public_key(sk_b) == pk_b
    assert ed25519._py_sign(sk_b, msg_b) == sig_b
    assert ed25519._py_verify(pk_b, msg_b, sig_b)
    assert not ed25519._py_verify(pk_b, msg_b + b"x", sig_b)
    bad = bytearray(sig_b)
    bad[0] ^= 1
    assert not ed25519._py_verify(pk_b, msg_b, bytes(bad))


@pytest.mark.parametrize("sk,pk,msg,sig", _VECTORS)
def test_rfc8032_vectors_active_backend(sk, pk, msg, sig):
    sk_b, pk_b, msg_b, sig_b = (bytes.fromhex(x) for x in (sk, pk, msg, sig))
    assert ed25519.public_key(sk_b) == pk_b
    assert ed25519.sign(sk_b, msg_b) == sig_b
    assert ed25519.verify(pk_b, msg_b, sig_b)


def test_bad_lengths_are_false_not_exceptions():
    assert ed25519.verify(b"\0" * 31, b"", b"\0" * 64) is False
    assert ed25519.verify(b"\0" * 32, b"", b"\0" * 63) is False


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not on PATH")
def test_interop_with_openssl(tmp_path):
    """A signature we make verifies with openssl, and vice versa."""
    sk = ed25519.generate_secret()
    pk = ed25519.public_key(sk)
    msg = b"open picture intelligence"
    # PKCS#8 wrapper for a raw Ed25519 private key (RFC 8410).
    pkcs8 = bytes.fromhex("302e020100300506032b657004220420") + sk
    spki = bytes.fromhex("302a300506032b6570032100") + pk
    (tmp_path / "sk.der").write_bytes(pkcs8)
    (tmp_path / "pk.der").write_bytes(spki)
    (tmp_path / "msg").write_bytes(msg)
    (tmp_path / "sig").write_bytes(ed25519.sign(sk, msg))
    r = subprocess.run(
        ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(tmp_path / "pk.der"),
         "-keyform", "DER", "-rawin", "-in", str(tmp_path / "msg"),
         "-sigfile", str(tmp_path / "sig")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    r = subprocess.run(
        ["openssl", "pkeyutl", "-sign", "-inkey", str(tmp_path / "sk.der"),
         "-keyform", "DER", "-rawin", "-in", str(tmp_path / "msg"),
         "-out", str(tmp_path / "sig2")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert ed25519.verify(pk, msg, (tmp_path / "sig2").read_bytes())
