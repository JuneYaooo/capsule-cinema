"""Binary framing for the official Doubao bidirectional TTS WebSocket API.

The wire contract is documented by Volcengine's ``TTS Websocket Bidirection
protocols`` attachment. Keep this module transport-only so it can be tested
without credentials or a network connection.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from enum import IntEnum


class MessageType(IntEnum):
    FULL_CLIENT_REQUEST = 0b0001
    FULL_SERVER_RESPONSE = 0b1001
    AUDIO_ONLY_SERVER = 0b1011
    ERROR = 0b1111


class MessageFlag(IntEnum):
    NO_SEQUENCE = 0
    POSITIVE_SEQUENCE = 0b0001
    LAST_NO_SEQUENCE = 0b0010
    NEGATIVE_SEQUENCE = 0b0011
    WITH_EVENT = 0b0100


class EventType(IntEnum):
    START_CONNECTION = 1
    FINISH_CONNECTION = 2
    CONNECTION_STARTED = 50
    CONNECTION_FAILED = 51
    CONNECTION_FINISHED = 52
    START_SESSION = 100
    CANCEL_SESSION = 101
    FINISH_SESSION = 102
    SESSION_STARTED = 150
    SESSION_CANCELED = 151
    SESSION_FINISHED = 152
    SESSION_FAILED = 153
    USAGE_RESPONSE = 154
    TASK_REQUEST = 200
    TTS_SENTENCE_START = 350
    TTS_SENTENCE_END = 351
    TTS_RESPONSE = 352
    TTS_ENDED = 359
    TTS_SUBTITLE = 364


_CONNECTION_EVENTS = {
    EventType.START_CONNECTION,
    EventType.FINISH_CONNECTION,
    EventType.CONNECTION_STARTED,
    EventType.CONNECTION_FAILED,
    EventType.CONNECTION_FINISHED,
}


@dataclass
class Message:
    """One Volcengine WebSocket protocol message."""

    message_type: MessageType
    flag: MessageFlag = MessageFlag.WITH_EVENT
    event: EventType | int = 0
    session_id: str = ""
    connect_id: str = ""
    sequence: int = 0
    error_code: int = 0
    payload: bytes = b""
    version: int = 1
    header_size_words: int = 1
    serialization: int = 1
    compression: int = 0

    def to_bytes(self) -> bytes:
        buffer = io.BytesIO()
        buffer.write(
            bytes(
                [
                    (self.version << 4) | self.header_size_words,
                    (int(self.message_type) << 4) | int(self.flag),
                    (self.serialization << 4) | self.compression,
                    0,
                ]
            )
        )
        if self.flag == MessageFlag.WITH_EVENT:
            buffer.write(struct.pack(">i", int(self.event)))
            if self.event not in _CONNECTION_EVENTS:
                self._write_sized_bytes(buffer, self.session_id.encode("utf-8"))
            if self.event in {
                EventType.CONNECTION_STARTED,
                EventType.CONNECTION_FAILED,
                EventType.CONNECTION_FINISHED,
            }:
                self._write_sized_bytes(buffer, self.connect_id.encode("utf-8"))
        if self.flag in {MessageFlag.POSITIVE_SEQUENCE, MessageFlag.NEGATIVE_SEQUENCE}:
            buffer.write(struct.pack(">i", self.sequence))
        if self.message_type == MessageType.ERROR:
            buffer.write(struct.pack(">I", self.error_code))
        self._write_sized_bytes(buffer, self.payload)
        return buffer.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        if len(data) < 4:
            raise ValueError(f"Doubao TTS frame is too short: {len(data)} bytes")
        buffer = io.BytesIO(data)
        version_and_size = buffer.read(1)[0]
        type_and_flag = buffer.read(1)[0]
        serialization_and_compression = buffer.read(1)[0]
        buffer.read(1)

        header_size_words = version_and_size & 0x0F
        header_bytes = header_size_words * 4
        if header_bytes < 4 or header_bytes > len(data):
            raise ValueError(f"Invalid Doubao TTS header size: {header_bytes}")
        if header_bytes > 4:
            buffer.read(header_bytes - 4)

        try:
            message_type = MessageType(type_and_flag >> 4)
        except ValueError as exc:
            raise ValueError(f"Unsupported Doubao TTS message type: {type_and_flag >> 4}") from exc
        try:
            flag = MessageFlag(type_and_flag & 0x0F)
        except ValueError as exc:
            raise ValueError(f"Unsupported Doubao TTS message flag: {type_and_flag & 0x0F}") from exc

        message = cls(
            message_type=message_type,
            flag=flag,
            version=version_and_size >> 4,
            header_size_words=header_size_words,
            serialization=serialization_and_compression >> 4,
            compression=serialization_and_compression & 0x0F,
        )
        if flag in {MessageFlag.POSITIVE_SEQUENCE, MessageFlag.NEGATIVE_SEQUENCE}:
            message.sequence = cls._read_int32(buffer, "sequence")
        if message_type == MessageType.ERROR:
            message.error_code = cls._read_uint32(buffer, "error code")
        if flag == MessageFlag.WITH_EVENT:
            event_value = cls._read_int32(buffer, "event")
            try:
                message.event = EventType(event_value)
            except ValueError:
                message.event = event_value
            if message.event not in _CONNECTION_EVENTS:
                message.session_id = cls._read_sized_bytes(buffer, "session id").decode("utf-8")
            if message.event in {
                EventType.CONNECTION_STARTED,
                EventType.CONNECTION_FAILED,
                EventType.CONNECTION_FINISHED,
            }:
                message.connect_id = cls._read_sized_bytes(buffer, "connection id").decode("utf-8")
        message.payload = cls._read_sized_bytes(buffer, "payload")
        if buffer.read(1):
            raise ValueError("Unexpected trailing bytes in Doubao TTS frame")
        return message

    @staticmethod
    def _write_sized_bytes(buffer: io.BytesIO, value: bytes) -> None:
        buffer.write(struct.pack(">I", len(value)))
        buffer.write(value)

    @staticmethod
    def _read_uint32(buffer: io.BytesIO, label: str) -> int:
        value = buffer.read(4)
        if len(value) != 4:
            raise ValueError(f"Incomplete Doubao TTS {label}")
        return struct.unpack(">I", value)[0]

    @classmethod
    def _read_int32(cls, buffer: io.BytesIO, label: str) -> int:
        value = buffer.read(4)
        if len(value) != 4:
            raise ValueError(f"Incomplete Doubao TTS {label}")
        return struct.unpack(">i", value)[0]

    @classmethod
    def _read_sized_bytes(cls, buffer: io.BytesIO, label: str) -> bytes:
        size = cls._read_uint32(buffer, f"{label} length")
        value = buffer.read(size)
        if len(value) != size:
            raise ValueError(f"Incomplete Doubao TTS {label}: expected {size}, got {len(value)}")
        return value


def client_event(event: EventType, payload: bytes = b"{}", session_id: str = "") -> bytes:
    """Build an upstream full-client request for one protocol event."""

    return Message(
        message_type=MessageType.FULL_CLIENT_REQUEST,
        flag=MessageFlag.WITH_EVENT,
        event=event,
        session_id=session_id,
        payload=payload,
    ).to_bytes()
