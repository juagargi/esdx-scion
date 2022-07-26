package serialize

import (
	pb "esdx_scion/market"
	"fmt"
	"log"
	"strconv"
)

func SerializeOfferSpecification(o *pb.OfferSpecification) []byte {
	s := fmt.Sprintf("ia:%s%d%dreachable:%s%d%sprofile:%sbr_address_template:%s"+
		"br_mtu:%dbr_link_to:%ssignature:",
		o.Iaid,
		o.Notbefore.Seconds,
		o.Notafter.Seconds,
		o.ReachablePaths,
		o.QosClass,
		strconv.FormatFloat(o.PricePerUnit, 'e', 6, 64),
		o.BwProfile,
		o.BrAddressTemplate,
		o.BrMtu,
		o.BrLinkTo)
	return append([]byte(s), o.Signature...)
}

// SerializePurchaseOrder serializes a PurchaseRequest (not its signature).
func SerializePurchaseOrder(o *pb.PurchaseRequest) []byte {
	return serializePairs(
		"offer:", SerializeOfferSpecification(o.Offer.Specs),
		"bw_profile:", []byte(o.BwProfile),
		"buyer:", []byte(o.BuyerIaid),
		"starting_on:", []byte(strconv.FormatInt(o.StartingOn.Seconds, 10)),
	)
}

func SerializeContract(c *pb.Contract, requestedOffer *pb.OfferSpecification) []byte {
	return serializePairs(
		"order:", SerializePurchaseOrder(&pb.PurchaseRequest{
			Offer: &pb.Offer{
				Specs: requestedOffer,
			},
			BuyerIaid:  c.BuyerIaid,
			BwProfile:  c.BuyerBwProfile,
			StartingOn: c.BuyerStartingOn,
		}),
		"signature_buyer:", c.BuyerSignature,
		"timestamp:", []byte(strconv.FormatInt(c.ContractTimestamp.Seconds, 10)),
		"br_address:", []byte(c.BrAddress),
	)
}

// serializePairs called like serializePairs("iaid", []byte(iaid), "offer:", offerbytes)
func serializePairs(pairs ...interface{}) []byte {
	if len(pairs)%2 != 0 {
		log.Panicf("expected N pairs, but got %d elements", len(pairs))
	}
	ret := make([]byte, 0)
	for i := 0; i < len(pairs); i += 2 {
		label := pairs[i].(string)
		ret = append(ret, []byte(label)...)
		value := pairs[i+1].([]byte)
		ret = append(ret, value...)
	}
	return ret
}
