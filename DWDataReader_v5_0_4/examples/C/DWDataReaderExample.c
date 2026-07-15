#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "DWLoadLib.h"

#define MAX_SAMPLES_PER_CH 10
#define SKIP_XML_DUMP 1
#define TEXT_BUFFER_SIZE 255

// Function to check and print errors
void check_error(enum DWStatus status) {
    if (status == DWSTAT_ERROR_CAN_NOT_SUPPORTED) {
        printf("Warning: CAN decoder functionality is limited. Value may be decoded incorrectly.");
        return;
    }

    if (status != DWSTAT_OK) {
        enum DWStatus errorStatus;
        char errorMsg[1024];
        int errorMsgSize = sizeof(errorMsg);

        DWGetLastStatus(&errorStatus, errorMsg, &errorMsgSize);
        printf("Error: %s (Code: %d)\n", errorMsg, errorStatus);
        exit(1);
    }
}

// Helper function to print file metadata
void get_file_metadata(READER_HANDLE reader_instance) {
    printf("===\n");
    printf(" File metadata: \n");
    printf("===\n");

    struct DWMeasurementInfo measurement_info = { 0 };
    check_error(DWIGetMeasurementInfo(reader_instance, &measurement_info));

    printf("DWMeasurement info: \n");
    printf("  Sample rate:        %f\n", measurement_info.sample_rate);
    printf("  Start measure time: %f\n", measurement_info.start_measure_time);
    printf("  Start store time:   %f\n", measurement_info.start_store_time);
    printf("  Duration:           %f\n", measurement_info.duration);

    int storing_type_c;
    check_error(DWIGetStoringType(reader_instance, &storing_type_c));

    const char* storing_type_str;
    switch (storing_type_c) {
    case ST_ALWAYS_FAST:
        storing_type_str = "ST_ALWAYS_FAST";
        break;
    case ST_ALWAYS_SLOW:
        storing_type_str = "ST_ALWAYS_SLOW";
        break;
    case ST_FAST_ON_TRIGGER:
        storing_type_str = "ST_FAST_ON_TRIGGER";
        break;
    case ST_FAST_ON_TRIGGER_SLOW_OTH:
        storing_type_str = "ST_FAST_ON_TRIGGER_SLOW_OTH";
        break;
    default:
        storing_type_str = "UNKNOWN";
    }
    printf("Storing type: %s\n", storing_type_str);

    int count;

    check_error(DWIGetHeaderEntryCount(reader_instance, &count));
    printf("Header entry count: %d\n", count);

    check_error(DWIGetChannelListCount(reader_instance, &count));
    printf("Channel count: %d\n", count);

    check_error(DWIGetComplexChannelListCount(reader_instance, &count));
    printf("Complex channel count: %d\n", count);

    check_error(DWIGetBinChannelListCount(reader_instance, &count));
    printf("Binary channel count: %d\n", count);
}

// Helper function to print file events
void get_file_events(READER_HANDLE reader_instance) {
    printf("===\n");
    printf(" File events: \n");
    printf("===\n");

    int event_count;
    check_error(DWIGetEventListCount(reader_instance, &event_count));

    struct DWEvent* event_list = (struct DWEvent*)malloc(event_count * sizeof(struct DWEvent));
    check_error(DWIGetEventList(reader_instance, event_list));

    for (int i = 0; i < event_count; i++) {
        struct DWEvent event = event_list[i];

        printf("Event %d:\n", i);
        printf("  Type: %d\n", event.event_type);
        printf("  Timestamp: %f\n", event.time_stamp);
        printf("  Description: %s\n", event.event_text);
    }

    free(event_list);
}

// Helper function to print file header entries
void get_file_header_entries(READER_HANDLE reader_instance) {
    printf("===\n");
    printf(" File header entries: \n");
    printf("===\n");

    int entry_count;
    check_error(DWIGetHeaderEntryCount(reader_instance, &entry_count));

    struct DWChannel* header_entries = (struct DWChannel*)malloc(entry_count * sizeof(struct DWChannel));
    check_error(DWIGetHeaderEntryList(reader_instance, header_entries));

    for (int i = 0; i < entry_count; i++) {
        struct DWChannel entry = header_entries[i];

        char entry_text[TEXT_BUFFER_SIZE] = { 0 };
        check_error(DWIGetHeaderEntryText(reader_instance, entry.index, entry_text, TEXT_BUFFER_SIZE));

        printf("Entry %d:\n", i);
        printf("  Name: %s\n", entry.name);
        printf("  Unit: %s\n", entry.unit);
        printf("  Value: %s\n", entry_text);
    }

    free(header_entries);
}

