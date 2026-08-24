"""
Tests for BaseTopic (alasio/backend/ws/ws_topic.py): subscription, RPC,
and diff pushing behavior.
"""

from unittest.mock import AsyncMock, MagicMock, call

import pytest
import trio

from alasio.backend.reactive.event import AccessDenied, ResponseEvent
from alasio.backend.reactive.rx_trio import async_reactive, async_reactive_source
from alasio.backend.ws.ws_topic import BaseTopic
from alasio.logger import logger
from tests.backend.ws.helpers import FullOnlyTopic, SampleTopic


def mock_server():
    """
    A mock server whose send() records awaited ResponseEvent objects
    """
    server = MagicMock()
    server.send = AsyncMock()
    return server


@pytest.fixture(autouse=True)
def cleanup_local_singletons():
    """
    Clear singletons of locally defined topics, plus shared test topics
    """
    yield
    SampleTopic.singleton_clear()
    FullOnlyTopic.singleton_clear()
    for cls in (GetDataTopic, ReactiveTopic, BareTopic):
        cls.singleton_clear()


class GetDataTopic(SampleTopic):
    """
    SampleTopic that counts getdata() calls
    """
    NAME = 'getdata_topic'

    def __init__(self, conn_id, server):
        super().__init__(conn_id, server, initial={'x': 1})
        self.getdata_calls = 0

    async def getdata(self):
        self.getdata_calls += 1
        return await super().getdata()


class ReactiveTopic(BaseTopic):
    """
    A topic whose data is computed from a mutable raw source, so changes
    broadcast reactive_callback with the real old and new values
    """
    NAME = 'reactive'

    def __init__(self, conn_id, server):
        super().__init__(conn_id, server)
        self._raw = {'a': 1, 'b': 2}

    @async_reactive_source
    async def raw(self):
        return self._raw

    @async_reactive
    async def data(self):
        return await self.raw


class BareTopic(BaseTopic):
    """
    A topic that does not implement data, data() raises AccessDenied
    """
    NAME = 'bare'

    def __init__(self, conn_id, server):
        super().__init__(conn_id, server)


class TestOpSub:
    @pytest.mark.trio
    async def test_op_sub_sends_full(self):
        """op_sub with truthy data sends one full event"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_sub()
        server.send.assert_awaited_once_with(ResponseEvent(t='sample', o='full', v={'a': 1, 'b': 2}))

    @pytest.mark.parametrize('data', [{}, [], '', 0, None])
    @pytest.mark.trio
    async def test_op_sub_empty_data_sends_nothing(self, data):
        """op_sub with falsy data sends nothing"""
        server = mock_server()
        topic = SampleTopic('conn-1', server, initial=data)
        await topic.op_sub()
        server.send.assert_not_awaited()

    @pytest.mark.trio
    async def test_op_sub_non_dict_data(self):
        """any truthy data is sent as the full event value"""
        server = mock_server()
        topic = SampleTopic('conn-1', server, initial='hello')
        await topic.op_sub()
        server.send.assert_awaited_once_with(ResponseEvent(t='sample', o='full', v='hello'))

    @pytest.mark.trio
    async def test_op_sub_goes_through_getdata(self):
        """op_sub fetches data through the getdata wrapper"""
        server = mock_server()
        topic = GetDataTopic('conn-1', server)
        await topic.op_sub()
        assert topic.getdata_calls == 1
        server.send.assert_awaited_once_with(ResponseEvent(t='getdata_topic', o='full', v={'x': 1}))

    @pytest.mark.trio
    async def test_op_sub_unimplemented_data_raises(self):
        """BaseTopic.data raises AccessDenied when the subclass doesn't implement it"""
        server = mock_server()
        topic = BareTopic('conn-1', server)
        with pytest.raises(AccessDenied):
            await topic.op_sub()
        server.send.assert_not_awaited()


