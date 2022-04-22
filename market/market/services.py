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

    def AddOffer(self, request, context):
        request.id = 0 # force to empty
        serializer = OfferProtoSerializer(message=request)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return serializer.message
