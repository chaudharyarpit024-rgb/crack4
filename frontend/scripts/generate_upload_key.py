#!/usr/bin/env python3
import sys
import getpass
import datetime
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

def main():
    target_dir = Path(__file__).resolve().parent.parent
    keystore_path = target_dir / "upload-keystore.jks"
    pem_path = target_dir / "upload_certificate.pem"

    print("=" * 60)
    print("  Google Play Upload Key & Certificate Generator (No Java Required)")
    print("=" * 60)

    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        while True:
            password = getpass.getpass("Enter password for new keystore: ")
            if not password:
                print("Password cannot be empty.")
                continue
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords do not match. Please try again.\n")
                continue
            break

    print("\nGenerating 2048-bit RSA keypair and certificate...")

    # Generate RSA 2048 key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Build Self-Signed X.509 Certificate (validity: 10,000 days ~ 27 years)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Android Upload"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Crack"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Mobile App"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=10000))
        .sign(key, hashes.SHA256())
    )

    # Export PKCS12 (.jks / .p12) keystore with alias 'upload'
    p12_data = pkcs12.serialize_key_and_certificates(
        name=b"upload",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8"))
    )

    with open(keystore_path, "wb") as f:
        f.write(p12_data)

    # Export PEM certificate
    pem_data = cert.public_bytes(serialization.Encoding.PEM)
    with open(pem_path, "wb") as f:
        f.write(pem_data)

    print("\n Success! Generated:")
    print(f"  1. Keystore:     {keystore_path}")
    print(f"  2. Certificate:  {pem_path}")
    print(f"  Alias:          upload")
    print(f"  Password:       [SAVED AS SPECIFIED]")
    print("\nNext step: Upload 'upload_certificate.pem' to Google Play Console.")

if __name__ == "__main__":
    main()
