"""Offline build smoke check: no ACME requests, DNS writes or cloud credentials."""
import importlib
from importlib import metadata, util
import os
from pathlib import Path
import re
import sys
from unittest.mock import patch


def main():
    root = Path(__file__).resolve().parent
    target = root / "python"
    if not target.is_dir():
        raise RuntimeError("Build dependencies into cert-generator/python first")
    sys.path.insert(0, str(target))
    # A full lock prevents old Certbot from importing newer, incompatible ACME,
    # josepy or pyOpenSSL packages from a runtime or a previous pip -t build.
    for line in (root / "requirements.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, expected = line.strip().split("==")
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        distribution = metadata.distribution(normalized)
        if distribution.version != expected:
            raise RuntimeError(f"{name}: expected {expected}, found {distribution.version}")
        if Path(distribution.locate_file("")).resolve() != target.resolve():
            raise RuntimeError(f"{name} was loaded outside bundled python/")

    for name in ("certbot.main", "acme.crypto_util", "josepy", "OpenSSL.crypto"):
        importlib.import_module(name)
    # The DNS wait helper must also be present in a hand-uploaded source package.
    importlib.import_module("dns_propagation")

    # Import the actual FC entrypoint with dummy credentials, blocking all network
    # access so this check cannot issue a certificate or modify a DNS record.
    with patch.dict(os.environ, {
        "ALIBABA_CLOUD_ACCESS_KEY_ID": "offline-smoke-check",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "offline-smoke-check",
        "ALIBABA_CLOUD_SECURITY_TOKEN": "offline-smoke-check",
        "FC_REGION": "ap-southeast-1",
    }), patch("socket.socket.connect", side_effect=RuntimeError("Network disabled")), \
            patch("socket.getaddrinfo", side_effect=RuntimeError("Network disabled")):
        spec = util.spec_from_file_location("fc_certbot_smoke_entrypoint", root / "index.py")
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not callable(module.handler):
            raise RuntimeError("FC handler is unavailable")

        from acme import crypto_util
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        csr = x509.load_pem_x509_csr(crypto_util.make_csr(pem, ["fc-certbot-smoke.invalid"]))
        names = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        if not csr.is_signature_valid or names.get_values_for_type(x509.DNSName) != ["fc-certbot-smoke.invalid"]:
            raise RuntimeError("ACME CSR generation failed")

    for name in ("certbot", "acme", "josepy", "pyOpenSSL", "cryptography"):
        print(f"{name}={metadata.version(name)}")
    print("FC entrypoint import and offline CSR generation passed")


if __name__ == "__main__":
    main()
