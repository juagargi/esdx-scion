package serialize

import (
	pb "esdx_scion/market"
	"testing"

	"github.com/stretchr/testify/require"
	"google.golang.org/protobuf/types/known/timestamppb"
)

func TestSerializeOfferSpecification(t *testing.T) {
	o := &pb.OfferSpecification{
		Iaid:              "1-ff00:0:111",
		Notbefore:         &timestamppb.Timestamp{Seconds: 11},
		Notafter:          &timestamppb.Timestamp{Seconds: 12},
		ReachablePaths:    "path1,path2",
		QosClass:          1,
		PricePerUnit:      100,
		BwProfile:         "2,2,2,2",
		BrAddressTemplate: "1.1.1.1:42-45",
		BrMtu:             1500,
		BrLinkTo:          "PARENT",
		Signature:         nil,
	}
	got := SerializeOfferSpecification(o)
	expected := "ia:1-ff00:0:1111112reachable:path1,path211.000000e+02profile:2,2,2,2" +
		"br_address_template:1.1.1.1:42-45br_mtu:1500br_link_to:PARENTsignature:"
	require.Equal(t, expected, string(got))
}

func TestSerializePurchaseOrder(t *testing.T) {
	o := &pb.OfferSpecification{
		Iaid:              "1-ff00:0:111",
		Notbefore:         &timestamppb.Timestamp{Seconds: 11},
		Notafter:          &timestamppb.Timestamp{Seconds: 12},
		ReachablePaths:    "path1,path2",
		QosClass:          1,
		PricePerUnit:      100,
		BwProfile:         "2,2,2,2",
		BrAddressTemplate: "1.1.1.1:42-45",
		BrMtu:             1500,
		BrLinkTo:          "PARENT",
		Signature:         nil,
	}

	// now actually test the purchase order serialization
	po := &pb.PurchaseRequest{
		Offer: &pb.Offer{
			Specs: o,
		},
		BuyerIaid:  "1-ff00:0:112",
		BwProfile:  "1,2,2,1",
		StartingOn: &timestamppb.Timestamp{Seconds: 11},
	}
	got := SerializePurchaseOrder(po)
	expected := "offer:ia:1-ff00:0:1111112reachable:path1,path211.000000e+02profile:2,2,2,2" +
		"br_address_template:1.1.1.1:42-45br_mtu:1500br_link_to:PARENTsignature:" +
		"bw_profile:1,2,2,1buyer:1-ff00:0:112starting_on:11"
	require.Equal(t, expected, string(got))
}

func TestSerializeContract(t *testing.T) {
	o := &pb.OfferSpecification{
		Iaid:              "1-ff00:0:111",
		Notbefore:         &timestamppb.Timestamp{Seconds: 11},
		Notafter:          &timestamppb.Timestamp{Seconds: 12},
		ReachablePaths:    "path1,path2",
		QosClass:          1,
		PricePerUnit:      100,
		BwProfile:         "2,2,2,2",
		BrAddressTemplate: "1.1.1.1:42-45",
		BrMtu:             1500,
		BrLinkTo:          "PARENT",
		Signature:         nil,
	}

	c := &pb.Contract{
		Offer:             o,
		BuyerIaid:         "1-ff00:0:112",
		BuyerBwProfile:    "1,2,2,1",
		BuyerStartingOn:   &timestamppb.Timestamp{Seconds: 11},
		BuyerSignature:    []byte{1, 2, 3, 4},
		ContractTimestamp: &timestamppb.Timestamp{Seconds: 8},
		BrAddress:         "1.1.1.1:1111",
	}
	got := SerializeContract(c)
	expected := "order:offer:ia:1-ff00:0:1111112reachable:path1,path211.000000e+02profile:2,2,2,2" +
		"br_address_template:1.1.1.1:42-45br_mtu:1500br_link_to:PARENTsignature:" +
		"bw_profile:1,2,2,1buyer:1-ff00:0:112starting_on:11" +
		"signature_buyer:\x01\x02\x03\x04" + "timestamp:8br_address:1.1.1.1:1111"
	require.Equal(t, expected, string(got))
}
