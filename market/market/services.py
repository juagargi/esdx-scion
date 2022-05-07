from django_grpc_framework.services import Service
from django.db import transaction
from market.models.offer import Offer
from market.models.purchase import PurchaseOrder
from market.models.contract import Contract
from market.serializers import OfferProtoSerializer
import market_pb2
from util.conversion import time_from_pb_timestamp


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
            try:
                # create purchse order will already validate the signature:
                purchase_order = PurchaseOrder.objects.create(
                    offer_id=offer.id,
                    buyer_id=request.buyer_id,
                    signature=request.signature,
                    bw_profile=request.bw_profile,
                    starting_on=starts_at)
            except Exception as e:  # e.g. invalid signature
                response.message = str(e)
                return response

            # create contract
            contract = Contract.objects.create(
                purchase_order=purchase_order,
                signature_broker=b"",  # TODO(juagargi) implement signing the contract
            )

            # create new offer
            offer.id = None
            offer.bw_profile = new_profile
            offer.save()

        response.message = "success"
        response.purchase_id = purchase_order.id
        response.new_offer_id = offer.id
        return response
