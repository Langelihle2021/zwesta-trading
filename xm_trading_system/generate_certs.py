#!/usr/bin/env python
import ssl
import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timedelta

# Generate private key
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Generate certificate
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"ZA"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"ZA"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"ZA"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Zwesta Trading"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"192.168.0.137"),
])

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365)
).add_extension(
    x509.SubjectAlternativeName([
        x509.DNSName(u"192.168.0.137"),
        x509.DNSName(u"localhost"),
    ]),
    critical=False,
).sign(private_key, hashes.SHA256(), default_backend())

# Write private key
with open("server.key", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

# Write certificate
with open("server.crt", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print("✓ SSL certificates generated: server.crt and server.key")
