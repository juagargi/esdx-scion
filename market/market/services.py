from market.models import Offer
from django_grpc_framework import generics
from market.serializers import OfferProtoSerializer


class MarketService(generics.ModelService):
    """
    gRPC service that allows working with offers.
    """
    queryset = Offer.objects.all()
    serializer_class = OfferProtoSerializer
