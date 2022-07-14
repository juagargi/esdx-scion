package main

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"time"

	pb "esdx_scion/market"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type deletemeRand struct{}

func (deletemeRand) Read(buff []byte) (int, error) {
	rep := bytes.Repeat([]byte("b"), len(buff))
	fmt.Printf("len(buff)=%d, rand=%d\n", len(buff), len(rep))
	return copy(buff, rep), nil
}

func main() {
	ctx, cancelF := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancelF()

	addr := flag.String("addr", "localhost:50051", "the address to connect to")
	flag.Parse()
	conn, err := grpc.Dial(*addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}
	defer conn.Close()

	fmt.Println("hello there")
	//
	//
	// load key
	data, err := ioutil.ReadFile("../test_data/1-ff00_0_111.key")
	if err != nil {
		log.Fatalf("couldn't load key: %v", err)
	}
	pemBlock, _ := pem.Decode(data)
	if pemBlock == nil {
		log.Fatal("invalid PEM key")
	}
	if pemBlock.Type != "PRIVATE KEY" {
		log.Fatalf("invalud PEM type: %s", pemBlock.Type)
	}
	var key *rsa.PrivateKey
	{
		keyGeneric, err := x509.ParsePKCS8PrivateKey(pemBlock.Bytes)
		if err != nil {
			log.Fatalf("error load loading pem key: %v", err)
		}
		key = keyGeneric.(*rsa.PrivateKey)
	}
	data = []byte("hello")
	dataHashed := sha256.Sum256(data)
	// signature, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, dataHashed[:])
	// signature, err := rsa.SignPKCS1v15(rand.Reader, key, 0, dataHashed[:])
	// signature, err := rsa.SignPKCS1v15(deletemeRand{}, key, crypto.SHA256, dataHashed[:])
	signature, err := rsa.SignPSS(rand.Reader, key, crypto.SHA256, dataHashed[:], &rsa.PSSOptions{
		SaltLength: rsa.PSSSaltLengthAuto,
		// Hash: crypto.mgf,
	})
	// signature, err := key.Sign(rand.Reader, data, &rsa.PSSOptions{})
	if err != nil {
		log.Fatalf("cannot sign: %v", err)
	}
	fmt.Println(hex.EncodeToString(signature))

	// prepare data
	// create signature

	//
	//
	//
	//
	//
	//
	//
	if 4%5 != 0 {
		os.Exit(0)
	}
	c := pb.NewMarketControllerClient(conn)
	r, err := c.ListOffers(ctx, &pb.ListRequest{})
	if err != nil {
		log.Fatalf("not listening: %v", err)
	}
	offers := make([]*pb.Offer, 0)
	for {
		o, err := r.Recv()
		if err != nil && err != io.EOF {
			log.Fatalf("listing offers: %v", err)
		}
		offers = append(offers, o)
		if err == io.EOF {
			break
		}
	}
	fmt.Printf("Got %d offers\n", len(offers))
	offer := offers[0]
	req := &pb.PurchaseRequest{
		Offer:      offer,
		BuyerIaid:  "1-ff00:0:111",
		StartingOn: offer.Specs.Notbefore,
		BwProfile:  "1",
		Signature:  []byte{},
	}
	contract, err := c.Purchase(ctx, req)
	if err != nil {
		log.Fatalf("buying offer: %v", err)
	}
	_ = contract
}
