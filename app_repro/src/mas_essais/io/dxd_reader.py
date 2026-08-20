from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from mas_essais.paths import PROJECT_ROOT

BASE_DIR = PROJECT_ROOT
SDK_PYTHON_DIR = BASE_DIR / "DWDataReader_v5_0_4" / "examples" / "Python"

if str(SDK_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_PYTHON_DIR))

from DWDataReaderHeader import (  # noqa: E402
    DWChannel,
    DWChannelProps,
    DWChannelType,
    DWFileInfo,
    DWStatus,
    READER_HANDLE,
    decode_bytes,
    load_library,
)


def _check_error(lib: ctypes.CDLL, status: DWStatus) -> None:
    if status == DWStatus.DWSTAT_OK:
        return
    if status == DWStatus.DWSTAT_ERROR_CAN_NOT_SUPPORTED:
        return

    from DWDataReaderHeader import check_error

    check_error(lib, status)


class Channel:
    def __init__(self, reader: "DewesoftFile", channel: DWChannel):
        self._reader = reader
        self._channel = channel
        self.index = int(channel.index)
        self.name = decode_bytes(channel.name)
        self.unit = decode_bytes(channel.unit)
        self.array_size = int(channel.array_size)

    def __str__(self) -> str:
        if self.unit:
            return f"{self.name} ({self.unit})"
        return self.name

    def _channel_type(self) -> DWChannelType:
        buf = ctypes.create_string_buffer(ctypes.sizeof(ctypes.c_int))
        buf_len = ctypes.c_int(ctypes.sizeof(ctypes.c_int))
        p_buf = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))
        _check_error(
            self._reader._lib,
            self._reader._lib.DWIGetChannelProps(
                self._reader._handle,
                self.index,
                DWChannelProps.DW_CH_TYPE,
                p_buf,
                ctypes.byref(buf_len),
            ),
        )
        value = ctypes.cast(p_buf, ctypes.POINTER(ctypes.c_int)).contents.value
        return DWChannelType(value)

    def series(self) -> pd.Series:
        sample_count = ctypes.c_longlong()
        _check_error(
            self._reader._lib,
            self._reader._lib.DWIGetScaledSamplesCount(
                self._reader._handle,
                self.index,
                ctypes.byref(sample_count),
            ),
        )

        n_samples = int(sample_count.value)
        if n_samples <= 0:
            return pd.Series(dtype=float)

        array_size = max(1, self.array_size)
        total_count = n_samples * array_size
        samples = (ctypes.c_double * total_count)()

        channel_type = self._channel_type()
        timestamps = None
        if channel_type == DWChannelType.DW_CH_TYPE_ASYNC:
            timestamps = (ctypes.c_double * n_samples)()

        _check_error(
            self._reader._lib,
            self._reader._lib.DWIGetScaledSamples(
                self._reader._handle,
                self.index,
                0,
                sample_count,
                samples,
                timestamps,
            ),
        )

        values = np.ctypeslib.as_array(samples).astype(np.float64, copy=True)
        if array_size > 1:
            values = values.reshape(n_samples, array_size)[:, 0]

        if timestamps is not None:
            index = np.ctypeslib.as_array(timestamps).astype(np.float64, copy=True)
        else:
            sample_rate = self._reader.sample_rate
            if not np.isfinite(sample_rate) or sample_rate <= 0:
                sample_rate = 1.0
            index = np.arange(n_samples, dtype=np.float64) / sample_rate

        return pd.Series(values, index=index)


class DewesoftFile:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lib = load_library(str(SDK_PYTHON_DIR / "DWDataReaderLib64.so"))
        self._handle = READER_HANDLE()
        self._file_info = DWFileInfo(0, 0, 0)
        self.channels: list[Channel] = []
        self.sample_rate = float("nan")

    def __enter__(self) -> "DewesoftFile":
        _check_error(self._lib, self._lib.DWICreateReader(ctypes.byref(self._handle)))
        _check_error(
            self._lib,
            self._lib.DWIOpenDataFile(
                self._handle,
                ctypes.c_char_p(self.path.encode("utf-8")),
                ctypes.byref(self._file_info),
            ),
        )
        self.sample_rate = float(self._file_info.sample_rate)
        self.channels = self._load_channels()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self._lib.DWICloseDataFile(self._handle)
        finally:
            self._lib.DWIDestroyReader(self._handle)

    def __iter__(self) -> Iterator[Channel]:
        return iter(self.channels)

    def _load_channels(self) -> list[Channel]:
        channel_count = ctypes.c_int()
        _check_error(
            self._lib,
            self._lib.DWIGetChannelListCount(self._handle, ctypes.byref(channel_count)),
        )

        raw_channels = (DWChannel * channel_count.value)()
        _check_error(
            self._lib,
            self._lib.DWIGetChannelList(self._handle, raw_channels),
        )
        return [Channel(self, raw_channels[i]) for i in range(channel_count.value)]


def open(path: str | Path) -> DewesoftFile:
    return DewesoftFile(path)


__all__ = ["open", "DewesoftFile", "Channel"]
