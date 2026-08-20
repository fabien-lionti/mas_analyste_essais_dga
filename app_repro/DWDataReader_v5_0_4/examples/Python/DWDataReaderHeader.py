"""
Python wrapper for DWDataReaderLibTypes.h using ctypes
This file defines the necessary structures and enums to interface with the DWDataReader shared library
"""

import ctypes
import platform
import os
from enum import IntEnum, auto

if platform.system() == 'Linux':
    # On Linux systems, load the shared library with .so extension
    def load_library(custom_path=None):
        if custom_path is not None:
            return ctypes.CDLL(custom_path)
        # Load 64bit or 32bit shared library depending on the architecture
        if platform.architecture()[0] == '64bit':
            lib_name = 'DWDataReaderLib64.so'
        else:
            lib_name = 'DWDataReaderLib.so'
        try:
            return ctypes.CDLL(os.path.join(os.path.dirname(__file__), lib_name))
        except OSError:
            return ctypes.CDLL(lib_name)
    # Define int64_t equivalent for Linux
    int64_t = ctypes.c_longlong

elif platform.system() == 'Darwin':
    # On macOS systems, load the dynamic library with .dylib extension
    def load_library(custom_path=None):
        if custom_path is not None:
            return ctypes.CDLL(custom_path)
        # Load 64bit or 32bit dynamic library depending on the architecture
        if platform.architecture()[0] == '64bit':
            lib_name = 'DWDataReaderLib64.dylib'
        else:
            lib_name = 'DWDataReaderLib.dylib'
        try:
            return ctypes.CDLL(os.path.join(os.path.dirname(__file__), lib_name))
        except OSError:
            return ctypes.CDLL(lib_name)
    # Define int64_t equivalent for macOS
    int64_t = ctypes.c_longlong

else:
    # On Windows systems, load the DLL
    def load_library(custom_path=None):
        if custom_path is not None:
            return ctypes.WinDLL(custom_path)
        # Load 64bit or 32bit DLL depending on the architecture
        if platform.architecture()[0] == '64bit':
            dll_name = 'DWDataReaderLib64.dll'
        else:
            dll_name = 'DWDataReaderLib.dll'
        # Try to load the DLL
        try:
            return ctypes.WinDLL(os.path.join(os.path.dirname(__file__), dll_name))
        except OSError:
            return ctypes.WinDLL(dll_name)
    # Windows already has __int64
    int64_t = ctypes.c_longlong


# Define READER_HANDLE type
READER_HANDLE = ctypes.c_void_p

INT_SIZE = ctypes.sizeof(ctypes.c_int)
DOUBLE_SIZE = ctypes.sizeof(ctypes.c_double)

# Define enums
class DWStatus(IntEnum):
    """Status codes returned from library function calls"""
    DWSTAT_OK = 0
    DWSTAT_ERROR = 1
    DWSTAT_ERROR_FILE_CANNOT_OPEN = 2
    DWSTAT_ERROR_FILE_ALREADY_IN_USE = 3
    DWSTAT_ERROR_FILE_CORRUPT = 4
    DWSTAT_ERROR_NO_MEMORY_ALLOC = 5
    DWSTAT_ERROR_CREATE_DEST_FILE = 6
    DWSTAT_ERROR_EXTRACTING_FILE = 7
    DWSTAT_ERROR_CANNOT_OPEN_EXTRACTED_FILE = 8
    DWSTAT_ERROR_INVALID_IB_LEVEL = 9
    DWSTAT_ERROR_CAN_NOT_SUPPORTED = 10
    DWSTAT_ERROR_INVALID_READER = 11
    DWSTAT_ERROR_INVALID_INDEX = 12
    DWSTAT_ERROR_INSUFFICENT_BUFFER = 13


class DWChannelProps(IntEnum):
    """Specifies the properties that can be retrieved for a channel."""
    DW_DATA_TYPE = 0
    DW_DATA_TYPE_LEN_BYTES = 1
    DW_CH_INDEX = 2
    DW_CH_INDEX_LEN = 3
    DW_CH_TYPE = 4
    DW_CH_SCALE = 5
    DW_CH_OFFSET = 6
    DW_CH_XML = 7
    DW_CH_XML_LEN = 8
    DW_CH_XMLPROPS = 9
    DW_CH_XMLPROPS_LEN = 10
    DW_CH_CUSTOMPROPS = 11
    DW_CH_CUSTOMPROPS_COUNT = 12
    DW_CH_LONGNAME = 13
    DW_CH_LONGNAME_LEN = 14


class DWChannelType(IntEnum):
    """Specifies the type of channel."""
    DW_CH_TYPE_SYNC = 0
    DW_CH_TYPE_ASYNC = 1
    DW_CH_TYPE_SV = 2


class DWCustomPropValueType(IntEnum):
    """Specifies the type of custom property value."""
    DW_CUSTOM_PROP_VAL_TYPE_EMPTY = 0
    DW_CUSTOM_PROP_VAL_TYPE_INT64 = 1
    DW_CUSTOM_PROP_VAL_TYPE_DOUBLE = 2
    DW_CUSTOM_PROP_VAL_TYPE_STRING = 3


class DWEventType(IntEnum):
    """Specifies the type of event."""
    etStart = 1
    etStop = 2
    etTrigger = 3
    etVStart = 11
    etVStop = 12
    etKeyboard = 20
    etNotice = 21
    etVoice = 22
    etPicture = 23
    etModule = 24
    etAlarm = 25
    etCursorInfo = 26
    etAlarmLevel = 27


