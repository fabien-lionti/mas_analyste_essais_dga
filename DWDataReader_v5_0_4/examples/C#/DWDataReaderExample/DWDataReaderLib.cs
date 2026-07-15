using System;
using System.Runtime.InteropServices;
using System.Text;

namespace DWDataReader
{
    /// <summary>
    /// C# wrapper for the DWDataReaderLib library
    /// </summary>
    public static class DWDataReaderLib
    {
        #region Constants

#if (_WIN64)
        private const string DllName = "DWDataReaderLib64.dll";
#else
        private const string DllName = "DWDataReaderLib.dll";
#endif


        private const int DefaultStringBufferSize = 200;

#endregion

        #region Enums

        /// <summary>
        /// Status codes returned from library function calls
        /// </summary>
        public enum DWStatus
        {
            DWSTAT_OK = 0,                             // Operation completed successfully
            DWSTAT_ERROR = 1,                          // Generic error occurred in the DLL
            DWSTAT_ERROR_FILE_CANNOT_OPEN = 2,         // Unable to open the specified file
            DWSTAT_ERROR_FILE_ALREADY_IN_USE = 3,      // File is already in use by another process
            DWSTAT_ERROR_FILE_CORRUPT = 4,             // File is corrupted or has invalid format
            DWSTAT_ERROR_NO_MEMORY_ALLOC = 5,          // Memory allocation failed
            DWSTAT_ERROR_CREATE_DEST_FILE = 6,         // Failed to create destination file (d7z files only)
            DWSTAT_ERROR_EXTRACTING_FILE = 7,          // Error occurred while extracting data (d7z files only)
            DWSTAT_ERROR_CANNOT_OPEN_EXTRACTED_FILE = 8, // Unable to open extracted file (d7z files only)
            DWSTAT_ERROR_INVALID_IB_LEVEL = 9,         // Invalid IB level specified
            DWSTAT_ERROR_CAN_NOT_SUPPORTED = 10,       // Feature or operation not supported on CAN channel
            DWSTAT_ERROR_INVALID_READER = 11,          // Invalid reader handle
            DWSTAT_ERROR_INVALID_INDEX = 12,           // Invalid index specified
            DWSTAT_ERROR_INSUFFICENT_BUFFER = 13,      // Insufficient buffer size provided
        }

        /// <summary>
        /// Specifies the properties that can be retrieved for a channel
        /// </summary>
        public enum DWChannelProps
        {
            DW_DATA_TYPE = 0,               // Data type
            DW_DATA_TYPE_LEN_BYTES = 1,     // Length of data type in bytes
            DW_CH_INDEX = 2,                // Channel index
            DW_CH_INDEX_LEN = 3,            // Length of channel index
            DW_CH_TYPE = 4,                 // Type
            DW_CH_SCALE = 5,                // Scale
            DW_CH_OFFSET = 6,               // Offset
            DW_CH_XML = 7,                  // XML structure of channel
            DW_CH_XML_LEN = 8,              // Length of XML structure
            DW_CH_XMLPROPS = 9,             // XML structure properties
            DW_CH_XMLPROPS_LEN = 10,        // Length of XML structure properties
            DW_CH_CUSTOMPROPS = 11,         // XML structure custom properties
            DW_CH_CUSTOMPROPS_COUNT = 12,   // Length of XML structure custom properties
            DW_CH_LONGNAME = 13,            // Long name of channel
            DW_CH_LONGNAME_LEN = 14         // Length of long name of channel
        }

        /// <summary>
        /// Specifies the type of channel
        /// </summary>
        public enum DWChannelType
        {
            DW_CH_TYPE_SYNC = 0,    // Synchronous channel
            DW_CH_TYPE_ASYNC = 1,   // Asynchronous channel
            DW_CH_TYPE_SV = 2       // Single value channel
        }

        /// <summary>
        /// Specifies the type of custom property value
        /// </summary>
        public enum DWCustomPropValueType
        {
            DW_CUSTOM_PROP_VAL_TYPE_EMPTY = 0,   // No value
            DW_CUSTOM_PROP_VAL_TYPE_INT64 = 1,   // 64-bit integer value
            DW_CUSTOM_PROP_VAL_TYPE_DOUBLE = 2,  // Double precision floating-point value
            DW_CUSTOM_PROP_VAL_TYPE_STRING = 3,  // String value
        }

