#pragma once
#include "DWDataReaderLibDef.h"

#ifndef _WIN32
    #include <inttypes.h>
    #define __int64 int64_t
#endif

/**
 * @file DWDataReaderLibTypes.h
 *
 * Enums, structs and constants exposed from DWDataReader library.
 */

#pragma pack(push, 1)

typedef void* READER_HANDLE; /**< Handle to the data reader object */

 /**
  * @enum DWStatus
  * @brief Status codes returned from library function calls
  *
  * This enumeration defines the possible status codes that can be returned by
  * library functions, indicating success or various error conditions.
  */
enum DWStatus
{
    DWSTAT_OK = 0,                               /**< Operation completed successfully */
    DWSTAT_ERROR = 1,                            /**< Generic error occurred in the DLL */
    DWSTAT_ERROR_FILE_CANNOT_OPEN = 2,           /**< Unable to open the specified file */
    DWSTAT_ERROR_FILE_ALREADY_IN_USE = 3,        /**< File is already in use by another process */
    DWSTAT_ERROR_FILE_CORRUPT = 4,               /**< File is corrupted or has invalid format */
    DWSTAT_ERROR_NO_MEMORY_ALLOC = 5,            /**< Memory allocation failed */
    DWSTAT_ERROR_CREATE_DEST_FILE = 6,           /**< Failed to create destination file (d7z files only) */
    DWSTAT_ERROR_EXTRACTING_FILE = 7,            /**< Error occurred while extracting data (d7z files only) */
    DWSTAT_ERROR_CANNOT_OPEN_EXTRACTED_FILE = 8, /**< Unable to open extracted file (d7z files only) */
    DWSTAT_ERROR_INVALID_IB_LEVEL = 9,           /**< Invalid IB level specified */
    DWSTAT_ERROR_CAN_NOT_SUPPORTED = 10,         /**< Feature or operation not supported on CAN channel */
	DWSTAT_ERROR_INVALID_READER = 11,            /**< Invalid reader handle */
	DWSTAT_ERROR_INVALID_INDEX = 12,             /**< Invalid index specified */
	DWSTAT_ERROR_INSUFFICENT_BUFFER = 13,        /**< Insufficient buffer size provided */
};

/**
 * @enum DWChannelProps
 * @brief Specifies the properties that can be retrieved for a channel.
 *
 * This enumeration is used in function DWGetChannelProps to specify
 * which property of a channel should be retrieved. Each enumerator corresponds to a
 * different aspect of a channel property.
 */
enum DWChannelProps
{
    DW_DATA_TYPE = 0,               /**< Data type */
    DW_DATA_TYPE_LEN_BYTES = 1,     /**< Length of data type in bytes */
    DW_CH_INDEX = 2,                /**< Channel index */
    DW_CH_INDEX_LEN = 3,            /**< Length of channel index */
    DW_CH_TYPE = 4,                 /**< Type */
    DW_CH_SCALE = 5,                /**< Scale */
    DW_CH_OFFSET = 6,               /**< Offset */
    DW_CH_XML = 7,                  /**< XML structure of channel */
    DW_CH_XML_LEN = 8,              /**< Length of XML structure */
    DW_CH_XMLPROPS = 9,             /**< XML structure properties */
    DW_CH_XMLPROPS_LEN = 10,        /**< Length of XML structure properties */
    DW_CH_CUSTOMPROPS = 11,         /**< XML structure custom properties */
    DW_CH_CUSTOMPROPS_COUNT = 12,   /**< Length of XML structure custom properties */
	DW_CH_LONGNAME = 13,		    /**< Long name of channel */   
	DW_CH_LONGNAME_LEN = 14		    /**< Length of long name of channel */
};

/**
 * @enum DWChannelType
 * @brief Specifies the type of channel.
 */
enum DWChannelType
{
	DW_CH_TYPE_SYNC = 0,    /**< Synchronous channel */
	DW_CH_TYPE_ASYNC = 1,	/**< Asynchronous channel */
	DW_CH_TYPE_SV = 2		/**< Single value channel */
};

/**
 * @enum DWCustomPropValueType
 * @brief Specifies the type of custom property value.
 *
 * This enumeration defines the possible types of custom property values that can be
 * associated with a channel. Each enumerator corresponds to a different data type.
 */
enum DWCustomPropValueType
{
	DW_CUSTOM_PROP_VAL_TYPE_EMPTY = 0,  /**< No value */
	DW_CUSTOM_PROP_VAL_TYPE_INT64 = 1,  /**< 64-bit integer value */
	DW_CUSTOM_PROP_VAL_TYPE_DOUBLE = 2, /**< Double precision floating-point value */
	DW_CUSTOM_PROP_VAL_TYPE_STRING = 3, /**< String value */
};

/**
 * @enum DWEventType
 * @brief Specifies the type of event.
 */
enum DWEventType
{
    etStart = 1,       /**< Recording start */
    etStop = 2,        /**< Recording stop */
    etTrigger = 3,     /**< Trigger event */
    etVStart = 11,     /**< Video recording start */
    etVStop = 12,      /**< Video recording stop */
    etKeyboard = 20,   /**< Keyboard input */
    etNotice = 21,     /**< System notice */
    etVoice = 22,      /**< Voice annotation */
    etPicture = 23,    /**< Picture capture */
    etModule = 24,     /**< Module event */
    etAlarm = 25,      /**< Alarm notification */
    etCursorInfo = 26, /**< Cursor information */
    etAlarmLevel = 27  /**< Alarm level change */
};


