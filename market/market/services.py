from market.models import Offer
# from django_grpc_framework import generics
from django_grpc_framework.services import Service
from market.serializers import OfferProtoSerializer
from datetime import datetime


class MarketService(Service):
    """
    gRPC service that allows working with offers.
    """
    # queryset = Offer.objects.all()
    # serializer_class = OfferProtoSerializer
    def ListOffers(self, request, context):
        offer = Offer()
        offer.iaid = 1111
        offer.iscore = True
        offer.signature = bytes.fromhex('deadbeef')
        offer.notbefore = datetime(2015, 10, 9, 23, 55, 59, 342380)
        offer.notafter = datetime(2015, 10, 9, 23, 56, 59, 342380)
        # 1-ff00:0:110 connects to 2 non-core ASes:
        offer.reachable_paths = "1-ff00:0:110#0,1 1-ff00:0:111#1\n" +\
                                "1-ff00:0:110#0,2 1-ff00:0:112#1"
        offer.qos_class = 1
        offer.bw_profile = "2,2,2,2,2,2"
        offer.price_per_nanounit = 2000  # 2$ per 1 million units = 2$ per 1 Pbps during 600 secs
        print(offer)

        serializer = OfferProtoSerializer(offer)
        print(serializer.message)
        return serializer.message
