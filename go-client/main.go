package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"sync"
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
	nClients := flag.Int("num", 1, "number of clients")
	flag.Parse()

	times := make(map[int]time.Duration)
	for i := 0; i <= *nClients; i += 10 {
		t0 := time.Now()
		runNClients(ctx, i, *addr)
		times[i] = time.Since(t0)
	}
	for i, d := range times {
		fmt.Printf("%d: %v\n", i, d.Seconds())
	}
	return 0
}

func runNClients(ctx context.Context, n int, serverAddr string) {
	wg := sync.WaitGroup{}
	wg.Add(n)
	fmt.Printf("%d ", n)
	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			client(ctx, serverAddr)
			fmt.Printf(".")
		}()
	}
	wg.Wait()
	fmt.Println()
}

func client(ctx context.Context, serverAddr string) {
	conn, err := grpc.Dial(serverAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}
	defer conn.Close()

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
	for tries := 0; tries < 100; tries++ {
		t0 := time.Now()
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
			if err == io.EOF {
				break
			}
			offers = append(offers, o)
		}
		// fmt.Printf("deleteme time to list: %s\n", time.Since(t0))
		t0 = time.Now()
		// fmt.Printf("Got %d offers:\n", len(offers))
		// for _, o := range offers {
		// 	fmt.Printf("ID: %d BW: %s\n", o.Id, o.Specs.BwProfile)
		// }
		// fmt.Println()
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
		// create signature
		signature, err := key.Sign(data)
		if err != nil {
			log.Fatalf("cannot sign purchaser order: %v", err)
		}
		req.Signature = signature

		contract, err := c.Purchase(ctx, req)
		// fmt.Printf("deleteme time to buy: %s\n", time.Since(t0))
		t0 = time.Now()
		if err != nil {
			// fmt.Printf("buying offer: %v\n", err)
			continue
		}
		data = serialize.SerializeContract(contract)
		err = certBroker.VerifySignature(data, contract.ContractSignature)
		if err != nil {
			log.Fatalf("contract signature: %v", err)
		}
		// fmt.Printf("deleteme time to verify contract: %s\n", time.Since(t0))
		_ = t0
		return
	}
	log.Fatalln("too many tries")
}