        /// <summary>
        /// Specifies the type of event
        /// </summary>
        public enum DWEventType
        {
            etStart = 1,       // Recording start
            etStop = 2,        // Recording stop
            etTrigger = 3,     // Trigger event
            etVStart = 11,     // Video recording start
            etVStop = 12,      // Video recording stop
            etKeyboard = 20,   // Keyboard input
            etNotice = 21,     // System notice
            etVoice = 22,      // Voice annotation
            etPicture = 23,    // Picture capture
            etModule = 24,     // Module event
            etAlarm = 25,      // Alarm notification
            etCursorInfo = 26, // Cursor information
            etAlarmLevel = 27  // Alarm level change
        }

        /// <summary>
        /// Specifies the type data storing mode
        /// </summary>
        public enum DWStoringType
        {
            ST_ALWAYS_FAST = 0,                  // Always fast storing
            ST_ALWAYS_SLOW = 1,                  // Always slow storing
            ST_FAST_ON_TRIGGER = 2,              // Fast on trigger storing
            ST_FAST_ON_TRIGGER_SLOW_OTH = 3,     // Fast on trigger slow otherwise storing
        }

        /// <summary>
        /// Specifies the channel data type
        /// </summary>
        public enum DWDataType
        {
            dtByte = 0,             // Byte data type
            dtShortInt = 1,         // Short integer data type
            dtSmallInt = 2,         // Small integer data type
            dtWord = 3,             // Word data type
            dtInteger = 4,          // Integer data type
            dtSingle = 5,           // Single precision floating point data type
            dtInt64 = 6,            // 64-bit integer data type
            dtDouble = 7,           // Double precision floating point data type
            dtLongword = 8,         // Long word data type
            dtComplexSingle = 9,    // Complex single precision data type
            dtComplexDouble = 10,   // Complex double precision data type
            dtText = 11,            // Text data type
            dtBinary = 12,          // Binary data type
            dtCANPortData = 13,     // CAN port data type
            dtCANFDPortData = 14,   // CAN FD port data type
            dtBytes8 = 15,          // 8 bytes data type
            dtBytes16 = 16,         // 16 bytes data type
            dtBytes32 = 17,         // 32 bytes data type
            dtBytes64 = 18          // 64 bytes data type
        }

        #endregion

        #region Structures

        /// <summary>
        /// Handle to the data reader object
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct READER_HANDLE
        {
            public IntPtr Handle;
        }

        /// <summary>
        /// Represents metadata about a data file (deprecated)
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWFileInfo
        {
            public double sample_rate;         // Sampling rate
            public double start_store_time;    // Absolute time at the start of storing (days)
            public double duration;            // Duration of the whole datafile (seconds)
        }

        /// <summary>
        /// Structure with information about the current measurement
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWMeasurementInfo
        {
            public double sample_rate;         // Sampling rate
            public double start_measure_time;  // Absolute time at the start of measurement (days)
            public double start_store_time;    // Absolute time at the start of storing (days)
            public double duration;            // Duration of the whole datafile (seconds)
        }

