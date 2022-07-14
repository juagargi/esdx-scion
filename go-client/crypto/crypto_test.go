package crypto

import (
	"encoding/hex"
	"path"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestLoadKey(t *testing.T) {
	key, err := LoadKey(testData("broker.key"))
	require.NoError(t, err)
	require.NotNil(t, key)
	require.NotNil(t, key.toRsa())
}

func TestSign(t *testing.T) {
	key, err := LoadKey(testData("broker.key"))
	require.NoError(t, err)
	data := []byte("hello")
	signature, err := key.Sign(data)
	require.NoError(t, err)
	require.NotEmpty(t, signature)
	t.Log(hex.EncodeToString(signature))
}

func TestLoadCert(t *testing.T) {
	cert, err := LoadCert(testData("broker.crt"))
	require.NoError(t, err)
	t.Log(cert.Subject.CommonName)
	require.NotNil(t, cert)
	require.NotNil(t, cert.toX509())
	require.NotNil(t, cert.toRsaPublicKey())
}

func TestVerifySignature(t *testing.T) {
	key, err := LoadKey(testData("broker.key"))
	require.NoError(t, err)
	data := []byte("hello")
	signature, err := key.Sign(data)
	require.NoError(t, err)

	// verify signature:
	cert, err := LoadCert(testData("broker.crt"))
	require.NoError(t, err)
	err = cert.VerifySignature(data, signature)
	require.NoError(t, err)
	data = []byte("hello world")
	err = cert.VerifySignature(data, signature)
	require.Error(t, err)
	require.Equal(t, err, InvalidSignatureErr)
}

// testData returns the path to the filename in the test data directory
func testData(filename string) string {
	return path.Join("..", "..", "test_data", filename)
}