// Get a channel property as a channel type
enum DWChannelType get_channel_type_property(READER_HANDLE reader_instance, struct DWChannel ch) {
    int buf_len = sizeof(int);
    int ch_type_val;
    void* p_buff = &ch_type_val;

    check_error(DWIGetChannelProps(reader_instance, ch.index, DW_CH_TYPE, p_buff, &buf_len));
    return (enum DWChannelType)ch_type_val;
}

// Get a channel property as a double
double get_channel_double_property(READER_HANDLE reader_instance, struct DWChannel ch, enum DWChannelProps property) {
    int buf_len = sizeof(double);
    double value;
    void* p_buff = &value;

    check_error(DWIGetChannelProps(reader_instance, ch.index, property, p_buff, &buf_len));
    return value;
}

// Get a channel property as a string
char* get_channel_string_property(READER_HANDLE reader_instance, struct DWChannel ch, enum DWChannelProps property, enum DWChannelProps len_property) {
    int buf_len = 0;
    int buf_len_default = sizeof(int);

    check_error(DWIGetChannelProps(reader_instance, ch.index, len_property, &buf_len, &buf_len_default));
    if (buf_len == 0) {
        return NULL;
    }

    char* value = (char*)malloc(buf_len);
    void* p_buff = value;

    check_error(DWIGetChannelProps(reader_instance, ch.index, property, p_buff, &buf_len));
    return value;
}

// Helper function to print array info
void print_array_info(READER_HANDLE reader_instance, struct DWChannel ch, struct DWArrayInfo array_info) {
    printf("Array %d:\n", array_info.index);
    printf("  Name: %s\n", array_info.name);
    printf("  Unit: %s\n", array_info.unit);
    printf("  Size: %d\n", array_info.size);

    for (int i = 0; i < array_info.size; i++) {
        char array_value[TEXT_BUFFER_SIZE] = { 0 };
        check_error(DWIGetArrayIndexValue(reader_instance, ch.index, array_info.index, i, array_value, TEXT_BUFFER_SIZE));
        printf("  Value %d: %s\n", i, array_value);
    }
}

// Helper function to print channel arrays
void print_channel_arrays(READER_HANDLE reader_instance, struct DWChannel ch) {
    int array_count;
    check_error(DWIGetArrayInfoCount(reader_instance, ch.index, &array_count));

    struct DWArrayInfo* array_list = (struct DWArrayInfo*)malloc(array_count * sizeof(struct DWArrayInfo));
    check_error(DWIGetArrayInfoList(reader_instance, ch.index, array_list));

    for (int i = 0; i < array_count; i++) {
        struct DWArrayInfo array_info = array_list[i];
        print_array_info(reader_instance, ch, array_info);
    }

    free(array_list);
}

// Helper function to print channel info
void print_channel_info(READER_HANDLE reader_instance, struct DWChannel ch) {
    printf("Channel %d:\n", ch.index);
    printf("  Name: %s\n", ch.name);
    printf("  Unit: %s\n", ch.unit);
    printf("  Description: %s\n", ch.description);
    printf("  Color: %u\n", ch.color);
    printf("  Array size: %d\n", ch.array_size);

    printf("  Data type: %d\n", ch.data_type);

    int data_type_val;
    int buf_len = sizeof(int);
    void* p_buff = &data_type_val;
    check_error(DWIGetChannelProps(reader_instance, ch.index, DW_DATA_TYPE, p_buff, &buf_len));
    printf("  Data type (from property): %d\n", data_type_val);

    char* ch_index = get_channel_string_property(reader_instance, ch, DW_CH_INDEX, DW_CH_INDEX_LEN);
    printf("  Channel index (from property): %s\n", ch_index ? ch_index : "NULL");
    if (ch_index) free(ch_index);

    enum DWChannelType ch_type = get_channel_type_property(reader_instance, ch);
    printf("  Channel type (from property): %d\n", ch_type);

    double ch_scale = get_channel_double_property(reader_instance, ch, DW_CH_SCALE);
    printf("  Scale (from property): %f\n", ch_scale);

    double ch_offset = get_channel_double_property(reader_instance, ch, DW_CH_OFFSET);
    printf("  Offset (from property): %f\n", ch_offset);

    if (!SKIP_XML_DUMP) {
        char* ch_xml = get_channel_string_property(reader_instance, ch, DW_CH_XML, DW_CH_XML_LEN);
        printf("  XML (from property): %s\n", ch_xml ? ch_xml : "NULL");
        if (ch_xml) free(ch_xml);

        char* ch_xmlprops = get_channel_string_property(reader_instance, ch, DW_CH_XMLPROPS, DW_CH_XMLPROPS_LEN);
        printf("  XML properties (from property): %s\n", ch_xmlprops ? ch_xmlprops : "NULL");
        if (ch_xmlprops) free(ch_xmlprops);
    }

    char* ch_longname = get_channel_string_property(reader_instance, ch, DW_CH_LONGNAME, DW_CH_LONGNAME_LEN);
    printf("  Long name (from property): %s\n", ch_longname ? ch_longname : "NULL");
    if (ch_longname) free(ch_longname);

    print_channel_arrays(reader_instance, ch);
}