        /// <summary>
        /// Structure represents a Dewesoft channel
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWChannel
        {
            public int index;                      // Unique identifier
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 100)]
            public byte[] name;                    // Name
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
            public byte[] unit;                    // Measurement unit
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 200)]
            public byte[] description;             // Description
            public uint color;                     // Display color
            public int array_size;                 // Array dimension size
            public DWDataType data_type;           // Data type

            public string Name
            {
                get { return Encoding.UTF8.GetString(name).TrimEnd('\0'); }
            }

            public string Unit
            {
                get { return Encoding.UTF8.GetString(unit).TrimEnd('\0'); }
            }

            public string Description
            {
                get { return Encoding.UTF8.GetString(description).TrimEnd('\0'); }
            }
        }

        /// <summary>
        /// Represents a complex number with real and imaginary components
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWComplex
        {
            public double re;                      // Real component
            public double im;                      // Imaginary component
        }

        /// <summary>
        /// Represents an event in datafile
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWEvent
        {
            public DWEventType event_type;         // Event type
            public double time_stamp;              // Timestamp in seconds
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 200)]
            public byte[] event_text;              // Event description

            public string EventText
            {
                get { return Encoding.UTF8.GetString(event_text).TrimEnd('\0'); }
            }
        }

        /// <summary>
        /// Represents a set of agregated data for samples over a specific time interval
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWReducedValue
        {
            public double time_stamp;              // Timestamp in seconds
            public double ave;                     // Average value
            public double min;                     // Minimum value
            public double max;                     // Maximum value
            public double rms;                     // RMS (Root mean square) value
        }

        /// <summary>
        /// Represents information about an axis on and array channel
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWArrayInfo
        {
            public int index;                     // Sequential axis identifier
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 100)]
            public byte[] name;                   // Name
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
            public byte[] unit;                   // Measurement unit
            public int size;                      // Size of axis dimension

            public string Name
            {
                get { return Encoding.UTF8.GetString(name).TrimEnd('\0'); }
            }

            public string Unit
            {
                get { return Encoding.UTF8.GetString(unit).TrimEnd('\0'); }
            }
        }

        /// <summary>
        /// Represents a custom property associated with a channel
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWCustomProp
        {
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 100)]
            public byte[] key;                     // Key
            public DWCustomPropValueType valueType; // Type of value
            public DWCustomPropValue value;        // Value

            public string Key
            {
                get { return Encoding.UTF8.GetString(key).TrimEnd('\0'); }
            }
        }

        /// <summary>
        /// Union representing different value types for custom properties
        /// </summary>
        [StructLayout(LayoutKind.Explicit, Pack = 1)]
        public struct DWCustomPropValue
        {
            [FieldOffset(0)]
            public long int64Val;                          // 64-bit integer value
            [FieldOffset(0)]
            public double doubleVal;                       // Double precision floating-point value
            [FieldOffset(0)]
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 100)]
            public byte[] strVal;                          // String value

            public string StringValue
            {
                get { return Encoding.UTF8.GetString(strVal).TrimEnd('\0'); }
            }
        }

        /// <summary>
        /// Represents a binary sample
        /// </summary>
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct DWBinarySample
        {
            public long position;
            public long size;
        }

        #endregion

        #region Status and Version Functions

        /// <summary>
        /// Retrieves the status and error message from last operation
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetLastStatus(out DWStatus status, StringBuilder statusMsg, ref int statusMsgSize);

        /// <summary>
        /// Gets the version number of the DWDataReader library
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetVersion();

        /// <summary>
        /// Gets the version number of the DWDataReader library in major, minor, and patch format
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetVersionEx(out int major, out int minor, out int patch);

        #endregion

        #region Reader Management Functions

        /// <summary>
        /// Initializes the DWDataReader library
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWInit();

        /// <summary>
        /// Deinitializes the DWDataReader library
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWDeInit();

        /// <summary>
        /// Creates a new reader within the shared reader pool
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWAddReader();

        /// <summary>
        /// Retrieves the number of readers in the shared reader pool
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetNumReaders(out int num_readers);

        /// <summary>
        /// Sets the active reader in the shared reader pool
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWSetActiveReader(int index);

        /// <summary>
        /// Creates a new reader instance handle
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWICreateReader(out IntPtr handle);

        /// <summary>
        /// Destroys the specified reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIDestroyReader(IntPtr handle);

        #endregion

        #region File Operations

        /// <summary>
        /// Opens the specified file and fills the file_info structure with information about the file contents
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWOpenDataFile([MarshalAs(UnmanagedType.LPStr)] string file_name, ref DWFileInfo file_info);

        /// <summary>
        /// Opens the specified file using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIOpenDataFile(IntPtr reader, [MarshalAs(UnmanagedType.LPStr)] string file_name, ref DWFileInfo file_info);

        /// <summary>
        /// Closes the currently open data file
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWCloseDataFile();

        /// <summary>
        /// Closes the currently open data file for a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWICloseDataFile(IntPtr reader);

        /// <summary>
        /// Retrieves the index of the currently open multifile
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetMultiFileIndex();

        /// <summary>
        /// Retrieves the index of the currently open multifile using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetMultiFileIndex(IntPtr reader, out int index);

        /// <summary>
        /// Retrieves detailed information about the current measurement
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetMeasurementInfo(ref DWMeasurementInfo measurement_info);

        /// <summary>
        /// Retrieves detailed information about the current measurement using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetMeasurementInfo(IntPtr reader, ref DWMeasurementInfo measurement_info);

        /// <summary>
        /// Exports the setup information to a specified file
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWExportHeader([MarshalAs(UnmanagedType.LPStr)] string file_name);

        /// <summary>
        /// Exports the setup information to a specified file using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIExportHeader(IntPtr reader, [MarshalAs(UnmanagedType.LPStr)] string file_name);

        /// <summary>
        /// Retrieves the current data storing type
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetStoringType();

        /// <summary>
        /// Retrieves the current data storing type using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetStoringType(IntPtr reader, out DWStoringType storingType);

        #endregion

        #region Channel List Functions

        /// <summary>
        /// Retrieves the number of available channels
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetChannelListCount();

        /// <summary>
        /// Retrieves the number of available channels using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetChannelListCount(IntPtr reader, out int count);

        /// <summary>
        /// Retrieves the list of available channels
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetChannelList([Out] DWChannel[] channel_list);

        /// <summary>
        /// Retrieves the list of available channels using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetChannelList(IntPtr reader, [Out] DWChannel[] channel_list);

        /// <summary>
        /// Retrieves information about a specific channel from the channel list
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetChannelListItem(int array_index, out int index, StringBuilder name, StringBuilder unit, StringBuilder description, out int color, out int array_size, int max_char_size);

        /// <summary>
        /// Retrieves information about a specific channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetChannelListItem(IntPtr reader, int array_index, out int index, StringBuilder name, StringBuilder unit, StringBuilder description, out int color, out int array_size, int max_char_size);

        /// <summary>
        /// Retrieves scaling factors for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetChannelFactors(int ch_index, out double scale, out double offset);

        /// <summary>
        /// Retrieves scaling factors for a specified channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetChannelFactors(IntPtr reader, int ch_index, out double scale, out double offset);

        /// <summary>
        /// Retrieves a specific property of a channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetChannelProps(int ch_index, DWChannelProps ch_prop, IntPtr buffer, ref int max_len);

        /// <summary>
        /// Retrieves a specific property of a channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetChannelProps(IntPtr reader, int ch_index, DWChannelProps ch_prop, IntPtr buffer, ref int max_len);

        #endregion

        #region Array Channel Functions

        /// <summary>
        /// Retrieves the count of array information entries for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetArrayInfoCount(int ch_index);

        /// <summary>
        /// Retrieves the count of array information entries using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetArrayInfoCount(IntPtr reader, int ch_index, out int count);

        /// <summary>
        /// Retrieves a list of array information entries for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetArrayInfoList(int ch_index, [Out] DWArrayInfo[] array_inf_list);

        /// <summary>
        /// Retrieves a list of array information entries using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetArrayInfoList(IntPtr reader, int ch_index, [Out] DWArrayInfo[] array_inf_list);

        /// <summary>
        /// Retrieves a specific value from an array's index for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetArrayIndexValue(int ch_index, int array_info_index, int array_value_index, StringBuilder value, int value_size);

        /// <summary>
        /// Retrieves a specific value from an array's index using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetArrayIndexValue(IntPtr reader, int ch_index, int array_info_index, int array_value_index, StringBuilder value, int value_size);

        /// <summary>
        /// Retrieves a numeric value from an array's index for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetArrayIndexValueF(int ch_index, int array_info_index, int array_value_index, out double value);

        /// <summary>
        /// Retrieves a numeric value from an array's index using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetArrayIndexValueF(IntPtr reader, int ch_index, int array_info_index, int array_value_index, out double value);

        #endregion

        #region Complex Channel Functions

        /// <summary>
        /// Retrieves the number of available complex channels
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetComplexChannelListCount();

        /// <summary>
        /// Retrieves the number of available complex channels using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetComplexChannelListCount(IntPtr reader, out int count);

        /// <summary>
        /// Retrieves the list of available complex channels
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetComplexChannelList([Out] DWChannel[] channel_list);

        /// <summary>
        /// Retrieves the list of available complex channels using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetComplexChannelList(IntPtr reader, [Out] DWChannel[] channel_list);

        /// <summary>
        /// Retrieves information about a specific complex channel from the channel list
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetComplexChannelListItem(int array_index, out int index, StringBuilder name, StringBuilder unit, StringBuilder description, out int color, out int array_size, int max_char_size);

        /// <summary>
        /// Retrieves information about a specific complex channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetComplexChannelListItem(IntPtr reader, int array_index, out int index, StringBuilder name, StringBuilder unit, StringBuilder description, out int color, out int array_size, int max_char_size);

        #endregion

        #region Data Sampling Functions

        /// <summary>
        /// Retrieves the count of scaled samples available for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern long DWGetScaledSamplesCount(int ch_index);

        /// <summary>
        /// Retrieves the count of scaled samples available for a specified channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetScaledSamplesCount(IntPtr reader, int ch_index, out long count);

        /// <summary>
        /// Retrieves a series of scaled samples and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetScaledSamples(int ch_index, long position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves a series of scaled samples and their timestamps for a specified channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetScaledSamples(IntPtr reader, int ch_index, long position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves the count of raw samples available for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern long DWGetRawSamplesCount(int ch_index);

        /// <summary>
        /// Retrieves the count of raw samples using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetRawSamplesCount(IntPtr reader, int ch_index, out long count);

        /// <summary>
        /// Retrieves a series of raw samples and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetRawSamples(int ch_index, long position, int count, IntPtr data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves a series of raw samples and timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetRawSamples(IntPtr reader, int ch_index, long position, int count, IntPtr data, [Out] double[] time_stamp);

        #endregion

        #region Complex Data Sampling Functions

        /// <summary>
        /// Retrieves the count of scaled samples available for a specified complex channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern long DWGetComplexScaledSamplesCount(int ch_index);

        /// <summary>
        /// Retrieves the count of scaled samples available for a specified complex channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetComplexScaledSamplesCount(IntPtr reader, int ch_index, out long count);

        /// <summary>
        /// Retrieves a series of complex scaled samples and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetComplexScaledSamples(int ch_index, long position, int count, [Out] DWComplex[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves a series of complex scaled samples and their timestamps for a specified channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetComplexScaledSamples(IntPtr reader, int ch_index, long position, int count, [Out] DWComplex[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves the count of complex raw samples available for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern long DWGetComplexRawSamplesCount(int ch_index);

        /// <summary>
        /// Retrieves the count of complex raw samples using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetComplexRawSamplesCount(IntPtr reader, int ch_index, out long count);

        /// <summary>
        /// Retrieves a series of complex raw samples and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetComplexRawSamples(int ch_index, long position, int count, [Out] DWComplex[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves complex raw samples and timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetComplexRawSamples(IntPtr reader, int ch_index, long position, int count, [Out] DWComplex[] data, [Out] double[] time_stamp);

        #endregion

        #region Binary Channel Functions

        /// <summary>
        /// Retrieves the number of available binary channels
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetBinChannelListCount();

        /// <summary>
        /// Retrieves the number of available binary channels using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetBinChannelListCount(IntPtr reader, out int count);

        /// <summary>
        /// Retrieves a list of available binary channels
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetBinChannelList([Out] DWChannel[] channel_list);

        /// <summary>
        /// Retrieves a list of available binary channels using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetBinChannelList(IntPtr reader, [Out] DWChannel[] channel_list);

        /// <summary>
        /// Retrieves the count of samples available for a specified binary channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern long DWGetBinarySamplesCount(int ch_index);

        /// <summary>
        /// Retrieves the count of samples available for a specified binary channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetBinarySamplesCount(IntPtr reader, int ch_index, out long count);

        /// <summary>
        /// Retrieves a single binary sample and its timestamp for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetBinarySamples(int ch_index, long sampleIndex, byte[] data, out double time_stamp, ref int datalen);

        /// <summary>
        /// Retrieves a single binary sample and its timestamp using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetBinarySamples(IntPtr reader, int ch_index, long sampleIndex, byte[] data, out double time_stamp, ref int datalen);

        /// <summary>
        /// Retrieves multiple binary samples and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetBinarySamplesEx(int ch_index, long position, int count, byte[] data, [Out] double[] time_stamp, ref int datalen);

        /// <summary>
        /// Retrieves multiple binary samples and their timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetBinarySamplesEx(IntPtr reader, int ch_index, long position, int count, byte[] data, [Out] double[] time_stamp, ref int datalen);

        /// <summary>
        /// Retrieves binary record samples and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetBinRecSamples(int ch_index, long sampleIndex, int count, byte[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves binary record samples and their timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetBinRecSamples(IntPtr reader, int ch_index, long sampleIndex, int count, [Out] DWBinarySample[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves binary data for a specified channel and sample
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetBinData(int ch_index, byte[] sample, byte[] data, ref long absPos, int binBufSize);

        /// <summary>
        /// Retrieves binary data for a specified channel and sample using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetBinData(IntPtr reader, int ch_index, ref DWBinarySample sample, byte[] data, ref long absPos, int binBufSize);

        #endregion

        #region Text Channel Functions

        /// <summary>
        /// Retrieves the number of text channels available
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetTextChannelListCount();

        /// <summary>
        /// Retrieves a list of text channels available
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetTextChannelList([Out] DWChannel[] channel_list);

        /// <summary>
        /// Retrieves the count of text values available for a specified text channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern long DWGetTextValuesCount(int ch_index);

        /// <summary>
        /// Retrieves a series of text values and their timestamps for a specified text channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetTextValues(int ch_index, int position, int count, StringBuilder text_values, [Out] double[] time_stamp);

        #endregion

        #region Reduced Data Functions

        /// <summary>
        /// Retrieves the count of reduced values and the block size for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedValuesCount(int ch_index, out int count, out double block_size);

        /// <summary>
        /// Retrieves the count of reduced values and the block size using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedValuesCount(IntPtr reader, int ch_index, out int count, out double block_size);

        /// <summary>
        /// Retrieves a series of reduced values for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedValues(int ch_index, int position, int count, [Out] DWReducedValue[] data);

        /// <summary>
        /// Retrieves a series of reduced values for a specified channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedValues(IntPtr reader, int ch_index, int position, int count, [Out] DWReducedValue[] data);

        /// <summary>
        /// Retrieves a block of reduced values for multiple channels
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedValuesBlock(int[] ch_ids, int ch_count, int position, int count, int ib_level, [Out] DWReducedValue[] data);

        /// <summary>
        /// Retrieves a block of reduced values for multiple channels using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedValuesBlock(IntPtr reader, int[] ch_ids, int ch_count, int position, int count, int ib_level, [Out] DWReducedValue[] data);

        /// <summary>
        /// Retrieves a series of average reduced values and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedAveValues(int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves average reduced values and timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedAveValues(IntPtr reader, int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves a series of minimum reduced values and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedMinValues(int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves minimum reduced values and timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedMinValues(IntPtr reader, int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves a series of maximum reduced values and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedMaxValues(int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves maximum reduced values and timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedMaxValues(IntPtr reader, int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves a series of RMS reduced values and their timestamps for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedRMSValues(int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        /// <summary>
        /// Retrieves RMS reduced values and timestamps using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedRMSValues(IntPtr reader, int ch_index, int position, int count, [Out] double[] data, [Out] double[] time_stamp);

        #endregion

        #region Stream Functions

        /// <summary>
        /// Retrieves a stream by name
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetStream([MarshalAs(UnmanagedType.LPStr)] string stream_name, byte[] buffer, ref int max_len);

        /// <summary>
        /// Retrieves a stream by name using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetStream(IntPtr reader, [MarshalAs(UnmanagedType.LPStr)] string stream_name, byte[] buffer, ref int max_len);

        #endregion

        #region Header Entry Functions

        /// <summary>
        /// Retrieves the count of entries in the current header
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetHeaderEntryCount();

        /// <summary>
        /// Retrieves the count of entries in the current header using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetHeaderEntryCount(IntPtr reader, out int count);

        /// <summary>
        /// Retrieves the list of entries in the current header
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetHeaderEntryList([Out] DWChannel[] entry_list);

        /// <summary>
        /// Retrieves the list of entries in the current header using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetHeaderEntryList(IntPtr reader, [Out] DWChannel[] entry_list);

        /// <summary>
        /// Retrieves the textual content of a specific header entry by index
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetHeaderEntryText(int ch_index, StringBuilder text_value, int text_value_size);

        /// <summary>
        /// Retrieves the textual content of a header entry using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetHeaderEntryText(IntPtr reader, int ch_index, StringBuilder text_value, int text_value_size);

        /// <summary>
        /// Retrieves information about a specific header entry from the header list
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetHeaderEntryListItem(int array_index, out int index, StringBuilder name, StringBuilder unit, StringBuilder description, out int color, out int array_size, int max_char_size);

        /// <summary>
        /// Retrieves information about a specific header entry using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetHeaderEntryListItem(IntPtr reader, int array_index, out int index, StringBuilder name, StringBuilder unit, StringBuilder description, out int color, out int array_size, int max_char_size);

        /// <summary>
        /// Retrieves the text value of a header entry by its entry number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetHeaderEntryTextF(int entry_number, StringBuilder text_value, int text_value_size);

        /// <summary>
        /// Retrieves the text value of a header entry using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetHeaderEntryTextF(IntPtr reader, int entry_number, StringBuilder text_value, int text_value_size);

        /// <summary>
        /// Retrieves the name of a header entry by its entry number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetHeaderEntryNameF(int entry_number, StringBuilder name, int name_size);

        /// <summary>
        /// Retrieves the name of a header entry using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetHeaderEntryNameF(IntPtr reader, int entry_number, StringBuilder name, int name_size);

        /// <summary>
        /// Retrieves the identifier (ID) of a header entry by its entry number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetHeaderEntryIDF(int entry_number, StringBuilder ID, int name_size);

        /// <summary>
        /// Retrieves the identifier (ID) of a header entry using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetHeaderEntryIDF(IntPtr reader, int entry_number, StringBuilder ID, int name_size);

        #endregion

        #region Event Functions

        /// <summary>
        /// Retrieves the count of events available in the current event list
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetEventListCount();

        /// <summary>
        /// Retrieves the count of events available in the current event list using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetEventListCount(IntPtr reader, out int count);

        /// <summary>
        /// Retrieves the list of events from the current event list
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetEventList([Out] DWEvent[] event_list);

        /// <summary>
        /// Retrieves the list of events from the current event list using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetEventList(IntPtr reader, [Out] DWEvent[] event_list);

        /// <summary>
        /// Retrieves information about a specific event from the event list
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetEventListItem(int event_Index, out int event_type, out double time_stamp, StringBuilder event_text, int max_char_size);

        /// <summary>
        /// Retrieves information about a specific event using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetEventListItem(IntPtr reader, int event_Index, out int event_type, out double time_stamp, StringBuilder event_text, int max_char_size);

        /// <summary>
        /// Retrieves the timestamp of a specific event by event number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern double DWGetEventTimeF(int event_number);

        /// <summary>
        /// Retrieves the timestamp of a specific event using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetEventTimeF(IntPtr reader, int event_number, out double time_stamp);

        /// <summary>
        /// Retrieves the text description of a specific event by event number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetEventTextF(int event_number, StringBuilder text, int text_size);

        /// <summary>
        /// Retrieves the text description of an event using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetEventTextF(IntPtr reader, int event_number, StringBuilder text, int text_size);

        /// <summary>
        /// Retrieves the type of a specific event by event number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetEventTypeF(int event_number);

        /// <summary>
        /// Retrieves the type of a specific event using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetEventTypeF(IntPtr reader, int event_number, out DWEventType eventType);

        #endregion

        #region Reduced Data Channel Functions

        /// <summary>
        /// Retrieves the number of channels available for reduced data
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetReducedDataChannelCountF();

        /// <summary>
        /// Retrieves the number of channels available for reduced data using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedDataChannelCountF(IntPtr reader, out int count);

        /// <summary>
        /// Retrieves the name of a reduced data channel by its number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetReducedDataChannelNameF(int Channel_Number, StringBuilder name, int name_size);

        /// <summary>
        /// Retrieves the name of a reduced data channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedDataChannelNameF(IntPtr reader, int Channel_Number, StringBuilder name, int name_size);

        /// <summary>
        /// Retrieves the index of a reduced data channel by its name
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetReducedDataChannelIndexF([MarshalAs(UnmanagedType.LPStr)] string name);

        /// <summary>
        /// Retrieves the index of a reduced data channel by its name using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetReducedDataChannelIndexF(IntPtr reader, [MarshalAs(UnmanagedType.LPStr)] string name, out int index);

        /// <summary>
        /// Retrieves detailed information about a reduced data channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetRecudedDataChannelInfoF(int Channel_Number, StringBuilder X_Axis_Units, int X_Axis_Units_size, StringBuilder Y_Axis_Units, int Y_Axis_Units_size, out double Chn_Offset, out int Channel_Length, out double ch_rate);

        /// <summary>
        /// Retrieves detailed information about a reduced data channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetRecudedDataChannelInfoF(IntPtr reader, int Channel_Number, StringBuilder X_Axis_Units, int X_Axis_Units_size, StringBuilder Y_Axis_Units, int Y_Axis_Units_size, out double Chn_Offset, out int Channel_Length, out double ch_rate);

        /// <summary>
        /// Retrieves X and Y axis data for a reduced data channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetRecudedDataF(int Channel_Number, [Out] double[] X_Axis, [Out] double[] Y_Axis, int position, int count);

        /// <summary>
        /// Retrieves X and Y axis data for a reduced data channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetRecudedDataF(IntPtr reader, int Channel_Number, [Out] double[] X_Axis, [Out] double[] Y_Axis, int position, int count);

        /// <summary>
        /// Retrieves Y-axis reduced data for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetRecudedYDataF(int Channel_Number, [Out] double[] Y_Axis, int position, int count);

        /// <summary>
        /// Retrieves Y-axis reduced data using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetRecudedYDataF(IntPtr reader, int Channel_Number, [Out] double[] Y_Axis, int position, int count);

        /// <summary>
        /// Retrieves all reduced data types (MIN, AVE, MAX, RMS) for a specified channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetRecudedDataAllF(int Channel_Number, [Out] double[] Y_MIN_Axis, [Out] double[] Y_AVE_Axis, [Out] double[] Y_MAX_Axis, [Out] double[] Y_RMS_Axis, int position, int count);

        /// <summary>
        /// Retrieves all reduced data types using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetRecudedDataAllF(IntPtr reader, int Channel_Number, [Out] double[] Y_MIN_Axis, [Out] double[] Y_AVE_Axis, [Out] double[] Y_MAX_Axis, [Out] double[] Y_RMS_Axis, int position, int count);

        #endregion

        #region Trigger Data Functions

        /// <summary>
        /// Retrieves the number of triggers in the trigger data
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetTriggerDataTriggerCountF();

        /// <summary>
        /// Retrieves the number of triggers using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetTriggerDataTriggerCountF(IntPtr reader, out int count);

        /// <summary>
        /// Retrieves the timestamp of a specific trigger by its number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern double DWGetTriggerDataTriggerTimeF(int Trigger_Number);

        /// <summary>
        /// Retrieves the timestamp of a specific trigger using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetTriggerDataTriggerTimeF(IntPtr reader, int Trigger_Number, out double time_stamp);

        /// <summary>
        /// Retrieves the name of a trigger data channel by its number
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetTriggerDataChannelNameF(int Channel_Number, StringBuilder name, int name_size);

        /// <summary>
        /// Retrieves the name of a trigger data channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetTriggerDataChannelNameF(IntPtr reader, int Channel_Number, StringBuilder name, int name_size);

        /// <summary>
        /// Retrieves the index of a trigger data channel by its name
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int DWGetTriggerDataChannelIndexF([MarshalAs(UnmanagedType.LPStr)] string name);

        /// <summary>
        /// Retrieves the index of a trigger data channel by its name using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetTriggerDataChannelIndexF(IntPtr reader, [MarshalAs(UnmanagedType.LPStr)] string name, out int index);

        /// <summary>
        /// Retrieves detailed information about a trigger data channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetTriggerDataChannelInfoF(int Trigger_Number, int Channel_Number, StringBuilder X_Axis_Units, int X_Axis_Units_size, StringBuilder Y_Axis_Units, int Y_Axis_Units_size, out double Chn_Offset, out double Channel_Length, out double ch_rate, out int ch_type);

        /// <summary>
        /// Retrieves detailed information about a trigger data channel using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetTriggerDataChannelInfoF(IntPtr reader, int Trigger_Number, int Channel_Number, StringBuilder X_Axis_Units, int X_Axis_Units_size, StringBuilder Y_Axis_Units, int Y_Axis_Units_size, out double Chn_Offset, out double Channel_Length, out double ch_rate, out int ch_type);

        /// <summary>
        /// Retrieves trigger data for a specific trigger and channel
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWGetTriggerDataF(int Trigger_Number, int Channel_Number, [Out] double[] Y_Axis, [Out] double[] X_Axis, double position, int count);

        /// <summary>
        /// Retrieves trigger data using a specific reader instance
        /// </summary>
        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        public static extern DWStatus DWIGetTriggerDataF(IntPtr reader, int Trigger_Number, int Channel_Number, [Out] double[] Y_Axis, [Out] double[] X_Axis, double position, int count);

        #endregion
    }
}
