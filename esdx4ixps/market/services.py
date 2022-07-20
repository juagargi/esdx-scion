from django_grpc_framework.services import Service
from django.db import IntegrityError, transaction, close_old_connections
from market.models.ases import AS
from market.models.contract import Contract
from market.models.offer import Offer
from market.serializers import OfferProtoSerializer, ContractProtoSerializer, pb_compare_messages
from market.purchases import purchase_offer
from util.conversion import time_from_pb_timestamp
from util import crypto
from util import conversion
from util import serialize

import copy
import market_pb2
import grpc
import threading
import time


# we don't allow concurrent purchases. Having a mutex is more performant than just locking
# the DB via a transaction (although the latter is needed anyways).
purchase_mutex = threading.Lock()


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

    def AddOffer(self, request: market_pb2.OfferSpecification, context):
        try:
            grpc_offer = OfferProtoSerializer(message=market_pb2.Offer(specs=request))
            grpc_offer.is_valid(raise_exception=True)
            with transaction.atomic():
                offer = grpc_offer.save() # only creates an instance without saving it to the DB
                offer.id = None  # ensure this will be a new offer
                offer.validate_signature_from_seller()
                offer.save() # store the original offer
                new_offer = copy.deepcopy(offer)
                new_offer.id = None
                new_offer.deprecates = offer
                new_offer.sign_with_broker()
                new_offer.save()
                return OfferProtoSerializer(new_offer).message
        except IntegrityError:
            # should never happen
            raise MarketServiceError("data was modified during the transaction")
        except Exception as ex:
            raise MarketServiceError(str(ex)) from ex

    def Purchase(self, request: market_pb2.PurchaseRequest, context):
        global purchase_mutex
        try:
            with purchase_mutex, transaction.atomic():
                offer = Offer.objects.get_available(id=request.offer.id)
                # check that this offer matches request.offer
                if not pb_compare_messages(request.offer, OfferProtoSerializer(offer).message):
                    raise MarketServiceError("purchase request validation failed: " + \
                        f"offer with ID {request.offer.id} not the same as in the request")
                # create contract and new offer
                contract, _ = purchase_offer(
                    offer,
                    request.buyer_iaid,
                    time_from_pb_timestamp(request.starting_on),
                    request.bw_profile,
                    request.signature,
                )
            serializer = ContractProtoSerializer(contract)
            return serializer.message
        except MarketServiceError:
            raise
        except IntegrityError as ex:
            raise MarketServiceError("data was modified during the transaction") from ex
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
