from datetime import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.x509 import load_pem_x509_certificate, load_der_x509_certificate
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_der_private_key
from cryptography.hazmat.primitives.asymmetric import padding

import base64


def get_common_name(cert: x509.Certificate) -> str:
    l = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if len(l) != 1:
        raise ValueError(f"wrong number of common names. Expected 1 got {len(l)}")
    return l[0].value


def create_x509_name(
    country_name: str,
    organization: str,
    org_unit: str,
    common_name: str) -> x509.Name:

    return x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, org_unit),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])


def create_key(key_size: int=2048) ->rsa.RSAPrivateKey:
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

def create_certificate(
    issuer: x509.Name,
    subject: x509.Name,
    key: rsa.RSAPrivateKey,
    notbefore: datetime,
    notafter: datetime) -> x509.Certificate:

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        notbefore
    ).not_valid_after(
        notafter
    ).sign(key, hashes.SHA256())
    return cert


def certificate_to_pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def key_to_pem(key: rsa.RSAPrivateKey, password: bytes = None) -> str:
    algo = serialization.BestAvailableEncryption(password) if password is not None \
        else serialization.NoEncryption()

    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=algo,
    ).decode("ascii")


def load_certificate(data):
    """ data can either be bytes or string (it will be automatically converted) """
    if isinstance(data, str):
        data = data.encode("ascii")
    try:
        cert = load_der_x509_certificate(data)
    except ValueError:
        try:
            cert = load_pem_x509_certificate(data)
        except ValueError:
            raise ValueError("this does not look like a DER or PEM certificate")
    return cert


def load_key(data, password=None):
    """ data can either be bytes or string (it will be automatically converted) """
    if isinstance(data, str):
        data = data.encode("ascii")
    try:
        key = load_der_private_key(data, password=password)
    except (TypeError, ValueError):
        try:
            key = load_pem_private_key(data, password=password)
        except ValueError:
            raise ValueError("this does not look like a DER or PEM private key")
    return key


def signature_create(key: rsa.RSAPrivateKey, data: bytes) -> str:
    s = key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    # encode it in base64
    return base64.standard_b64encode(s).decode("ascii")


def signature_validate(cert: x509.Certificate, signature: str, data: bytes) -> None:
    # decode signature from base64
    try:
        s = base64.standard_b64decode(signature)
    except:
        raise ValueError("invalid signature")
    try:
        cert.public_key().verify(
            s,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
    except InvalidSignature:
        raise ValueError("invalid signature")
