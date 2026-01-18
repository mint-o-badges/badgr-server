from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base64
import os

secret_key = "super_secret"

# Generate Ed25519 private key encrypted with this SECRET_KEY
private_key = ed25519.Ed25519PrivateKey.generate()
encrypted_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.BestAvailableEncryption(
        secret_key.encode('utf-8')  # Convert string to bytes
    )
).decode('utf-8')

print("\nEncrypted Private Key:")
print(encrypted_pem)
