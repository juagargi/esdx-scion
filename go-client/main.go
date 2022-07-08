package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"time"

	pb "esdx_scion/market"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

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
