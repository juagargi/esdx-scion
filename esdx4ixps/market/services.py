from django_grpc_framework.services import Service
from django.db import IntegrityError, transaction
from market.models.ases import AS
from market.models.contract import Contract
from market.models.offer import Offer
from market.serializers import OfferProtoSerializer, ContractProtoSerializer
from market.purchases import purchase_offer
from util.conversion import time_from_pb_timestamp
from util import crypto
from util import serialize

import market_pb2
import grpc


class MarketServiceError(grpc.RpcError):
    """Raised by the MarketService to indicate non-OK-status RPC termination."""


class MarketService(Service):
    """
    gRPC service that allows working with offers.
    """
    def ListOffers(self, request, context):
        try:
            offers = Offer.objects.available()
            serializer = OfferProtoSerializer(offers, many=True)
            for offer in serializer.message:
                yield offer
        except Exception as ex:
            raise MarketServiceError(str(ex)) from ex

    def AddOffer(self, request, context):
        try:
            grpc_offer = OfferProtoSerializer(message=market_pb2.Offer(specs=request))
            grpc_offer.is_valid(raise_exception=True)
            grpc_offer.validate_signature_from_seller()
            grpc_offer.sign_with_broker()
            saved = grpc_offer.save()
            grpc_offer.message.id = saved.id
            return grpc_offer.message
        except Exception as ex:
            raise MarketServiceError(str(ex)) from ex

    def Purchase(self, request, context):
        try:
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
                except ValueError as ex:
                    response.message = str(ex)
                    return response
            response.message = ""
            response.contract_id = contract.id
            response.new_offer_id = offer.id
            return response
        except IntegrityError:
            response.message = "data was modified during the transaction"
            return response
        except Exception as ex:
            raise MarketServiceError(str(ex)) from ex

    def GetContract(self, request: market_pb2.GetContractRequest, context):
        try:
            # validate signature
            cert = crypto.load_certificate(AS.objects.get(iaid=request.requester_iaid).certificate_pem)
            data = serialize.get_contract_request_serialize(
                contract_id=request.contract_id,
                requester_iaid=request.requester_iaid,
                signature=None,
            )
            crypto.signature_validate(cert,request.requester_signature, data)
            contract = Contract.objects.get(id=request.contract_id)
            if contract.purchase_order.buyer.iaid != request.requester_iaid and \
                contract.purchase_order.offer.iaid != request.requester_iaid:
                raise MarketServiceError(f"IA {request.requester_iaid} cannot obtain this contract")
            serializer = ContractProtoSerializer(contract)
            return serializer.message
        except Exception as ex:
            raise MarketServiceError(str(ex)) from ex