class DWStoringType(IntEnum):
    """Specifies the type data storing mode."""
    ST_ALWAYS_FAST = 0
    ST_ALWAYS_SLOW = 1
    ST_FAST_ON_TRIGGER = 2
    ST_FAST_ON_TRIGGER_SLOW_OTH = 3


class DWDataType(IntEnum):
    """Specifies the channel data type."""
    dtByte = 0
    dtShortInt = 1
    dtSmallInt = 2
    dtWord = 3
    dtInteger = 4
    dtSingle = 5
    dtInt64 = 6
    dtDouble = 7
    dtLongword = 8
    dtComplexSingle = 9
    dtComplexDouble = 10
    dtText = 11
    dtBinary = 12
    dtCANPortData = 13
    dtCANFDPortData = 14
    dtBytes8 = 15
    dtBytes16 = 16
    dtBytes32 = 17
    dtBytes64 = 18


# Define structures
class DWFileInfo(ctypes.Structure):
    """Represents metadata about a data file. (Deprecated, use DWMeasurementInfo instead)"""
    _pack_ = 1
    _fields_ = [
        ("sample_rate", ctypes.c_double),
        ("start_store_time", ctypes.c_double),
        ("duration", ctypes.c_double)
    ]


class DWMeasurementInfo(ctypes.Structure):
    """Structure with information about the current measurement."""
    _pack_ = 1
    _fields_ = [
        ("sample_rate", ctypes.c_double),
        ("start_measure_time", ctypes.c_double),
        ("start_store_time", ctypes.c_double),
        ("duration", ctypes.c_double)
    ]


class DWChannel(ctypes.Structure):
    """Structure represents a Dewesoft channel."""
    _pack_ = 1
    _fields_ = [
        ("index", ctypes.c_int),
        ("name", ctypes.c_char * 100),
        ("unit", ctypes.c_char * 20),
        ("description", ctypes.c_char * 200),
        ("color", ctypes.c_uint),
        ("array_size", ctypes.c_int),
        ("data_type", ctypes.c_int)  # Using DWDataType enum
    ]


class DWComplex(ctypes.Structure):
    """Represents a complex number with real and imaginary components."""
    _pack_ = 1
    _fields_ = [
        ("re", ctypes.c_double),
        ("im", ctypes.c_double)
    ]


class DWEvent(ctypes.Structure):
    """Represents an event in datafile."""
    _pack_ = 1
    _fields_ = [
        ("event_type", ctypes.c_int),  # Using DWEventType enum
        ("time_stamp", ctypes.c_double),
        ("event_text", ctypes.c_char * 200)
    ]


class DWReducedValue(ctypes.Structure):
    """Represents a set of agregated data for samples over a specific time interval."""
    _pack_ = 1
    _fields_ = [
        ("time_stamp", ctypes.c_double),
        ("ave", ctypes.c_double),
        ("min", ctypes.c_double),
        ("max", ctypes.c_double),
        ("rms", ctypes.c_double)
    ]


class DWArrayInfo(ctypes.Structure):
    """Represents information about an axis on and array channel."""
    _pack_ = 1
    _fields_ = [
        ("index", ctypes.c_int),
        ("name", ctypes.c_char * 100),
        ("unit", ctypes.c_char * 20),
        ("size", ctypes.c_int)
    ]


# Union for DWCustomProp
class DWCustomPropValue(ctypes.Union):
    """Union containing different types of custom property values."""
    _fields_ = [
        ("int64Val", int64_t),
        ("doubleVal", ctypes.c_double),
        ("strVal", ctypes.c_char * 100)
    ]


class DWCustomProp(ctypes.Structure):
    """Represents a custom property associated with a channel."""
    _pack_ = 1
    _fields_ = [
        ("key", ctypes.c_char * 100),
        ("valueType", ctypes.c_int),  # Using DWCustomPropValueType enum
        ("value", DWCustomPropValue)
    ]


class DWBinarySample(ctypes.Structure):
    """Binary data structure."""
    _pack_ = 1
    _fields_ = [
        ("position", int64_t),
        ("size", int64_t)
    ]

# Helper function to create a string buffer with the right encoding
def create_string_buffer(string_value, buffer_size=None):
    """Create a string buffer with proper encoding."""
    if isinstance(string_value, str):
        return ctypes.create_string_buffer(string_value.encode('utf-8'), buffer_size)
    return ctypes.create_string_buffer(string_value, buffer_size)


# Helper function to decode bytes to string
def decode_bytes(byte_string):
    """Convert bytes to string with proper decoding."""
    if isinstance(byte_string, bytes):
        return byte_string.decode('utf-8', errors='replace').rstrip('\x00')
    return byte_string

def check_error(lib: ctypes.CDLL, status: DWStatus):
    """Check the status returned by the library functions."""

    if status == DWStatus.DWSTAT_OK:
        return

    if status == DWStatus.DWSTAT_ERROR_CAN_NOT_SUPPORTED:
        print("Warning: CAN decoder functionality is limited. Value may be decoded incorrectly.")
        return
    
    err_msg_len = ctypes.c_int(1024)
    err_msg = create_string_buffer(err_msg_len.value)
    err_status = ctypes.c_int(DWStatus.DWSTAT_OK)

    while lib.DWGetLastStatus(ctypes.byref(err_status), err_msg, ctypes.byref(err_msg_len)) == DWStatus.DWSTAT_ERROR_NO_MEMORY_ALLOC:
        err_msg = create_string_buffer(err_msg_len.value)
    
    raise RuntimeError(f"Error {status}: {decode_bytes(err_msg.value)}")    