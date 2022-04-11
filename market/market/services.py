from market.models import Offer
# from django_grpc_framework import generics
from django_grpc_framework.services import Service
from market.serializers import OfferProtoSerializer


class MarketService(Service):
    """
    gRPC service that allows working with offers.
    """
    # queryset = Offer.objects.all()
    # serializer_class = OfferProtoSerializer
    def ListOffers(self, request, context):
        offer = Offer()
        offer.ia_id = 1111
        offer.comment = 'deleteme comment'
        print(offer)
        serializer = OfferProtoSerializer(offer)
        return serializer.message
