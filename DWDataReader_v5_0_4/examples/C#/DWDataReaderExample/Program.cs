using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Linq;
using System.Net.Http.Headers;

namespace DWDataReader
{
    class Program
    {
        private const int MAX_SAMPLES_PER_CH = 10;
        private const bool SKIP_XML_DUMP = true;
        private const int STRING_BUFFER_SIZE = 255;

        static void Main(string[] args)
        {
            // Get version information
            int majorVersion, minorVersion, patchVersion;
            DWDataReaderLib.DWGetVersionEx(out majorVersion, out minorVersion, out patchVersion);
            Console.WriteLine($"Dewesoft Data Reader version: {majorVersion}.{minorVersion}.{patchVersion}");

            if (args.Length < 1)
            {
                Console.WriteLine("Usage: DWDataReaderExample.exe <datafile> [<datafile> ...]");
                return;
            }

            if (MAX_SAMPLES_PER_CH >= 0)
            {
                Console.WriteLine($"Max samples per channel limited to {MAX_SAMPLES_PER_CH}");
            }

            if (SKIP_XML_DUMP)
            {
                Console.WriteLine("XML dump will be skipped");
            }

            // Create reader instance
            IntPtr readerInstance;
            CheckError(DWDataReaderLib.DWICreateReader(out readerInstance));

            try
            {
                // Process each file from command line
                foreach (string filename in args)
                {
                    Console.WriteLine("============================================");
                    Console.WriteLine("Loading file: " + filename);
                    Console.WriteLine("============================================");

                    DWDataReaderLib.DWFileInfo fileInfo = new DWDataReaderLib.DWFileInfo();
                    CheckError(DWDataReaderLib.DWIOpenDataFile(readerInstance, filename, ref fileInfo));

                    Console.WriteLine("DWFile info: ");
                    Console.WriteLine($"  Sample rate:      {fileInfo.sample_rate}");
                    Console.WriteLine($"  Start store time: {fileInfo.start_store_time}");
                    Console.WriteLine($"  Duration:         {fileInfo.duration}");

                    GetFileMetadata(readerInstance);
                    GetFileEvents(readerInstance);
                    GetFileHeaderEntries(readerInstance);

                    GetFileChannels(readerInstance);
                    GetFileComplexChannels(readerInstance);
                    GetFileBinaryChannels(readerInstance);

                    CheckError(DWDataReaderLib.DWICloseDataFile(readerInstance));
                }
            }
            finally
            {
                // Cleanup
                CheckError(DWDataReaderLib.DWIDestroyReader(readerInstance));
            }
        }

        static void GetFileMetadata(IntPtr readerInstance)
        {
            Console.WriteLine("===");
            Console.WriteLine(" File metadata: ");
            Console.WriteLine("===");

            DWDataReaderLib.DWMeasurementInfo measurementInfo = new DWDataReaderLib.DWMeasurementInfo();
            CheckError(DWDataReaderLib.DWIGetMeasurementInfo(readerInstance, ref measurementInfo));
            Console.WriteLine("DWMeasurement info: ");
            Console.WriteLine($"  Sample rate:        {measurementInfo.sample_rate}");
            Console.WriteLine($"  Start measure time: {measurementInfo.start_measure_time}");
            Console.WriteLine($"  Start store time:   {measurementInfo.start_store_time}");
            Console.WriteLine($"  Duration:           {measurementInfo.duration}");

            DWDataReaderLib.DWStoringType storingType;
            CheckError(DWDataReaderLib.DWIGetStoringType(readerInstance, out storingType));
            Console.WriteLine($"Storing type: {storingType}");

            int chCount;

            CheckError(DWDataReaderLib.DWIGetHeaderEntryCount(readerInstance, out chCount));
            Console.WriteLine($"Header entry count: {chCount}");

            CheckError(DWDataReaderLib.DWIGetChannelListCount(readerInstance, out chCount));
            Console.WriteLine($"Channel count: {chCount}");

            CheckError(DWDataReaderLib.DWIGetComplexChannelListCount(readerInstance, out chCount));
            Console.WriteLine($"Complex channel count: {chCount}");

            CheckError(DWDataReaderLib.DWIGetBinChannelListCount(readerInstance, out chCount));
            Console.WriteLine($"Binary channel count: {chCount}");
        }

