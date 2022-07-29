package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"math/rand"
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
	experiment := flag.String("experiment", "", "experiment to run; one of: "+
		"{firstOffer,randomOffer,gaussianOffer,justOnce}")
	equivalentOffer := flag.Bool("equivalent", false, "allow purchasing equivalent offer")
	flag.Parse()

	var experimentFcn func(context.Context, string, bool)
	switch *experiment {
	case "firstOffer":
		experimentFcn = experimentBuyFirstOffer
	case "randomOffer":
		experimentFcn = experimentBuyRandomOffer
	case "gaussianOffer":
		experimentFcn = experimentBuyNormalDistributedOffer
	case "justOnce":
		experimentFcn = experimentGetFirstResponse
	default:
		fmt.Fprint(flag.CommandLine.Output(), "wrong experiment type !!\n\n")
		flag.Usage()
		return 1
	}

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
		runFcn(ctx, experimentFcn, i, *addr, *equivalentOffer)
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

func runNClients(ctx context.Context, experiment func(context.Context, string, bool), n int,
	serverAddr string, allowEquivalentOffer bool) {

	wg := sync.WaitGroup{}
	wg.Add(n)
	fmt.Printf("%d ", n)
	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			experiment(ctx, serverAddr, allowEquivalentOffer)
			fmt.Printf(".")
		}()
	}
	wg.Wait()
	fmt.Println()
}

func runNClientsWithMutex(ctx context.Context, experiment func(context.Context, string, bool), n int,
	serverAddr string, allowEquivalentOffer bool) {

	wg := sync.WaitGroup{}
	wg.Add(n)
	var m sync.Mutex
	fmt.Printf("%d ", n)
	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			m.Lock()
			defer m.Unlock()
			experiment(ctx, serverAddr, allowEquivalentOffer)
			fmt.Printf(".")
		}()
	}
	wg.Wait()
	fmt.Println()
}

func experimentBuyFirstOffer(ctx context.Context, serverAddr string, allowEquivalentOffer bool) {
	buyOffer(ctx, serverAddr, func(offers []*pb.Offer) *pb.Offer {
		return offers[0]
	}, allowEquivalentOffer)
}

func experimentBuyRandomOffer(ctx context.Context, serverAddr string, allowEquivalentOffer bool) {
	rand.NormFloat64()
	buyOffer(ctx, serverAddr, func(offers []*pb.Offer) *pb.Offer {
		return offers[rand.Intn(len(offers))]
	}, allowEquivalentOffer)
}

// experimentBuyNormalDistributedOffer
// the range of the gaussian based selection is [-4*sigma, 4*sigma],
// 8*sigma = len(offers) -> sigma = len(offers)/8
func experimentBuyNormalDistributedOffer(ctx context.Context, serverAddr string,
	allowEquivalentOffer bool) {

	buyOffer(ctx, serverAddr, func(offers []*pb.Offer) *pb.Offer {
		i := rand.NormFloat64()*float64(len(offers))/8 + float64(len(offers))/2
		return offers[int(i)]
	}, allowEquivalentOffer)
}

func experimentGetFirstResponse(ctx context.Context, serverAddr string, allowEquivalentOffer bool) {
	conn, err := grpc.Dial(serverAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}
	defer conn.Close()

	key, certBroker := keyCert()
	c := pb.NewMarketControllerClient(conn)
	offers := listOffers(ctx, c)
	offer := offers[0]
	_, _ = purchaseOffer(ctx, c, offer, allowEquivalentOffer, key, certBroker)
}

func keyCert() (*crypto.Key, *crypto.Cert) {
	// load key
	key, err := crypto.LoadKey("../test_data/1-ff00_0_111.key")
	if err != nil {
		log.Fatalf("loading key: %v", err)
	}
	certBroker, err := crypto.LoadCert("../test_data/broker.crt")
	if err != nil {
		log.Fatalf("loading broker certificate: %v", err)
	}
	return key, certBroker
}

func listOffers(ctx context.Context, c pb.MarketControllerClient) []*pb.Offer {
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
	return offers
}

func purchaseOffer(ctx context.Context, c pb.MarketControllerClient, offer *pb.Offer,
	allowEquivalent bool, key *crypto.Key, certBroker *crypto.Cert) (*pb.Contract, error) {

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

	var contract *pb.Contract
	if allowEquivalent {
		contract, err = c.PurchaseEquivalent(ctx, req)
	} else {
		contract, err = c.Purchase(ctx, req)
	}

	if err != nil {
		return nil, err
	}
	data = serialize.SerializeContract(contract, offer.Specs)
	err = certBroker.VerifySignature(data, contract.ContractSignature)
	if err != nil {
		log.Fatalf("contract signature: %v", err)
	}
	return contract, nil
}

func buyOffer(ctx context.Context, serverAddr string, offerSelecter func([]*pb.Offer) *pb.Offer,
	allowEquivalentOffer bool) {

	conn, err := grpc.Dial(serverAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}
	defer conn.Close()

	key, certBroker := keyCert()
	c := pb.NewMarketControllerClient(conn)
	for {
		offers := listOffers(ctx, c)
		offer := offerSelecter(offers)
		_, err := purchaseOffer(ctx, c, offer, allowEquivalentOffer, key, certBroker)
		if err == nil {
			break
		}
		// fmt.Fprintf(os.Stderr, "buying offer: %v\n", err)
	}
}
