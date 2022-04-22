from market.models import Offer
from django_grpc_framework import proto_serializers
from rest_framework import serializers
import market_pb2
import base64



# class BinaryField(serializers.Field):
#     def to_representation(self, value):
#         return base64.standard_b64encode(value)

#     def to_internal_value(self, data):
#         return base64.standard_b64decode(data)

class OfferProtoSerializer(proto_serializers.ModelProtoSerializer):
    class Meta:
        model = Offer
        proto_class = market_pb2.Offer
        fields = ['iaid', 'iscore', 'signature', 'notbefore', 'notafter', 'reachable_paths',
                  'qos_class', 'bw_profile', 'price_per_nanounit']

# class OfferProtoSerializer(proto_serializers.ProtoSerializer):
#     class Meta:
#         model = Offer
#         proto_class = market_pb2.Offer
#     iaid = serializers.IntegerField()
#     comment = serializers.CharField()
#     signature = BinaryField()