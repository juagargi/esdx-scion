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
    signature = BinaryField()
    notbefore = serializers.DateTimeField()
    notafter = serializers.DateTimeField()
    reachable_paths = serializers.CharField()
    qos_class = serializers.IntegerField()
    price_per_unit = serializers.FloatField()  # TODO(juagargi) maybe DecimalField
    bw_profile = serializers.CharField()

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
        return Offer.objects.create(**values)

    def validate_signature_from_seller(self):
        # find seller
        seller = AS.objects.get(iaid=self.validated_data["iaid"])
        # get cert
        cert = crypto.load_certificate(seller.certificate_pem)
        # serialize fields
        data = self.serialize_to_bytes()
        # validate signature
        signature = self.validated_data['signature']
        crypto.signature_validate(cert, signature, data)

    def sign_with_broker(self):
        # serialize fields
        data = self.serialize_to_bytes()
        # get key from broker
        broker = Broker.objects.get()
        key = crypto.load_key(broker.key_pem)
        # sign
        signature = crypto.signature_create(key, data)
        self.validated_data["signature"] = signature

    def serialize_to_bytes(self) -> bytes:
        return serialize.offer_fields_serialize_to_bytes(
            self.validated_data["iaid"],
            self.validated_data["is_core"],
            int(self.validated_data["notbefore"].timestamp()),
            int(self.validated_data["notafter"].timestamp()),
            self.validated_data["reachable_paths"],
            self.validated_data["qos_class"],
            self.validated_data["price_per_unit"],
            self.validated_data["bw_profile"]
        )


class ContractProtoSerializer(proto_serializers.ModelProtoSerializer):
    class Meta:
        model = Contract
        proto_class = market_pb2.Contract
        fields = ["id", "timestamp", "signature_broker", "purchase_order"]
        depth = 2

    def __eq__(self,o: object) -> bool:
        return type(o) == ContractProtoSerializer and self.data == o.data

    # def message_to_data(self, message: market_pb2.Contract) -> dict:
    #     return super().message_to_data(message)

    def data_to_message(self, data: dict) -> market_pb2.Contract:
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
                signature=base64.standard_b64decode(offer["signature"]),
            ),
            buyer_iaid=buyer["iaid"],
            buyer_starting_on=conversion.pb_timestamp_from_str(po["starting_on"]),
            buyer_bw_profile=po["bw_profile"],
            buyer_signature=base64.standard_b64decode(po["signature"]),
        )