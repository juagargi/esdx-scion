from models import Offer
from django_grpc_framework import proto_serializers
import market_pb2


class UserProtoSerializer(proto_serializers.ModelProtoSerializer):
    class Meta:
        model = Offer
        proto_class = market_pb2.Offer
        fields = ['ia_id']
