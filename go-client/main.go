package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"strconv"
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

	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(),
			"%s FIRST [LAST [STEP]]\n"+
				"  FIRST\tint\n"+
				"  LAST\tint (default FIRST)\n"+
				"  STEP\tint (default 1)\n",
			os.Args[0])
		flag.PrintDefaults()
	}
	addr := flag.String("addr", "localhost:50051", "the address to connect to")
	useMutex := flag.Bool("mutex", false, "use a mutex in the client to avoid concurrent purchases")
	flag.Parse()

	if flag.NArg() < 1 {
		fmt.Fprint(flag.CommandLine.Output(), "Need at least FIRST !!\n\n")
		flag.Usage()
		return 1
	}
	parseValue := func(i, defaultValue int) int {
		v := flag.Arg(i)
		if v == "" {
			return defaultValue
		}
		ret, err := strconv.Atoi(v)
		if err != nil {
			fmt.Fprintf(flag.CommandLine.Output(), "%s not an int\n\n", v)
			flag.Usage()
			os.Exit(1)
		}
		return ret
	}

	first := parseValue(0, -1)
	last := parseValue(1, first)
	step := parseValue(2, 1)
	fmt.Printf("running from %d to %d with %d step\n", first, last, step)

	type numAndDuration struct {
		num int
		dur time.Duration
	}
	runFcn := runNClients
	if *useMutex {
		fmt.Println("(using mutex on client")
		runFcn = runNClientsWithMutex
	}
	times := make([]numAndDuration, 0)
	for i := first; i <= last; i += step {
		t0 := time.Now()
		runFcn(ctx, i, *addr)
		times = append(times, numAndDuration{
			num: i,
			dur: time.Since(t0)},
		)
	}
	for _, nd := range times {
		fmt.Printf("%4d:\t\t%20v\n", nd.num, nd.dur.Seconds())
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

func runNClientsWithMutex(ctx context.Context, n int, serverAddr string) {
	wg := sync.WaitGroup{}
	wg.Add(n)
	var m sync.Mutex
	fmt.Printf("%d ", n)
	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			m.Lock()
			defer m.Unlock()
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
	for {
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
		t0 = time.Now()
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
		t0 = time.Now()
		if err != nil {
			// fmt.Fprintf(os.Stderr, "buying offer: %v\n", err)
			continue
		}
		data = serialize.SerializeContract(contract)
		err = certBroker.VerifySignature(data, contract.ContractSignature)
		if err != nil {
			log.Fatalf("contract signature: %v", err)
		}
		_ = t0
		return
	}
}
