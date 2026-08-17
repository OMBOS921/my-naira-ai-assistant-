"""
Cybersecurity & Cryptography Domain Generator for Dataset A.
Generates comprehensive technical prose on symmetric/asymmetric encryption, hashing, PKI, authentication, and application security.
"""

from __future__ import annotations

from typing import Any


def get_security_crypto_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "security",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Cybersecurity and cryptography engineering exposition",
            },
        })

    add(
        "sem_sec_001",
        "Symmetric encryption algorithms utilize the identical shared secret key for both plaintext encryption and ciphertext decryption. The Advanced Encryption Standard (AES) is the gold standard block cipher, operating on 128-bit blocks with key lengths of 128, 192, or 256 bits through repeated substitution-permutation network rounds (SubBytes, ShiftRows, MixColumns, AddRoundKey). AES in Galois/Counter Mode (AES-GCM) provides Authenticated Encryption with Associated Data (AEAD), guaranteeing both high-speed confidentiality and cryptographic data integrity verification in hardware.",
        "Symmetric block ciphers, AES-GCM, and AEAD authenticated encryption",
    )

    add(
        "sem_sec_002",
        "Asymmetric (public-key) cryptography uses mathematically linked keypairs consisting of a public key (openly distributed) and a private key (kept strictly secret). In the RSA cryptosystem, security is grounded in the computational intractability of factoring the product of two large prime numbers. In Elliptic Curve Cryptography (ECC, such as Ed25519 and ECDSA over secp256k1), security relies on the hardness of the Elliptic Curve Discrete Logarithm Problem (ECDLP), achieving equivalent cryptographic security to RSA with significantly smaller key sizes and lower computational overhead.",
        "Asymmetric cryptography (RSA vs Elliptic Curve Cryptography ECDSA/Ed25519)",
    )

    add(
        "sem_sec_003",
        "Cryptographic hash functions are deterministic algorithms that map arbitrary-length input byte streams to fixed-size bit strings (digests) satisfying three core security properties: Pre-image resistance (computationally infeasible to find input x given hash h(x)), Second pre-image resistance (infeasible to find a distinct input y such that h(x) = h(y)), and Collision resistance (infeasible to find any two arbitrary inputs a and b such that h(a) = h(b)). Modern secure hash standards include SHA-256, SHA-3 (Keccak), and BLAKE3.",
        "Cryptographic hash function properties (Collision resistance, SHA-256, BLAKE3)",
    )

    add(
        "sem_sec_004",
        "Password storage requires specialized, computationally expensive key derivation functions (KDFs) designed to resist high-speed GPU and ASIC brute-force dictionary attacks. General-purpose cryptographic hashes like MD5 and SHA-256 are dangerously fast and inappropriate for passwords. In contrast, modern password hashing standards—such as Argon2id (the winner of the Password Hashing Competition), bcrypt, and scrypt—incorporate configurable memory-hardness, CPU iteration counts, and salt parameters to defeat rainbow tables and parallelized hardware crackers.",
        "Password hashing best practices (Argon2id, bcrypt, memory hardness)",
    )

    add(
        "sem_sec_005",
        "Public Key Infrastructure (PKI) manages digital certificates to secure network communications via X.509 standards. A Certificate Authority (CA) signs a digital certificate that binds a subject's domain identity to their public key. When a client connects via HTTPS, it validates the certificate against its trusted root store, verifying the digital signature, expiration dates, Subject Alternative Names (SAN), and checking revocation status via Online Certificate Status Protocol (OCSP) stapling.",
        "Public Key Infrastructure (PKI), Certificate Authorities, and X.509 validation",
    )

    add(
        "sem_sec_006",
        "SQL Injection (SQLi) occurs when untrusted user input is directly concatenated into dynamic SQL query strings, allowing an attacker to manipulate query syntax and execute unauthorized database commands. SQLi vulnerabilities permit attackers to bypass authentication, extract sensitive database contents, modify records, or execute operating system commands. The definitive defense is using Parameterized Queries (Prepared Statements) with bound parameters, separating user data from executable SQL syntax.",
        "SQL Injection vulnerability mechanics and Prepared Statements remediation",
    )

    add(
        "sem_sec_007",
        "Cross-Site Scripting (XSS) is an injection vulnerability wherein malicious JavaScript scripts are injected into trusted web applications. Stored XSS occurs when malicious scripts are permanently stored on the server (e.g., in a comments database) and executed whenever other users view the page. Reflected XSS occurs when input from a URL parameter is immediately rendered into the response without sanitization. DOM-based XSS executes entirely within client-side JavaScript. Mitigations include context-aware HTML entity encoding, Content Security Policy (CSP) headers, and HttpOnly cookies.",
        "Cross-Site Scripting (Stored, Reflected, DOM) and CSP defenses",
    )

    add(
        "sem_sec_008",
        "OAuth 2.0 is an industry-standard authorization framework that enables third-party applications to obtain limited access to a user's HTTP resources without sharing user credentials. In the Authorization Code Flow with PKCE (Proof Key for Code Exchange), the client creates a cryptographic code verifier and code challenge, redirects the user to the Authorization Server, receives a temporary authorization code upon user consent, and exchanges the code alongside the verifier for a scoped JSON Web Token (JWT) access token.",
        "OAuth 2.0 Authorization Code Flow with PKCE and token scopes",
    )

    return samples