        static void GetFileEvents(IntPtr readerInstance)
        {
            Console.WriteLine("===");
            Console.WriteLine(" File events: ");
            Console.WriteLine("===");

            int eventCount;
            CheckError(DWDataReaderLib.DWIGetEventListCount(readerInstance, out eventCount));

            DWDataReaderLib.DWEvent[] eventList = new DWDataReaderLib.DWEvent[eventCount];
            CheckError(DWDataReaderLib.DWIGetEventList(readerInstance, eventList));

            for (int i = 0; i < eventCount; i++)
            {
                var evt = eventList[i];
                Console.WriteLine($"Event {i}:");
                Console.WriteLine($"  Type: {evt.event_type}");
                Console.WriteLine($"  Timestamp: {evt.time_stamp}");
                Console.WriteLine($"  Description: {evt.EventText}");
            }
        }

        static void GetFileHeaderEntries(IntPtr readerInstance)
        {
            Console.WriteLine("===");
            Console.WriteLine(" File header entries: ");
            Console.WriteLine("===");

            int entryCount;
            CheckError(DWDataReaderLib.DWIGetHeaderEntryCount(readerInstance, out entryCount));

            DWDataReaderLib.DWChannel[] headerEntries = new DWDataReaderLib.DWChannel[entryCount];
            CheckError(DWDataReaderLib.DWIGetHeaderEntryList(readerInstance, headerEntries));

            for (int i = 0; i < entryCount; i++)
            {
                var entry = headerEntries[i];

                StringBuilder entryText = new StringBuilder(STRING_BUFFER_SIZE);
                CheckError(DWDataReaderLib.DWIGetHeaderEntryText(readerInstance, entry.index, entryText, STRING_BUFFER_SIZE));

                Console.WriteLine($"Entry {i}:");
                Console.WriteLine($"  Name: {entry.Name}");
                Console.WriteLine($"  Unit: {entry.Unit}");
                Console.WriteLine($"  Value: {entryText}");
            }
        }

        static object GetChannelProperty(IntPtr readerInstance, DWDataReaderLib.DWChannel ch, DWDataReaderLib.DWChannelProps property)
        {
            int bufLen = 4;  // Default int size
            int bufLenDefault = 4;
            IntPtr bufLenPtr = Marshal.AllocHGlobal(bufLen);

            // Determine buffer size for different property types
            if (property == DWDataReaderLib.DWChannelProps.DW_CH_INDEX)
            {
                CheckError(DWDataReaderLib.DWIGetChannelProps(readerInstance, ch.index, DWDataReaderLib.DWChannelProps.DW_CH_INDEX_LEN, bufLenPtr, ref bufLenDefault));
                bufLen = Marshal.ReadInt32(bufLenPtr);
            }
            else if (property == DWDataReaderLib.DWChannelProps.DW_CH_LONGNAME)
            {
                CheckError(DWDataReaderLib.DWIGetChannelProps(readerInstance, ch.index, DWDataReaderLib.DWChannelProps.DW_CH_LONGNAME_LEN, bufLenPtr, ref bufLenDefault));
                bufLen = Marshal.ReadInt32(bufLenPtr);
            }
            else if (property == DWDataReaderLib.DWChannelProps.DW_CH_XML)
            {
                CheckError(DWDataReaderLib.DWIGetChannelProps(readerInstance, ch.index, DWDataReaderLib.DWChannelProps.DW_CH_XML_LEN, bufLenPtr, ref bufLenDefault));
                bufLen = Marshal.ReadInt32(bufLenPtr);
            }
            else if (property == DWDataReaderLib.DWChannelProps.DW_CH_XMLPROPS)
            {
                CheckError(DWDataReaderLib.DWIGetChannelProps(readerInstance, ch.index, DWDataReaderLib.DWChannelProps.DW_CH_XMLPROPS_LEN, bufLenPtr, ref bufLenDefault));
                bufLen = Marshal.ReadInt32(bufLenPtr);
                if (bufLen == 0)
                    return null;
            }
            else if (property == DWDataReaderLib.DWChannelProps.DW_CH_SCALE || property == DWDataReaderLib.DWChannelProps.DW_CH_OFFSET)
            {
                bufLen = 8;  // Double size
            }

