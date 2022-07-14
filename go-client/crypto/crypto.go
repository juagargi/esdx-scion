package crypto

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"io/ioutil"
	"log"
)

type Key rsa.PrivateKey

type Cert x509.Certificate

var InvalidSignatureErr = fmt.Errorf("invalid signature")

func LoadKey(filename string) (*Key, error) {
	data, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, fmt.Errorf("couldn't load key: %w", err)
	}
	pemBlock, _ := pem.Decode(data)
	if pemBlock == nil {
		return nil, fmt.Errorf("invalid PEM key")
	}
	if pemBlock.Type != "PRIVATE KEY" {
		log.Fatalf("invalid PEM type: %s", pemBlock.Type)
	}

	keyGeneric, err := x509.ParsePKCS8PrivateKey(pemBlock.Bytes)
	if err != nil {
		return nil, fmt.Errorf("error load loading pem key: %w", err)
	}
	key, ok := keyGeneric.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("key is not a RSA private key but %T", key)
	}
	return (*Key)(key), nil
}

func (k *Key) toRsa() *rsa.PrivateKey {
	return (*rsa.PrivateKey)(k)
}

func (k *Key) Sign(data []byte) ([]byte, error) {
	digest := sha256.Sum256(data)
	return rsa.SignPSS(rand.Reader, k.toRsa(), crypto.SHA256, digest[:],
		&rsa.PSSOptions{SaltLength: rsa.PSSSaltLengthAuto})
}

func LoadCert(filename string) (*Cert, error) {
	data, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, fmt.Errorf("couldn't load certificate: %w", err)
	}
	pemBlock, _ := pem.Decode(data)
	if pemBlock == nil {
		return nil, fmt.Errorf("invalid PEM certificate")
	}
	if pemBlock.Type != "CERTIFICATE" {
		return nil, fmt.Errorf("invalid PEM type: %s", pemBlock.Type)
	}
	c, err := x509.ParseCertificate(pemBlock.Bytes)
	if err != nil {
		return nil, fmt.Errorf("error parsing certificate: %w", err)
	}
	return (*Cert)(c), nil
}

func (c *Cert) toX509() *x509.Certificate {
	return (*x509.Certificate)(c)
}

func (c *Cert) toRsaPublicKey() *rsa.PublicKey {
	return c.toX509().PublicKey.(*rsa.PublicKey)
}

func (c *Cert) VerifySignature(data, signature []byte) error {
	digest := sha256.Sum256(data)
	err := rsa.VerifyPSS(c.toRsaPublicKey(), crypto.SHA256, digest[:], signature,
		&rsa.PSSOptions{SaltLength: rsa.PSSSaltLengthAuto})
	if err != nil {
		return InvalidSignatureErr
	}
	return nil
}
