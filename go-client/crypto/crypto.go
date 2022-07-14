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

func (k *Key) Sign(data []byte) ([]byte, error) {
	digest := sha256.Sum256(data)
	return rsa.SignPSS(rand.Reader, (*rsa.PrivateKey)(k), crypto.SHA256, digest[:],
		&rsa.PSSOptions{SaltLength: rsa.PSSSaltLengthAuto})
}
