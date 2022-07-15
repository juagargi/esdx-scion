package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"time"

	"esdx_scion/crypto"
	pb "esdx_scion/market"
	"esdx_scion/serialize"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	os.Exit(mainFunc())
}

func mainFunc() int {
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

	// load key
	key, err := crypto.LoadKey("../test_data/1-ff00_0_111.key")
	if err != nil {
		log.Fatalf("loading key: %v", err)
	}
	certBroker, err := crypto.LoadCert("../test_data/broker.crt")
	if err != nil {
		log.Fatalf("loading broker certificate: %v", err)
	}

	c := pb.NewMarketControllerClient(conn)
	r, err := c.ListOffers(ctx, &pb.ListRequest{})
	if err != nil {
		log.Fatalf("not listing: %v", err)
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
	// prepare data
	data := serialize.SerializePurchaseOrder(req)
	// fmt.Printf("deleteme purchase order serialized: %s\n", hex.EncodeToString(data))
	// create signature
	signature, err := key.Sign(data)
	if err != nil {
		log.Fatalf("cannot sign purchaser order: %v", err)
	}
	req.Signature = signature

	contract, err := c.Purchase(ctx, req)
	if err != nil {
		log.Fatalf("buying offer: %v", err)
	}
	data = serialize.SerializeContract(contract)
	err = certBroker.VerifySignature(data, contract.ContractSignature)
	if err != nil {
		log.Fatalf("contract signature: %v", err)
	}
	return 0
}