// Helper function to print channel values
void print_channel_values(READER_HANDLE reader_instance, struct DWChannel ch) {
    printf("===\n");
    printf(" Channel values: \n");
    printf("===\n");

    __int64 sample_cnt;
    check_error(DWIGetScaledSamplesCount(reader_instance, ch.index, &sample_cnt));
    printf("  Sample count: %lld\n", sample_cnt);

    __int64 display_sample_cnt = sample_cnt;
    if (MAX_SAMPLES_PER_CH >= 0 && display_sample_cnt > MAX_SAMPLES_PER_CH) {
        display_sample_cnt = MAX_SAMPLES_PER_CH;
    }

    int display_array_size = ch.array_size;
    if (MAX_SAMPLES_PER_CH >= 0 && display_array_size > MAX_SAMPLES_PER_CH) {
        display_array_size = MAX_SAMPLES_PER_CH;
    }

    __int64 total_count = sample_cnt * ch.array_size;
    double* samples = (double*)malloc(total_count * sizeof(double));

    enum DWChannelType ch_type = get_channel_type_property(reader_instance, ch);

    double* timestamps = NULL;
    if (ch_type == DW_CH_TYPE_ASYNC) {
        timestamps = (double*)malloc(sample_cnt * sizeof(double));
    }

    enum DWStatus cmd_status = DWIGetScaledSamples(reader_instance, ch.index, 0, sample_cnt, samples, timestamps);
    check_error(cmd_status);

    for (__int64 i = 0; i < sample_cnt; i++) {
        if (i >= display_sample_cnt) {
            printf("  ...\n");
            break;
        }

        if (ch.array_size == 1) {
            if (ch_type == DW_CH_TYPE_ASYNC) {
                printf("  Timestamp: %.2f  Value: %.2f\n", timestamps[i], samples[i]);
            }
            else {
                printf("  Value: %.2f\n", samples[i]);
            }
        }
        else {
            if (ch_type == DW_CH_TYPE_ASYNC) {
                printf("  Timestamp: %.2f\n", timestamps[i]);
            }

            for (int j = 0; j < ch.array_size; j++) {
                if (j >= display_array_size) {
                    printf("  ...\n");
                    break;
                }
                printf("  Value[%d]: %.2f\n", j, samples[i * ch.array_size + j]);
            }
        }
    }

    free(samples);
    if (timestamps) free(timestamps);
}