class TestReactiveCallback:
    @pytest.mark.parametrize('old, new', [
        ({'a': 1}, {'a': 2}),
        ('x', 'y'),
        (1, 2),
    ])
    @pytest.mark.trio
    async def test_full_event_only(self, old, new):
        """FULL_EVENT_ONLY topics push a single full event on any change"""
        server = mock_server()
        topic = FullOnlyTopic('conn-1', server)
        await topic.reactive_callback('data', old, new)
        server.send.assert_awaited_once_with(ResponseEvent(t='full_only', o='full', v=new))

    @pytest.mark.trio
    async def test_ignores_other_property_names(self):
        """changes of non-data properties are not pushed"""
        server = mock_server()
        topic = FullOnlyTopic('conn-1', server)
        await topic.reactive_callback('other', {'a': 1}, {'a': 2})
        server.send.assert_not_awaited()

    @pytest.mark.parametrize('old, new, expected', [
        # added key
        ({'a': 1}, {'a': 1, 'b': 2}, [('add', ['b'], 2)]),
        # removed key
        ({'a': 1, 'b': 2}, {'a': 1}, [('del', ['b'], None)]),
        # changed value
        ({'a': 1, 'b': 2}, {'a': 1, 'b': 3}, [('set', ['b'], 3)]),
        # nested dict change
        ({'a': {'x': 1}, 'b': 2}, {'a': {'x': 2}, 'b': 2}, [('set', ['a', 'x'], 2)]),
        # value replaced by a list
        ({'a': 1}, {'a': [1, 2]}, [('set', ['a'], [1, 2])]),
        # list changed, replaced wholesale
        ({'a': [1, 2]}, {'a': [1, 3]}, [('set', ['a'], [1, 3])]),
        # unchanged
        ({'a': 1}, {'a': 1}, []),
        # non-dict old value, root set
        ('root', {'a': 1}, [('set', [], {'a': 1})]),
        # non-dict new value, root set
        ({'a': 1}, 'root', [('set', [], 'root')]),
    ])
    @pytest.mark.trio
    async def test_diff_events(self, old, new, expected):
        """data changes are pushed as add/set/del diff events with exact key paths"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.reactive_callback('data', old, new)
        assert server.send.await_args_list == [
            call(ResponseEvent(t='sample', o=op, k=keys, v=value))
            for op, keys, value in expected
        ]

    @pytest.mark.trio
    async def test_diff_events_from_reactive_chain(self):
        """
        Mutating the raw source pushes diff events computed from the real
        old and new values (not _NOT_FOUND), through the whole reactive chain
        """
        server = mock_server()
        topic = ReactiveTopic('conn-1', server)
        await topic.op_sub()
        server.send.reset_mock()

        # dict change at depth 1
        await topic.raw.mutate({'a': {'x': 1}, 'b': 2})
        await trio.testing.wait_all_tasks_blocked()
        server.send.assert_awaited_once_with(ResponseEvent(t='reactive', o='set', k=['a'], v={'x': 1}))
        server.send.reset_mock()

        # deep nested change
        await topic.raw.mutate({'a': {'x': 2}, 'b': 2})
        await trio.testing.wait_all_tasks_blocked()
        server.send.assert_awaited_once_with(ResponseEvent(t='reactive', o='set', k=['a', 'x'], v=2))
        server.send.reset_mock()

        # unchanged value, no events
        await topic.raw.mutate({'a': {'x': 2}, 'b': 2})
        await trio.testing.wait_all_tasks_blocked()
        server.send.assert_not_awaited()
        server.send.reset_mock()

        # key removal
        await topic.raw.mutate({'a': {'x': 2}})
        await trio.testing.wait_all_tasks_blocked()
        server.send.assert_awaited_once_with(ResponseEvent(t='reactive', o='del', k=['b'], v=None))


class TestOpRpc:
    @pytest.mark.trio
    async def test_rpc_success(self):
        """successful rpc calls the method with converted args and responds without value"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='echo', value={'x': 5}, rpc_id='r1')
        assert topic.calls == [('echo', 5, 'hi')]
        server.send.assert_awaited_once_with(ResponseEvent(t='sample', i='r1'))

    @pytest.mark.trio
    async def test_rpc_unknown_method(self):
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='nope', value={}, rpc_id='r1')
        server.send.assert_awaited_once_with(
            ResponseEvent(t='sample', v='RPC method not found "nope"', i='r1'))

    @pytest.mark.trio
    async def test_rpc_validation_error(self):
        """invalid argument types respond with a ValidationError message"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='echo', value={'x': 'bad'}, rpc_id='r1')
        server.send.assert_awaited_once_with(ResponseEvent(
            t='sample', v='ValidationError: Invalid type for arg "x": Expected `int`, got `str`', i='r1'))

    @pytest.mark.trio
    async def test_rpc_missing_required_arg(self):
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='echo', value={}, rpc_id='r1')
        server.send.assert_awaited_once_with(
            ResponseEvent(t='sample', v='ValidationError: Missing arg: "x"', i='r1'))

    @pytest.mark.trio
    async def test_rpc_input_not_dict(self):
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='echo', value=['not', 'dict'], rpc_id='r1')
        server.send.assert_awaited_once_with(
            ResponseEvent(t='sample', v='ValidationError: Input is not a dict', i='r1'))

    @pytest.mark.trio
    async def test_rpc_input_none(self):
        """value=None is treated as a non-dict input"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='echo', value=None, rpc_id='r1')
        server.send.assert_awaited_once_with(
            ResponseEvent(t='sample', v='ValidationError: Input is not a dict', i='r1'))

    @pytest.mark.trio
    async def test_rpc_access_denied(self):
        """methods raising AccessDenied respond with an AccessDenied message"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='deny', value={}, rpc_id='r1')
        server.send.assert_awaited_once_with(
            ResponseEvent(t='sample', v='AccessDenied: denied', i='r1'))

    @pytest.mark.trio
    async def test_rpc_rpc_value_error(self):
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_rpc(func='bad_input', value={}, rpc_id='r1')
        server.send.assert_awaited_once_with(
            ResponseEvent(t='sample', v='RpcValueError: bad input', i='r1'))

    @pytest.mark.trio
    async def test_rpc_internal_error(self):
        """unexpected exceptions respond with an error and are logged"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        with logger.mock_capture_writer() as capture:
            await topic.op_rpc(func='explode', value={}, rpc_id='r1')
            assert capture.fd.any_contains('boom')
        server.send.assert_awaited_once_with(
            ResponseEvent(t='sample', v='ValueError: boom', i='r1'))


class TestOpUnsub:
    @pytest.mark.trio
    async def test_op_unsub_removes_singleton(self):
        """op_unsub releases the named singleton instance"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        assert SampleTopic.singleton_instances().get('conn-1') is topic
        await topic.op_unsub()
        assert 'conn-1' not in SampleTopic.singleton_instances()

    @pytest.mark.trio
    async def test_op_unsub_twice_no_error(self):
        """calling op_unsub twice does not raise"""
        server = mock_server()
        topic = SampleTopic('conn-1', server)
        await topic.op_unsub()
        await topic.op_unsub()
