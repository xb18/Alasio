"""
Tests for the ws message protocol (alasio/backend/reactive/event.py):
RequestEvent / ResponseEvent msgspec encoding and decoding.

Uses the runtime codec instances from ws_server.py, so the exact
serialization path of the server is pinned down.
"""

import msgspec
import pytest
from msgspec import DecodeError, ValidationError

from alasio.backend.reactive.event import RequestEvent, ResponseEvent
from alasio.backend.ws.ws_server import REQUEST_EVENT_DECODER

ENCODER = msgspec.json.Encoder()
RESPONSE_DECODER = msgspec.json.Decoder(ResponseEvent)


class TestRequestEvent:
    def test_encode_omits_defaults(self):
        """default fields (o/f/v/i) are omitted from the wire format"""
        assert ENCODER.encode(RequestEvent(t='x')) == b'{"t":"x"}'

    def test_encode_omits_explicit_defaults(self):
        assert ENCODER.encode(RequestEvent(t='x', o='sub', f='', v={}, i='')) == b'{"t":"x"}'

    def test_encode_full_fields(self):
        event = RequestEvent(t='x', o='rpc', f='fn', v={'a': 1}, i='id')
        assert ENCODER.encode(event) == b'{"t":"x","o":"rpc","f":"fn","v":{"a":1},"i":"id"}'

    def test_decode_defaults(self):
        """decoding a minimal message fills in the defaults"""
        event = REQUEST_EVENT_DECODER.decode(b'{"t":"x"}')
        assert event.t == 'x'
        assert event.o == 'sub'
        assert event.f == ''
        assert event.v == {}
        assert event.i == ''
        assert isinstance(event.v, dict)

    def test_round_trip(self):
        event = RequestEvent(t='x', o='unsub')
        decoded = REQUEST_EVENT_DECODER.decode(ENCODER.encode(event))
        assert decoded == event

    def test_decode_invalid_op(self):
        """an operation outside the Literal is rejected"""
        with pytest.raises(ValidationError, match='Invalid enum value'):
            REQUEST_EVENT_DECODER.decode(b'{"t":"x","o":"foo"}')

    def test_decode_missing_topic(self):
        """t is required"""
        with pytest.raises(ValidationError, match='missing required field'):
            REQUEST_EVENT_DECODER.decode(b'{"o":"sub"}')

    def test_decode_invalid_json(self):
        with pytest.raises(DecodeError):
            REQUEST_EVENT_DECODER.decode(b'not json')

    def test_decode_value_any(self):
        """v accepts any JSON value"""
        assert REQUEST_EVENT_DECODER.decode(b'{"t":"x","v":5}').v == 5
        assert REQUEST_EVENT_DECODER.decode(b'{"t":"x","v":"str"}').v == 'str'
        assert REQUEST_EVENT_DECODER.decode(b'{"t":"x","v":null}').v is None


class TestResponseEvent:
    def test_encode_omits_defaults(self):
        """default fields (o/k/v/i) are omitted from the wire format"""
        assert ENCODER.encode(ResponseEvent(t='x')) == b'{"t":"x"}'

    def test_encode_omits_explicit_defaults(self):
        assert ENCODER.encode(ResponseEvent(t='x', o='add', k=(), v=None, i='')) == b'{"t":"x"}'

    def test_encode_k_tuple_as_array(self):
        """k is serialized as a JSON array"""
        event = ResponseEvent(t='x', o='set', k=('a', 1), v='val')
        assert ENCODER.encode(event) == b'{"t":"x","o":"set","k":["a",1],"v":"val"}'

    def test_decode_k_as_tuple(self):
        """k is decoded back to a tuple with mixed str/int keys"""
        event = RESPONSE_DECODER.decode(b'{"t":"x","o":"set","k":["a",1],"v":"val"}')
        assert event.k == ('a', 1)

    def test_decode_defaults(self):
        event = RESPONSE_DECODER.decode(b'{"t":"x"}')
        assert event.o == 'add'
        assert event.k == ()
        assert event.v is None
        assert event.i == ''

    def test_rpc_success_omits_value(self):
        """an rpc response without v means success"""
        assert ENCODER.encode(ResponseEvent(t='x', i='id')) == b'{"t":"x","i":"id"}'

    def test_rpc_error_has_value(self):
        """an rpc response with v means error"""
        assert ENCODER.encode(ResponseEvent(t='x', v='msg', i='id')) == b'{"t":"x","v":"msg","i":"id"}'

    def test_del_omits_value(self):
        assert ENCODER.encode(ResponseEvent(t='x', o='del', k=('a',))) == b'{"t":"x","o":"del","k":["a"]}'

    def test_full_keeps_value(self):
        assert ENCODER.encode(ResponseEvent(t='x', o='full', v={'a': 1})) == b'{"t":"x","o":"full","v":{"a":1}}'

    def test_batch_encode(self):
        """multiple events are batched into a JSON array"""
        events = [ResponseEvent(t='a'), ResponseEvent(t='b')]
        assert ENCODER.encode(events) == b'[{"t":"a"},{"t":"b"}]'

    def test_round_trip(self):
        event = ResponseEvent(t='x', o='set', k=('a', 1), v='val', i='id')
        assert RESPONSE_DECODER.decode(ENCODER.encode(event)) == event