// Helper function to print complex channel values
void print_complex_channel_values(READER_HANDLE reader_instance, struct DWChannel ch) {
    printf("===\n");
    printf(" Complex channel values: \n");
    printf("===\n");

    __int64 sample_cnt;
    check_error(DWIGetComplexScaledSamplesCount(reader_instance, ch.index, &sample_cnt));
    printf("  Sample count: %lld\n", sample_cnt);

    __int64 display_sample_cnt = sample_cnt;
    if (MAX_SAMPLES_PER_CH >= 0 && display_sample_cnt > MAX_SAMPLES_PER_CH) {
        display_sample_cnt = MAX_SAMPLES_PER_CH;
    }

    int display_array_size = ch.array_size;
    if (MAX_SAMPLES_PER_CH >= 0 && display_array_size > MAX_SAMPLES_PER_CH) {
        display_array_size = MAX_SAMPLES_PER_CH;
    }

    __int64 total_count = sample_cnt * ch.array_size;
    struct DWComplex* samples = (struct DWComplex*)malloc(total_count * sizeof(struct DWComplex));

    enum DWChannelType ch_type = get_channel_type_property(reader_instance, ch);

    double* timestamps = NULL;
    if (ch_type == DW_CH_TYPE_ASYNC) {
        timestamps = (double*)malloc(sample_cnt * sizeof(double));
    }

    check_error(DWIGetComplexScaledSamples(reader_instance, ch.index, 0, sample_cnt, samples, timestamps));

    for (__int64 i = 0; i < sample_cnt; i++) {
        if (i >= display_sample_cnt) {
            printf("  ...\n");
            break;
        }

        if (ch.array_size == 1) {
            if (ch_type == DW_CH_TYPE_ASYNC) {
                printf("  Timestamp: %.2f  Value: (%.2f  %.2f)\n",
                    timestamps[i], samples[i].re, samples[i].im);
            }
            else {
                printf("  Value: (%.2f  %.2f)\n", samples[i].re, samples[i].im);
            }
        }
        else {
            if (ch_type == DW_CH_TYPE_ASYNC) {
                printf("  Timestamp: %.2f\n", timestamps[i]);
            }

            for (int j = 0; j < ch.array_size; j++) {
                if (j >= display_array_size) {
                    printf("  ...\n");
                    break;
                }
                printf("  Value[%d]: (%.2f  %.2f)\n",
                    j, samples[i * ch.array_size + j].re, samples[i * ch.array_size + j].im);
            }
        }
    }

    free(samples);
    if (timestamps) free(timestamps);
}

// Helper function to print binary channel values
void print_binary_channel_values(READER_HANDLE reader_instance, struct DWChannel ch) {
    printf("===\n");
    printf(" Binary channel values: \n");
    printf("===\n");

    __int64 sample_cnt;
    check_error(DWIGetScaledSamplesCount(reader_instance, ch.index, &sample_cnt));
    printf("  Sample count: %lld\n", sample_cnt);

    __int64 display_sample_cnt = sample_cnt;
    if (MAX_SAMPLES_PER_CH >= 0 && display_sample_cnt > MAX_SAMPLES_PER_CH) {
        display_sample_cnt = MAX_SAMPLES_PER_CH;
    }

    enum DWChannelType ch_type = get_channel_type_property(reader_instance, ch);
    if (ch_type != DW_CH_TYPE_ASYNC || ch.array_size != 1) {
        printf("  Binary channel must be async with array size 1\n");
        return;
    }

    struct DWBinarySample* samples = (struct DWBinarySample*)malloc(sample_cnt * sizeof(struct DWBinarySample));
    double* timestamps = (double*)malloc(sample_cnt * sizeof(double));

    check_error(DWIGetBinRecSamples(reader_instance, ch.index, 0, sample_cnt, samples, timestamps));

    for (__int64 i = 0; i < sample_cnt; i++) {
        if (i >= display_sample_cnt) {
            printf("  ...\n");
            break;
        }

#define BIN_BUF_SIZE 1024
        struct DWBinarySample bin_rec = samples[i];
        char bin_buf[BIN_BUF_SIZE] = { 0 };
        __int64 bin_buf_pos = 0;

        check_error(DWIGetBinData(reader_instance, ch.index, &bin_rec, bin_buf, &bin_buf_pos, BIN_BUF_SIZE));
        printf("  Timestamp: %.2f  Value: %s\n", timestamps[i], bin_buf);
    }

    free(samples);
    free(timestamps);
}

// Helper function to print reduced channel values
void print_reduced_channel_values(READER_HANDLE reader_instance, struct DWChannel ch) {
    printf("===\n");
    printf(" Reduced channel values: \n");
    printf("===\n");

    int sample_cnt;
    double block_size;
    check_error(DWIGetReducedValuesCount(reader_instance, ch.index, &sample_cnt, &block_size));

    printf("  Reduced block count: %d\n", sample_cnt);
    printf("  Reduced block size: %f\n", block_size);

    int display_sample_cnt = sample_cnt;
    if (MAX_SAMPLES_PER_CH >= 0 && display_sample_cnt > MAX_SAMPLES_PER_CH) {
        display_sample_cnt = MAX_SAMPLES_PER_CH;
    }

    struct DWReducedValue* blocks = (struct DWReducedValue*)malloc(sample_cnt * sizeof(struct DWReducedValue));
    check_error(DWIGetReducedValues(reader_instance, ch.index, 0, sample_cnt, blocks));

    for (int i = 0; i < sample_cnt; i++) {
        if (i >= display_sample_cnt) {
            printf("  ...\n");
            break;
        }

        struct DWReducedValue block = blocks[i];
        printf("  Timestamp: %.2f  Ave: %.2f  Min: %.2f  Max: %.2f  Rms: %.2f\n",
            block.time_stamp, block.ave, block.min, block.max, block.rms);
    }

    free(blocks);
}

