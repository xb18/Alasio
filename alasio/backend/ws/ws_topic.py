from typing import TYPE_CHECKING

from msgspec import DecodeError, ValidationError

from alasio.backend.reactive.base_topic import BaseTopic as BaseMixin
from alasio.backend.reactive.event import AccessDenied, ResponseEvent, RpcValueError
from alasio.backend.reactive.rx_trio import AsyncReactiveCallback, async_reactive
from alasio.ext.deep import deep_iter_patch
from alasio.ext.singleton import SingletonNamed
from alasio.logger import logger

if TYPE_CHECKING:
    # For IDE typehint, avoid recursive import
    from .ws_server import WebsocketTopicServer


class BaseTopic(AsyncReactiveCallback, BaseMixin, metaclass=SingletonNamed):
    # Topic-level electron restriction: when True, subscribing to this
    # topic and every rpc under it requires a valid electron token on the
    # connection (verified at operation time, never cached). Default
    # topics are public; mark the sensitive ones explicitly.
    REQUIRE_ELECTRON = False

    def __init__(self, conn_id, server: "WebsocketTopicServer"):
        """
        Create a data topic, that supports subscribe/unsubscribe
        and sends data changes once subscribed

        Args:
            conn_id (str):
        """
        self.conn_id = conn_id
        self.server = server

    def __str__(self):
        return f'{self.topic_name()}({self.conn_id})>'

    def _check_electron(self):
        """
        Verify the connection's electron token in real time.

        Raises:
            ElectronOnlyError: When the connection has no valid token
        """
        from alasio.backend.mpipe.token_backend import token_table
        from alasio.backend.reactive.event import ElectronOnlyError

        if not token_table.verify(self.server.auth_token):
            raise ElectronOnlyError('Electron token required')

    @async_reactive
    async def data(self):
        """
        Subclasses should implement how to get data.

        Examples:
            @reactive
            async def data(self):
                # Do simple data filtering
                return Shared().data.get('lang', 'cn')
                # Put the real data fetching on thread to avoid blocking event loop
                return await run_sync(ConfigScanSource.scan)
        """
        raise AccessDenied('Topic did not implement "data" method')

    async def getdata(self):
        """
        A wrapper function to get data.
        So you can do some pre-process and post-process
        """
        return await self.data

    async def op_sub(self):
        """
        Subscribe to this topic, once subscribe the data will flow

        When receiving a "sub" event from client, the data flows
        --> Topic.subscribe()
        --> Topic.getdata()
        --> Topic.data
            data is returned and observer chain is built

        Changes may come from:
        - backend background task that updates data
        - external database changes
        - another topic changes the dependency ot current topic
        - another client changes the data of current topic

        When receiving a dependency change, the data flows:
        --> DataSource.data.mutate(self, data)
        --> @async_reactive
            changes will broadcast to callback function
            --> reactive_callback
            --> sender.send()
            and also broadcast to each observer
            --> Observer1.data
            --> Observer2.data
        """
        data = await self.getdata()

        # prepare event
        topic = self.topic_name()
        event = ResponseEvent(t=topic, o='full', v=data)

        # send event
        if data:
            await self.server.send(event)

    async def reactive_callback(self, name, old, new):
        """
        Callback function to send diff when `self.data` is re-computed
        """
        if name != 'data':
            return
        topic = self.topic_name()
        if self.FULL_EVENT_ONLY:
            event = ResponseEvent(t=topic, o='full', v=new)
            await self.server.send(event)
        else:
            for op, keys, value in deep_iter_patch(old, new):
                event = ResponseEvent(t=topic, o=op, k=keys, v=value)
                await self.server.send(event)

    async def op_unsub(self):
        """
        Release current data topic
        """
        cls = self.__class__
        cls.singleton_remove(self.conn_id)

    async def op_rpc(self, func, value, rpc_id):
        """
        Do RPC call on current topic

        Args:
            func (str): RPC method name
            value (Any): RPC method args
            rpc_id (str):
        """
        try:
            method = self.rpc_methods[func]
        except KeyError:
            msg = f'RPC method not found "{func}"'
            event = ResponseEvent(t=self.topic_name(), v=msg, i=rpc_id)
            await self.server.send(event)
            return

        # Electron check must happen BEFORE the call executes (never
        # inside the method body): a rejected request never ran, so a
        # renewal retry is a first execution, not a re-execution
        # (idempotency). Inside the try so the existing except branch
        # returns the error response carrying the rpc_id.
        try:
            if method.require_electron or self.REQUIRE_ELECTRON:
                self._check_electron()
            await method.call_async(self, value)
        except (ValidationError, DecodeError, UnicodeDecodeError, AccessDenied, RpcValueError) as e:
            # input errors
            msg = f'{e.__class__.__name__}: {e}'
            event = ResponseEvent(t=self.topic_name(), v=msg, i=rpc_id)
            await self.server.send(event)
            return
        except Exception as e:
            # unexpected internal errors
            logger.exception(e)
            msg = f'{e.__class__.__name__}: {e}'
            event = ResponseEvent(t=self.topic_name(), v=msg, i=rpc_id)
            await self.server.send(event)
            return

        # success
        # RPC success has no return value sent, omitting "v" means success, having "v" means error
        # The real RPC response will go through existing topic subscription
        event = ResponseEvent(t=self.topic_name(), i=rpc_id)
        await self.server.send(event)
        return
