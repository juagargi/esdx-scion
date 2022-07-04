from django_grpc_framework import proto_serializers
from google.protobuf.timestamp_pb2 import Timestamp
from market.models.offer import Offer
from market.models.ases import AS
from market.models.broker import Broker
from market.models.contract import Contract
from util import conversion
from util import crypto
from util import serialize
from rest_framework import serializers

import base64
import market_pb2


class BinaryField(serializers.Field):
    """ this binary field uses base64 encoding """
    def to_internal_value(self, data: str) -> bytes:
        return base64.standard_b64decode(data)

    def to_representation(self, value: bytes) -> bytes:
        return base64.standard_b64encode(value)


class OfferProtoSerializer(proto_serializers.ProtoSerializer):
    class Meta:
        model = Offer
        proto_class = market_pb2.Offer

    id = serializers.IntegerField()
    iaid = serializers.CharField(max_length=32)
    is_core = serializers.BooleanField()
    notbefore = serializers.DateTimeField()
    notafter = serializers.DateTimeField()
    reachable_paths = serializers.CharField()
    qos_class = serializers.IntegerField()
    price_per_unit = serializers.FloatField()  # TODO(juagargi) maybe DecimalField
    bw_profile = serializers.CharField()
    br_address_template = serializers.CharField()
    br_mtu = serializers.IntegerField()
    br_link_to = serializers.CharField()
    signature = BinaryField()

    embed_in_specs = [f.name for f in market_pb2.OfferSpecification().DESCRIPTOR.fields]

    def message_to_data(self, message: market_pb2.Offer) -> dict:
        data = super().message_to_data(message)
        # move values from specs to plain dict
        d = data
        for k, v in data["specs"].items():
            d[k] = v
        del d["specs"]
        return d

    def data_to_message(self, data: dict) -> market_pb2.Offer:
        d = {
            "specs": {},
        }
        for k, v in data.items():
            if k in self.embed_in_specs:
                d["specs"][k] = v
            else:
                d[k] = v
        return super().data_to_message(d)

    def create(self, values):
        """only creates an instance, not a record in the DB"""
        return Offer(**values)

    def serialize_to_bytes(self) -> bytes:
        return serialize.offer_fields_serialize_to_bytes(
            self.validated_data["iaid"],
            self.validated_data["is_core"],
            int(self.validated_data["notbefore"].timestamp()),
            int(self.validated_data["notafter"].timestamp()),
            self.validated_data["reachable_paths"],
            self.validated_data["qos_class"],
            self.validated_data["price_per_unit"],
            self.validated_data["bw_profile"],
            self.validated_data["br_address_template"],
            self.validated_data["br_mtu"],
            self.validated_data["br_link_to"],
        )


class ContractProtoSerializer(proto_serializers.ModelProtoSerializer):
    class Meta:
        model = Contract
        proto_class = market_pb2.Contract
        fields = ["id", "timestamp", "br_address", "signature_broker", "purchase_order"]
        depth = 2

    def __eq__(self,o: object) -> bool:
        return type(o) == ContractProtoSerializer and self.data == o.data

    # def message_to_data(self, message: market_pb2.Contract) -> dict:
    #     return super().message_to_data(message)

    def data_to_message(self, data: dict) -> market_pb2.Contract:
        """ dict of fields from the model Contract to the protobuf Contract """
        po = data["purchase_order"]
        buyer = po["buyer"]
        offer = po["offer"]
        return market_pb2.Contract(
            contract_id=data["id"],
            contract_timestamp=conversion.pb_timestamp_from_str(data["timestamp"]),
            contract_signature=base64.standard_b64decode(data["signature_broker"]),
            offer=market_pb2.OfferSpecification(
                iaid=offer["iaid"],
                is_core=offer["is_core"],
                notbefore=conversion.pb_timestamp_from_str(offer["notbefore"]),
                notafter=conversion.pb_timestamp_from_str(offer["notafter"]),
                reachable_paths=offer["reachable_paths"],
                qos_class=int(offer["qos_class"]),
                price_per_unit=float(offer["price_per_unit"]),
                bw_profile=offer["bw_profile"],
                br_address_template=offer["br_address_template"],
                br_mtu=int(offer["br_mtu"]),
                br_link_to=offer["br_link_to"],
                signature=base64.standard_b64decode(offer["signature"]),
            ),
            br_address=data["br_address"],
            buyer_iaid=buyer["iaid"],
            buyer_starting_on=conversion.pb_timestamp_from_str(po["starting_on"]),
            buyer_bw_profile=po["bw_profile"],
            buyer_signature=base64.standard_b64decode(po["signature"]),
        )