            IntPtr buffer = Marshal.AllocHGlobal(bufLen);
            try
            {
                CheckError(DWDataReaderLib.DWIGetChannelProps(readerInstance, ch.index, property, buffer, ref bufLen));

                if (property == DWDataReaderLib.DWChannelProps.DW_DATA_TYPE)
                {
                    return (DWDataReaderLib.DWDataType)Marshal.ReadInt32(buffer);
                }
                if (property == DWDataReaderLib.DWChannelProps.DW_CH_INDEX ||
                    property == DWDataReaderLib.DWChannelProps.DW_CH_XML ||
                    property == DWDataReaderLib.DWChannelProps.DW_CH_XMLPROPS ||
                    property == DWDataReaderLib.DWChannelProps.DW_CH_LONGNAME)
                {
                    return Marshal.PtrToStringAnsi(buffer);
                }
                if (property == DWDataReaderLib.DWChannelProps.DW_CH_TYPE)
                {
                    return (DWDataReaderLib.DWChannelType)Marshal.ReadInt32(buffer);
                }
                if (property == DWDataReaderLib.DWChannelProps.DW_CH_SCALE || property == DWDataReaderLib.DWChannelProps.DW_CH_OFFSET)
                {
                    return Marshal.PtrToStructure<double>(buffer);
                }

                throw new ArgumentException($"Unsupported property: {property}");
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }

        static void PrintArrayInfo(IntPtr readerInstance, DWDataReaderLib.DWChannel ch, DWDataReaderLib.DWArrayInfo arrayInfo)
        {
            Console.WriteLine($"Array {arrayInfo.index}:");
            Console.WriteLine($"  Name: {arrayInfo.Name}");
            Console.WriteLine($"  Unit: {arrayInfo.Unit}");
            Console.WriteLine($"  Size: {arrayInfo.size}");

            for (int i = 0; i < arrayInfo.size; i++)
            {
                const int ARR_VALUE_MAX_LEN = 255;
                StringBuilder arrayValue = new StringBuilder(ARR_VALUE_MAX_LEN);
                CheckError(DWDataReaderLib.DWIGetArrayIndexValue(readerInstance, ch.index, arrayInfo.index, i, arrayValue, ARR_VALUE_MAX_LEN));
                Console.WriteLine($"  Value {i}: {arrayValue}");
            }
        }

        static void PrintChannelArrays(IntPtr readerInstance, DWDataReaderLib.DWChannel ch)
        {
            int arrayCount;
            CheckError(DWDataReaderLib.DWIGetArrayInfoCount(readerInstance, ch.index, out arrayCount));

            DWDataReaderLib.DWArrayInfo[] arrayList = new DWDataReaderLib.DWArrayInfo[arrayCount];
            CheckError(DWDataReaderLib.DWIGetArrayInfoList(readerInstance, ch.index, arrayList));

            for (int i = 0; i < arrayCount; i++)
            {
                PrintArrayInfo(readerInstance, ch, arrayList[i]);
            }
        }

        static void PrintChannelInfo(IntPtr readerInstance, DWDataReaderLib.DWChannel ch)
        {
            Console.WriteLine($"Channel {ch.index}:");
            Console.WriteLine($"  Name: {ch.Name}");
            Console.WriteLine($"  Unit: {ch.Unit}");
            Console.WriteLine($"  Description: {ch.Description}");
            Console.WriteLine($"  Color: {ch.color}");
            Console.WriteLine($"  Array size: {ch.array_size}");
            Console.WriteLine($"  Data type: {ch.data_type}");

            var dataType = (DWDataReaderLib.DWDataType)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_DATA_TYPE);
            Console.WriteLine($"  Data type (from property): {dataType}");

            var chIndex = (string)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_INDEX);
            Console.WriteLine($"  Channel index (from property): {chIndex}");

            var chType = (DWDataReaderLib.DWChannelType)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_TYPE);
            Console.WriteLine($"  Channel type (from property): {chType}");