/**
 * @enum DWStoringType
 * @brief Specifies the type data storing mode.
 */
enum DWStoringType {
    ST_ALWAYS_FAST = 0,                 /**< Always fast storing */
    ST_ALWAYS_SLOW = 1,                 /**< Always slow storing */
    ST_FAST_ON_TRIGGER = 2,             /**< Fast on trigger storing */
    ST_FAST_ON_TRIGGER_SLOW_OTH = 3,    /**< Fast on trigger slow otherwise storing */
};

/**
 * @enum DWDataType
 * @brief Specifies the channel data type.
 */
enum DWDataType
{
    dtByte = 0,             /**< Byte data type */
    dtShortInt = 1,         /**< Short integer data type */
    dtSmallInt = 2,         /**< Small integer data type */
    dtWord = 3,             /**< Word data type */
    dtInteger = 4,          /**< Integer data type */
    dtSingle = 5,           /**< Single precision floating point data type */
    dtInt64 = 6,            /**< 64-bit integer data type */
    dtDouble = 7,           /**< Double precision floating point data type */
    dtLongword = 8,         /**< Long word data type */
    dtComplexSingle = 9,    /**< Complex single precision data type */
    dtComplexDouble = 10,   /**< Complex double precision data type */
    dtText = 11,            /**< Text data type */
    dtBinary = 12,          /**< Binary data type */
    dtCANPortData = 13,     /**< CAN port data type */
    dtCANFDPortData = 14,   /**< CAN FD port data type */
    dtBytes8 = 15,          /**< 8 bytes data type */
    dtBytes16 = 16,         /**< 16 bytes data type */
    dtBytes32 = 17,         /**< 32 bytes data type */
    dtBytes64 = 18          /**< 64 bytes data type */
};

/**
 * @struct DWFileInfo
 * @brief Represents metadata about a data file.
 *
 * This structure provides information about a data file's sampling rate, when data
 * storage began, and the duration for which data is recorded.
 *
 * @deprecated This structure is deprecated and will be removed in a future release.
 * Please use `DWMeasurementInfo` instead.
 */
struct DWFileInfo
{
    double sample_rate;         /**< Sampling rate */
    double start_store_time;    /**< Absolute time at the start of storing (days) (in triggered storing this is the time of first trigger) */
    double duration;            /**< Duration of the whole datafile (seconds) */
};

/**
 * @struct DWMeasurementInfo
 * @brief Structure with information about the current measurement.
 */
struct DWMeasurementInfo
{
    double sample_rate;			/**< Sampling rate */
    double start_measure_time;	/**< Absolute time at the start of measurement (days) (in triggered storing this is the time of arming) */
    double start_store_time;	/**< Absolute time at the start of storing (days) (in triggered storing this is the time of first trigger) */
    double duration;			/**< Duration of the whole datafile (seconds) */
};

/**
 * @struct DWChannel
 * @brief Structure represents a Dewesoft channel.
 */
struct DWChannel
{
    int index;                      /**< Unique identifier */
    char name[100];                 /**< Name */
    char unit[20];                  /**< Measurement unit */
    char description[200];          /**< Description */
    unsigned int color;             /**< Display color */
    int array_size;                 /**< Array dimension size */
    enum DWDataType data_type;                  /**< Data type  */
};

/**
 * @struct DWComplex
 * @brief Represents a complex number with real and imaginary components.
 */
struct DWComplex
{
    double re;                      /**< Real component */
    double im;                      /**< Imaginary component */
};

/**
 * @struct DWEvent
 * @brief Represents an event in datafile.
 */
struct DWEvent
{
    enum DWEventType event_type;        /**< Event type */
    double time_stamp;             /**< Timestamp in seconds relative to `DWMeasurementInfo::start_measure_time` */
    char event_text[200];          /**< Event description */
};

/**
 * @struct DWReducedValue
 * @brief Represents a set of agregated data for samples over a specific time interval.
 */
struct DWReducedValue
{
    double time_stamp;              /**< Timestamp in seconds relative to `DWMeasurementInfo::start_measure_time` */
    double ave;                     /**< Average value */
    double min;                     /**< Minimum value */
    double max;                     /**< Maximum value */
    double rms;                     /**< RMS (Root mean square) value */
};

/**
 * @struct DWArrayInfo
 * @brief Represents information about an axis on and array channel.
 */
struct DWArrayInfo
{
    int index;                     /**< Sequential axis identifier */
    char name[100];                /**< Name */
    char unit[20];                 /**< Measurement unit */
    int size;                      /**< Size of axis dimension */
};

/**
 * @struct DWCustomProp
 * @brief Represents a custom property associated with a channel.
 *
 * This structure contains a key-value pair where the key is a string and the value
 * can be of different types (integer, double, or string).
 */ 
struct DWCustomProp
{
	char key[100];                                  /**< Key */
	enum DWCustomPropValueType valueType;           /**< Type of value */
    __int64 int64Val;                               /**< 64-bit integer value */
    double doubleVal;			                    /**< Double precision floating-point value */
    char strVal[100];                               /**< String value */			                       
};

/**
 * @struct DWBinarySample
 * @brief Represents a binary sample.
 *
 * This structure contains a position and size of a binary sample in the datafile.
 */
struct DWBinarySample
{
    __int64 position;
    __int64 size;
};

#pragma pack(pop)