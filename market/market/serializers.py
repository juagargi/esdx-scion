from market.models import Offer
from django_grpc_framework import proto_serializers
import market.market_pb2


class OfferProtoSerializer(proto_serializers.ModelProtoSerializer):
    class Meta:
        model = Offer
        proto_class = market.market_pb2.Offer
        fields = ['ia_id']
