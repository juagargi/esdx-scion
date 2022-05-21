from market.models.offer import Offer, fields_serialize_to_bytes
from market.models.ases import AS
from util import crypto
from django_grpc_framework import proto_serializers
from rest_framework import serializers
import market_pb2
import base64


class OfferProtoSerializer(proto_serializers.ProtoSerializer):
    class Meta:
        model = Offer
        proto_class = market_pb2.Offer

    iaid = serializers.CharField(max_length=32)
    iscore = serializers.BooleanField()
    signature = serializers.CharField(max_length=4096)
    notbefore = serializers.DateTimeField()
    notafter = serializers.DateTimeField()
    reachable_paths = serializers.CharField()
    qos_class = serializers.IntegerField()
    price_per_nanounit = serializers.IntegerField()
    bw_profile = serializers.CharField()

    def is_valid(self, *args, **kwargs):
        """ a gRPC Offer is being validated """
        super().is_valid(*args, **kwargs)

    def create(self, values):
        return Offer.objects.create(**values)

    def validate_signature_from_seller(self):
        # find seller
        seller = AS.objects.get(iaid=self.iaid)
        # get cert
        cert = crypto.load_pem_x509_certificate(seller.certificate_pem.decode("ascii"))
        # serialize fields
        data = self.serialize()
        # validate signature
        crypto.signature_validate(cert, self.signature, data)

    def serialize(self) -> bytes:
        return fields_serialize_to_bytes(
            self.iaid,
            self.iscore,
            int(self.notbefore.timestamp()),
            int(self.notafter.timestamp()),
            self.reachable_paths,
            self.qos_class,
            self.price_per_nanounit,
            self.bw_profile
        )
