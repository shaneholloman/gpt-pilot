import asyncio
from typing import Awaitable, Callable, Dict, Optional

from pydantic import ValidationError

from core.log import get_logger
from core.state.state_manager import StateManager
from core.ui.ipc_client import MESSAGE_SIZE_LIMIT, Message, MessageType

log = get_logger(__name__)


class IPCServer:
    """
    IPC server for handling requests from external clients.
    """

    def __init__(self, host: str, port: int, state_manager: StateManager):
        """
        Initialize the IPC server.

        :param host: Host to bind to.
        :param port: Port to listen on.
        :param state_manager: State manager instance.
        """
        self.host = host
        self.port = port
        self.state_manager = state_manager
        self.server = None
        self.handlers: Dict[MessageType, Callable[[Message, asyncio.StreamWriter], Awaitable[None]]] = {}
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up message handlers."""
        self.handlers[MessageType.EPICS_AND_TASKS] = self._handle_epics_and_tasks
        # Add more handlers as needed

    async def start(self) -> bool:
        """
        Start the IPC server.

        :return: True if server started successfully, False otherwise.
        """
        try:
            self.server = await asyncio.start_server(
                self._handle_client,
                self.host,
                self.port,
                limit=MESSAGE_SIZE_LIMIT,
            )
            log.info(f"IPC server started on {self.host}:{self.port}")
            return True
        except (OSError, ConnectionError) as err:
            log.error(f"Failed to start IPC server: {err}")
            return False

    async def stop(self):
        """Stop the IPC server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            log.info(f"IPC server on {self.host}:{self.port} stopped")
            self.server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handle client connection.

        :param reader: Stream reader.
        :param writer: Stream writer.
        """
        addr = writer.get_extra_info("peername")
        log.debug(f"New connection from {addr}")

        try:
            while True:
                # Read message length (4 bytes)
                length_bytes = await reader.readexactly(4)
                if not length_bytes:
                    break

                # Parse message length
                message_length = int.from_bytes(length_bytes, byteorder="big")

                # Read message data
                data = await reader.readexactly(message_length)
                if not data:
                    break

                # Parse message
                try:
                    message = Message.from_bytes(data)
                    await self._process_message(message, writer)
                except ValidationError as err:
                    log.error(f"Invalid message format: {err}")
                    await self._send_error(writer, "Invalid message format")
                except ValueError as err:
                    log.error(f"Error decoding message: {err}")
                    await self._send_error(writer, "Error decoding message")

        except asyncio.IncompleteReadError:
            log.debug(f"Client {addr} disconnected")
        except (ConnectionResetError, BrokenPipeError) as err:
            log.debug(f"Connection to {addr} lost: {err}")
        finally:
            writer.close()
            await writer.wait_closed()
            log.debug(f"Connection to {addr} closed")

    async def _process_message(self, message: Message, writer: asyncio.StreamWriter):
        """
        Process incoming message.

        :param message: Incoming message.
        :param writer: Stream writer to send response.
        """
        log.debug(f"Received message of type {message.type} with request ID {message.request_id}")

        handler = self.handlers.get(message.type)
        if handler:
            await handler(message, writer)
        else:
            log.warning(f"No handler for message type {message.type}")
            request_id = getattr(message, "request_id", None)
            await self._send_error(writer, f"Unsupported message type: {message.type}", request_id)

    async def _send_response(self, writer: asyncio.StreamWriter, message: Message):
        """
        Send response to client.

        :param writer: Stream writer.
        :param message: Message to send.
        """
        data = message.to_bytes()
        try:
            writer.write(len(data).to_bytes(4, byteorder="big"))
            writer.write(data)
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError) as err:
            log.error(f"Failed to send response: {err}")

    async def _send_error(self, writer: asyncio.StreamWriter, error_message: str, request_id: Optional[str] = None):
        """
        Send error response to client.

        :param writer: Stream writer.
        :param error_message: Error message.
        :param request_id: Optional request ID to include in the response.
        """
        message = Message(type=MessageType.RESPONSE, content={"error": error_message}, request_id=request_id)
        await self._send_response(writer, message)

    async def _handle_epics_and_tasks(self, message: Message, writer: asyncio.StreamWriter):
        """
        Handle request for epics and tasks.

        :param message: Request message.
        :param writer: Stream writer to send response.
        """
        try:
            # Get current state
            current_state = self.state_manager.current_state

            # Extract epics and tasks
            epics = current_state.epics if current_state.epics else []
            tasks = current_state.tasks if current_state.tasks else []

            # Send response with the same request_id from the incoming message
            response = Message(
                type=MessageType.EPICS_AND_TASKS,
                content={"epics": epics, "tasks": tasks},
                request_id=message.request_id,  # Include the request_id from the incoming message
            )
            log.debug(f"Sending epics and tasks response with request_id: {message.request_id}")
            await self._send_response(writer, response)

        except Exception as err:
            log.error(f"Error handling epics and tasks request: {err}", exc_info=True)
            await self._send_error(writer, f"Internal server error: {str(err)}", message.request_id)
