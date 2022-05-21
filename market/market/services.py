from django_grpc_framework.services import Service
from django.db import transaction
from market.models.offer import Offer
from market.models.ases import AS
from market.models.broker import Broker
from market.serializers import OfferProtoSerializer
import market_pb2
from util.conversion import time_from_pb_timestamp
from market.purchases import purchase_offer


class MarketService(Service):
    """
    gRPC service that allows working with offers.
    """
    def ListOffers(self, request, context):
        offers = Offer.objects.available()
        serializer = OfferProtoSerializer(offers, many=True)
        for offer in serializer.message:
            yield offer

    def AddOffer(self, request, context):
        request.id = 0 # force to zero because we will get an id from the DB
        grpc_offer = OfferProtoSerializer(message=request)
        grpc_offer.is_valid(raise_exception=True)
        grpc_offer.validate_signature_from_seller()
        grpc_offer.sign_with_broker()
        saved = grpc_offer.save()
        grpc_offer.message.id = saved.id
        return grpc_offer.message

    def Purchase(self, request, context):
        response = market_pb2.PurchaseResponse()
        with transaction.atomic():
            try:
                offer = Offer.objects.get(id=request.offer_id)
            except Offer.DoesNotExist:
                response.message = f"offer id {request.offer_id} not found"
                return response
            starts_at = time_from_pb_timestamp(request.starting_on)

            try:
                contract, offer = purchase_offer(offer,
                                                 request.buyer_iaid,
                                                 starts_at,
                                                 request.bw_profile,
                                                 request.signature)
            except Exception as ex:
                response.message = str(ex)
                return response

        response.message = ""
        response.contract_id = contract.id
        response.new_offer_id = offer.id
        return response