            var chScale = (double)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_SCALE);
            Console.WriteLine($"  Scale (from property): {chScale}");

            var chOffset = (double)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_OFFSET);
            Console.WriteLine($"  Offset (from property): {chOffset}");

            if (!SKIP_XML_DUMP)
            {
                var chXml = (string)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_XML);
                Console.WriteLine($"  XML (from property): {chXml}");

                var chXmlProps = GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_XMLPROPS);
                if (chXmlProps != null)
                    Console.WriteLine($"  XML properties (from property): {chXmlProps}");
            }

            var chLongname = (string)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_LONGNAME);
            Console.WriteLine($"  Long name (from property): {chLongname}");

            PrintChannelArrays(readerInstance, ch);
        }

        static void PrintChannelValues(IntPtr readerInstance, DWDataReaderLib.DWChannel ch)
        {
            Console.WriteLine("===");
            Console.WriteLine(" Channel values: ");
            Console.WriteLine("===");

            long sampleCnt;
            CheckError(DWDataReaderLib.DWIGetScaledSamplesCount(readerInstance, ch.index, out sampleCnt));
            Console.WriteLine($"  Sample count: {sampleCnt}");

            long displaySampleCnt = sampleCnt;
            if (MAX_SAMPLES_PER_CH >= 0 && displaySampleCnt > MAX_SAMPLES_PER_CH)
                displaySampleCnt = MAX_SAMPLES_PER_CH;

            int displayArraySize = ch.array_size;
            if (MAX_SAMPLES_PER_CH >= 0 && displayArraySize > MAX_SAMPLES_PER_CH)
                displayArraySize = MAX_SAMPLES_PER_CH;

            long totalCount = sampleCnt * ch.array_size;
            double[] samples = new double[totalCount];

            var chType = (DWDataReaderLib.DWChannelType)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_TYPE);

            double[] timestamps = null;
            if (chType == DWDataReaderLib.DWChannelType.DW_CH_TYPE_ASYNC)
            {
                timestamps = new double[sampleCnt];
            }

            CheckError(DWDataReaderLib.DWIGetScaledSamples(readerInstance, ch.index, 0, (int)sampleCnt, samples, timestamps));

            for (long i = 0; i < displaySampleCnt; i++)
            {
                if (ch.array_size == 1)
                {
                    if (chType == DWDataReaderLib.DWChannelType.DW_CH_TYPE_ASYNC)
                    {
                        Console.WriteLine($"  Timestamp: {timestamps[i]:F2}  Value: {samples[i]:F2}");
                    }
                    else
                    {
                        Console.WriteLine($"  Value: {samples[i]:F2}");
                    }
                }
                else
                {
                    if (chType == DWDataReaderLib.DWChannelType.DW_CH_TYPE_ASYNC)
                    {
                        Console.WriteLine($"  Timestamp: {timestamps[i]:F2}");
                    }
                    for (int j = 0; j < displayArraySize; j++)
                    {
                        Console.WriteLine($"  Value[{j}]: {samples[i * ch.array_size + j]:F2}");
                    }
                    if (displayArraySize < ch.array_size)
                    {
                        Console.WriteLine("  ...");
                    }
                }
            }
            if (displaySampleCnt < sampleCnt)
            {
                Console.WriteLine("  ...");
            }
        }

        static void PrintComplexChannelValues(IntPtr readerInstance, DWDataReaderLib.DWChannel ch)
        {
            Console.WriteLine("===");
            Console.WriteLine(" Complex channel values: ");
            Console.WriteLine("===");

            long sampleCnt;
            CheckError(DWDataReaderLib.DWIGetComplexScaledSamplesCount(readerInstance, ch.index, out sampleCnt));
            Console.WriteLine($"  Sample count: {sampleCnt}");

            long displaySampleCnt = sampleCnt;
            if (MAX_SAMPLES_PER_CH >= 0 && displaySampleCnt > MAX_SAMPLES_PER_CH)
                displaySampleCnt = MAX_SAMPLES_PER_CH;

            int displayArraySize = ch.array_size;
            if (MAX_SAMPLES_PER_CH >= 0 && displayArraySize > MAX_SAMPLES_PER_CH)
                displayArraySize = MAX_SAMPLES_PER_CH;

            long totalCount = sampleCnt * ch.array_size;
            DWDataReaderLib.DWComplex[] samples = new DWDataReaderLib.DWComplex[totalCount];

            var chType = (DWDataReaderLib.DWChannelType)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_TYPE);

            double[] timestamps = null;
            if (chType == DWDataReaderLib.DWChannelType.DW_CH_TYPE_ASYNC)
            {
                timestamps = new double[sampleCnt];
            }

            CheckError(DWDataReaderLib.DWIGetComplexScaledSamples(readerInstance, ch.index, 0, (int)sampleCnt, samples, timestamps));

            for (long i = 0; i < displaySampleCnt; i++)
            {
                if (ch.array_size == 1)
                {
                    if (chType == DWDataReaderLib.DWChannelType.DW_CH_TYPE_ASYNC)
                    {
                        Console.WriteLine($"  Timestamp: {timestamps[i]:F2}  Value: ({samples[i].re:F2}  {samples[i].im:F2})");
                    }
                    else
                    {
                        Console.WriteLine($"  Value: ({samples[i].re:F2}  {samples[i].im:F2})");
                    }
                }
                else
                {
                    if (chType == DWDataReaderLib.DWChannelType.DW_CH_TYPE_ASYNC)
                    {
                        Console.WriteLine($"  Timestamp: {timestamps[i]:F2}");
                    }
                    for (int j = 0; j < displayArraySize; j++)
                    {
                        Console.WriteLine($"  Value[{j}]: ({samples[i * ch.array_size + j].re:F2}  {samples[i * ch.array_size + j].im:F2})");
                    }
                    if (displayArraySize < ch.array_size)
                    {
                        Console.WriteLine("  ...");
                    }
                }
            }
            if (displaySampleCnt < sampleCnt)
            {
                Console.WriteLine("  ...");
            }
        }

        static void PrintBinaryChannelValues(IntPtr readerInstance, DWDataReaderLib.DWChannel ch)
        {
            Console.WriteLine("===");
            Console.WriteLine(" Binary channel values: ");
            Console.WriteLine("===");

            long sampleCnt;
            CheckError(DWDataReaderLib.DWIGetScaledSamplesCount(readerInstance, ch.index, out sampleCnt));
            Console.WriteLine($"  Sample count: {sampleCnt}");

            long displaySampleCnt = sampleCnt;
            if (MAX_SAMPLES_PER_CH >= 0 && displaySampleCnt > MAX_SAMPLES_PER_CH)
                displaySampleCnt = MAX_SAMPLES_PER_CH;

            var chType = (DWDataReaderLib.DWChannelType)GetChannelProperty(readerInstance, ch, DWDataReaderLib.DWChannelProps.DW_CH_TYPE);
            // Binary channels should be async and have array size of 1
            if (chType != DWDataReaderLib.DWChannelType.DW_CH_TYPE_ASYNC || ch.array_size != 1)
            {
                Console.WriteLine("  Unexpected binary channel configuration");
                return;
            }

            DWDataReaderLib.DWBinarySample[] samples = new DWDataReaderLib.DWBinarySample[sampleCnt];
            double[] timestamps = new double[sampleCnt];

            CheckError(DWDataReaderLib.DWIGetBinRecSamples(readerInstance, ch.index, 0, (int)sampleCnt, samples, timestamps));

            const int BIN_BUF_SIZE = 1024;
            for (long i = 0; i < displaySampleCnt; i++)
            {
                byte[] binBuf = new byte[BIN_BUF_SIZE];
                long binBufPos = 0;

                CheckError(DWDataReaderLib.DWIGetBinData(readerInstance, ch.index, ref samples[i], binBuf, ref binBufPos, BIN_BUF_SIZE));
                string binData = System.Text.Encoding.UTF8.GetString(binBuf, 0, (int)binBufPos).TrimEnd('\0');

                Console.WriteLine($"  Timestamp: {timestamps[i]:F2}  Value: {binData}");
            }
            if (displaySampleCnt < sampleCnt)
            {
                Console.WriteLine("  ...");
            }
        }

        static void PrintReducedChannelValues(IntPtr readerInstance, DWDataReaderLib.DWChannel ch)
        {
            Console.WriteLine("===");
            Console.WriteLine(" Reduced channel values: ");
            Console.WriteLine("===");

            int sampleCnt;
            double blockSize;
            CheckError(DWDataReaderLib.DWIGetReducedValuesCount(readerInstance, ch.index, out sampleCnt, out blockSize));

            Console.WriteLine($"  Reduced block count: {sampleCnt}");
            Console.WriteLine($"  Reduced block size: {blockSize}");

            int displaySampleCnt = sampleCnt;
            if (MAX_SAMPLES_PER_CH >= 0 && displaySampleCnt > MAX_SAMPLES_PER_CH)
                displaySampleCnt = MAX_SAMPLES_PER_CH;

            DWDataReaderLib.DWReducedValue[] blocks = new DWDataReaderLib.DWReducedValue[sampleCnt];
            CheckError(DWDataReaderLib.DWIGetReducedValues(readerInstance, ch.index, 0, sampleCnt, blocks));

            for (int i = 0; i < displaySampleCnt; i++)
            {
                var block = blocks[i];
                Console.WriteLine($"  Timestamp: {block.time_stamp:F2}  Ave: {block.ave:F2}  Min: {block.min:F2}  Max: {block.max:F2}  Rms: {block.rms:F2}");
            }
            if (displaySampleCnt < sampleCnt)
            {
                Console.WriteLine("  ...");
            }
        }

        static void GetFileChannels(IntPtr readerInstance)
        {
            Console.WriteLine("===");
            Console.WriteLine(" Channels: ");
            Console.WriteLine("===");

            int channelCount;
            CheckError(DWDataReaderLib.DWIGetChannelListCount(readerInstance, out channelCount));

            DWDataReaderLib.DWChannel[] channelList = new DWDataReaderLib.DWChannel[channelCount];
            CheckError(DWDataReaderLib.DWIGetChannelList(readerInstance, channelList));

            for (int i = 0; i < channelCount; i++)
            {
                PrintChannelInfo(readerInstance, channelList[i]);
                PrintChannelValues(readerInstance, channelList[i]);
                PrintReducedChannelValues(readerInstance, channelList[i]);
            }
        }

        static void GetFileComplexChannels(IntPtr readerInstance)
        {
            Console.WriteLine("===");
            Console.WriteLine(" Complex channels: ");
            Console.WriteLine("===");

            int channelCount;
            CheckError(DWDataReaderLib.DWIGetComplexChannelListCount(readerInstance, out channelCount));

            DWDataReaderLib.DWChannel[] channelList = new DWDataReaderLib.DWChannel[channelCount];
            CheckError(DWDataReaderLib.DWIGetComplexChannelList(readerInstance, channelList));

            for (int i = 0; i < channelCount; i++)
            {
                PrintChannelInfo(readerInstance, channelList[i]);
                PrintComplexChannelValues(readerInstance, channelList[i]);
                PrintReducedChannelValues(readerInstance, channelList[i]);
            }
        }

        static void GetFileBinaryChannels(IntPtr readerInstance)
        {
            Console.WriteLine("===");
            Console.WriteLine(" Binary channels: ");
            Console.WriteLine("===");

            int channelCount;
            CheckError(DWDataReaderLib.DWIGetBinChannelListCount(readerInstance, out channelCount));

            DWDataReaderLib.DWChannel[] channelList = new DWDataReaderLib.DWChannel[channelCount];
            CheckError(DWDataReaderLib.DWIGetBinChannelList(readerInstance, channelList));

            for (int i = 0; i < channelCount; i++)
            {
                PrintChannelInfo(readerInstance, channelList[i]);
                PrintBinaryChannelValues(readerInstance, channelList[i]);
            }
        }

        static void CheckError(DWDataReaderLib.DWStatus status)
        {
            if (status != DWDataReaderLib.DWStatus.DWSTAT_OK)
            {
                DWDataReaderLib.DWStatus statusCode;
                StringBuilder errorMsg = new StringBuilder(STRING_BUFFER_SIZE);
                int msgSize = STRING_BUFFER_SIZE;
                DWDataReaderLib.DWGetLastStatus(out statusCode, errorMsg, ref msgSize);

                throw new Exception($"DWDataReader Error {status}: {errorMsg}");
            }
        }
    }
}
