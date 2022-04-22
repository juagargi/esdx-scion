from market.models import Offer
# from django_grpc_framework import generics
from django_grpc_framework.services import Service
from market.serializers import OfferProtoSerializer
from datetime import datetime


class MarketService(Service):
    """
    gRPC service that allows working with offers.
    """
    def ListOffers(self, request, context):
        offers = Offer.objects.all()
        serializer = OfferProtoSerializer(offers, many=True)
        for offer in serializer.message:
            yield offer