// Helper functions to get and print file channels
void get_file_channels(READER_HANDLE reader_instance) {
    printf("===\n");
    printf(" Channels: \n");
    printf("===\n");

    int channel_count;
    check_error(DWIGetChannelListCount(reader_instance, &channel_count));

    struct DWChannel* channel_list = (struct DWChannel*)malloc(channel_count * sizeof(struct DWChannel));
    check_error(DWIGetChannelList(reader_instance, channel_list));

    for (int i = 0; i < channel_count; i++) {
        struct DWChannel ch = channel_list[i];
        print_channel_info(reader_instance, ch);
        print_channel_values(reader_instance, ch);
        print_reduced_channel_values(reader_instance, ch);
    }

    free(channel_list);
}

void get_file_complex_channels(READER_HANDLE reader_instance) {
    printf("===\n");
    printf(" Complex channels: \n");
    printf("===\n");

    int channel_count;
    check_error(DWIGetComplexChannelListCount(reader_instance, &channel_count));

    struct DWChannel* channel_list = (struct DWChannel*)malloc(channel_count * sizeof(struct DWChannel));
    check_error(DWIGetComplexChannelList(reader_instance, channel_list));

    for (int i = 0; i < channel_count; i++) {
        struct DWChannel ch = channel_list[i];
        print_channel_info(reader_instance, ch);
        print_complex_channel_values(reader_instance, ch);
        print_reduced_channel_values(reader_instance, ch);
    }

    free(channel_list);
}

void get_file_binary_channels(READER_HANDLE reader_instance) {
    printf("===\n");
    printf(" Binary channels: \n");
    printf("===\n");

    int channel_count;
    check_error(DWIGetBinChannelListCount(reader_instance, &channel_count));

    struct DWChannel* channel_list = (struct DWChannel*)malloc(channel_count * sizeof(struct DWChannel));
    check_error(DWIGetBinChannelList(reader_instance, channel_list));

    for (int i = 0; i < channel_count; i++) {
        struct DWChannel ch = channel_list[i];
        print_channel_info(reader_instance, ch);
        print_binary_channel_values(reader_instance, ch);
    }

    free(channel_list);
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        printf("Usage: %s <datafile> [<datafile> ...]\n", argv[0]);
        return 1;
    }

    if (MAX_SAMPLES_PER_CH >= 0) {
        printf("Max samples per channel limited to %d\n", MAX_SAMPLES_PER_CH);
    }

    if (SKIP_XML_DUMP) {
        printf("XML dump will be skipped\n");
    }

    // Load the DLL
    if (!LoadDWDLL()) {
        printf("Failed to load DWDataReader library\n");
        return 1;
    }

    // Get library version
    int ver_major, ver_minor, ver_patch;
    check_error(DWGetVersionEx(&ver_major, &ver_minor, &ver_patch));
    printf("Dewesoft Data Reader version: %d.%d.%d\n", ver_major, ver_minor, ver_patch);

    // Create reader instance
    READER_HANDLE reader_instance;
    check_error(DWICreateReader(&reader_instance));

    // Process each input file
    for (int i = 1; i < argc; i++) {
        const char* filename = argv[i];
        printf("============================================\n");
        printf("Loading file: %s\n", filename);
        printf("============================================\n");

        // Open the data file
        struct DWFileInfo file_info = { 0 };
        check_error(DWIOpenDataFile(reader_instance, (char*)filename, &file_info));

        printf("DWFile info: \n");
        printf("  Sample rate:      %f\n", file_info.sample_rate);
        printf("  Start store time: %f\n", file_info.start_store_time);
        printf("  Duration:         %f\n", file_info.duration);

        // Get file information
        get_file_metadata(reader_instance);
        get_file_events(reader_instance);
        get_file_header_entries(reader_instance);

        // Get channel data
        get_file_channels(reader_instance);
        get_file_complex_channels(reader_instance);
        get_file_binary_channels(reader_instance);

        // Close the file
        check_error(DWICloseDataFile(reader_instance));
    }

    // Clean up
    check_error(DWIDestroyReader(reader_instance));
    CloseDWDLL();

    return 0;
}
