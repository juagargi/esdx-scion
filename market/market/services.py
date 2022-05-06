from market.models import Offer
# from django_grpc_framework import generics
from django_grpc_framework.services import Service
from market.serializers import OfferProtoSerializer
from django.utils import timezone as tz
import market_pb2
import pytz


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

    def Purchase(self, request, context):
        response = market_pb2.PurchaseResponse()
        offers = Offer.objects.filter(id=request.offer_id)
        if len(offers) != 1:
            response.message = f"offer id {request.offer_id} not found"
            return response
        starts_at = tz.datetime.fromtimestamp(request.starting_on.seconds + request.starting_on.nanos / 1e9)
        starts_at = starts_at.replace(tzinfo=pytz.utc)
        if not offers[0].contains_profile(request.bw_profile, starts_at):
            response.message = "offer does not contain the requested BW profile"
            return response

        response.message = "success"
        return response
