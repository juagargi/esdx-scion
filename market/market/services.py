from django_grpc_framework.services import Service
from django.db import transaction
from market.models.offer import Offer
from market.serializers import OfferProtoSerializer
import market_pb2
from util.conversion import time_from_pb_timestamp


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
        with transaction.atomic():
            try:
                offer = Offer.objects.get(id=request.offer_id)
            except Offer.DoesNotExist:
                response.message = f"offer id {request.offer_id} not found"
                return response
            starts_at = time_from_pb_timestamp(request.starting_on)
            new_profile = offer.purchase(request.bw_profile, starts_at)
            if new_profile is None:
                response.message = "offer does not contain the requested BW profile"
                return response
            offer.bw_profile = new_profile
            offer.delete()
            offer.save()

        response.message = "success"
        response.new_offer_id = offer.id
        return response
