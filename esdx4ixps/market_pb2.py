# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: market.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0cmarket.proto\x12\x06market\x1a\x1fgoogle/protobuf/timestamp.proto\"\r\n\x0bListRequest\"\xfb\x01\n\x12OfferSpecification\x12\x0c\n\x04iaid\x18\x01 \x01(\t\x12\x0f\n\x07is_core\x18\x02 \x01(\x08\x12-\n\tnotbefore\x18\x03 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12,\n\x08notafter\x18\x04 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x17\n\x0freachable_paths\x18\x05 \x01(\t\x12\x11\n\tqos_class\x18\x06 \x01(\x05\x12\x16\n\x0eprice_per_unit\x18\x07 \x01(\x01\x12\x12\n\nbw_profile\x18\x08 \x01(\t\x12\x11\n\tsignature\x18\t \x01(\x0c\">\n\x05Offer\x12\n\n\x02id\x18\x01 \x01(\x03\x12)\n\x05specs\x18\x02 \x01(\x0b\x32\x1a.market.OfferSpecification\"\x8f\x01\n\x0fPurchaseRequest\x12\x10\n\x08offer_id\x18\x01 \x01(\x03\x12\x12\n\nbuyer_iaid\x18\x02 \x01(\t\x12\x11\n\tsignature\x18\x03 \x01(\x0c\x12\x12\n\nbw_profile\x18\x04 \x01(\t\x12/\n\x0bstarting_on\x18\x05 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\"\x9c\x02\n\x08\x43ontract\x12\x13\n\x0b\x63ontract_id\x18\x01 \x01(\x03\x12\x36\n\x12\x63ontract_timestamp\x18\x02 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x1a\n\x12\x63ontract_signature\x18\x03 \x01(\x0c\x12)\n\x05offer\x18\n \x01(\x0b\x32\x1a.market.OfferSpecification\x12\x12\n\nbuyer_iaid\x18\x32 \x01(\t\x12\x35\n\x11\x62uyer_starting_on\x18\x33 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x18\n\x10\x62uyer_bw_profile\x18\x34 \x01(\t\x12\x17\n\x0f\x62uyer_signature\x18\x35 \x01(\x0c\"^\n\x12GetContractRequest\x12\x13\n\x0b\x63ontract_id\x18\x01 \x01(\x03\x12\x16\n\x0erequester_iaid\x18\x02 \x01(\t\x12\x1b\n\x13requester_signature\x18\x03 \x01(\x0c\x32\xf9\x01\n\x10MarketController\x12\x34\n\nListOffers\x12\x13.market.ListRequest\x1a\r.market.Offer\"\x00\x30\x01\x12\x37\n\x08\x41\x64\x64Offer\x12\x1a.market.OfferSpecification\x1a\r.market.Offer\"\x00\x12\x37\n\x08Purchase\x12\x17.market.PurchaseRequest\x1a\x10.market.Contract\"\x00\x12=\n\x0bGetContract\x12\x1a.market.GetContractRequest\x1a\x10.market.Contract\"\x00\x62\x06proto3')



_LISTREQUEST = DESCRIPTOR.message_types_by_name['ListRequest']
_OFFERSPECIFICATION = DESCRIPTOR.message_types_by_name['OfferSpecification']
_OFFER = DESCRIPTOR.message_types_by_name['Offer']
_PURCHASEREQUEST = DESCRIPTOR.message_types_by_name['PurchaseRequest']
_CONTRACT = DESCRIPTOR.message_types_by_name['Contract']
_GETCONTRACTREQUEST = DESCRIPTOR.message_types_by_name['GetContractRequest']
ListRequest = _reflection.GeneratedProtocolMessageType('ListRequest', (_message.Message,), {
  'DESCRIPTOR' : _LISTREQUEST,
  '__module__' : 'market_pb2'
  # @@protoc_insertion_point(class_scope:market.ListRequest)
  })
_sym_db.RegisterMessage(ListRequest)

OfferSpecification = _reflection.GeneratedProtocolMessageType('OfferSpecification', (_message.Message,), {
  'DESCRIPTOR' : _OFFERSPECIFICATION,
  '__module__' : 'market_pb2'
  # @@protoc_insertion_point(class_scope:market.OfferSpecification)
  })
_sym_db.RegisterMessage(OfferSpecification)

Offer = _reflection.GeneratedProtocolMessageType('Offer', (_message.Message,), {
  'DESCRIPTOR' : _OFFER,
  '__module__' : 'market_pb2'
  # @@protoc_insertion_point(class_scope:market.Offer)
  })
_sym_db.RegisterMessage(Offer)

PurchaseRequest = _reflection.GeneratedProtocolMessageType('PurchaseRequest', (_message.Message,), {
  'DESCRIPTOR' : _PURCHASEREQUEST,
  '__module__' : 'market_pb2'
  # @@protoc_insertion_point(class_scope:market.PurchaseRequest)
  })
_sym_db.RegisterMessage(PurchaseRequest)

Contract = _reflection.GeneratedProtocolMessageType('Contract', (_message.Message,), {
  'DESCRIPTOR' : _CONTRACT,
  '__module__' : 'market_pb2'
  # @@protoc_insertion_point(class_scope:market.Contract)
  })
_sym_db.RegisterMessage(Contract)

GetContractRequest = _reflection.GeneratedProtocolMessageType('GetContractRequest', (_message.Message,), {
  'DESCRIPTOR' : _GETCONTRACTREQUEST,
  '__module__' : 'market_pb2'
  # @@protoc_insertion_point(class_scope:market.GetContractRequest)
  })
_sym_db.RegisterMessage(GetContractRequest)

_MARKETCONTROLLER = DESCRIPTOR.services_by_name['MarketController']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _LISTREQUEST._serialized_start=57
  _LISTREQUEST._serialized_end=70
  _OFFERSPECIFICATION._serialized_start=73
  _OFFERSPECIFICATION._serialized_end=324
  _OFFER._serialized_start=326
  _OFFER._serialized_end=388
  _PURCHASEREQUEST._serialized_start=391
  _PURCHASEREQUEST._serialized_end=534
  _CONTRACT._serialized_start=537
  _CONTRACT._serialized_end=821
  _GETCONTRACTREQUEST._serialized_start=823
  _GETCONTRACTREQUEST._serialized_end=917
  _MARKETCONTROLLER._serialized_start=920
  _MARKETCONTROLLER._serialized_end=1169
# @@protoc_insertion_point(module_scope)
