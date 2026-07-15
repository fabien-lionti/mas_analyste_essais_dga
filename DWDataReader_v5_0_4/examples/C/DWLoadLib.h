#pragma once
#include "../../Objects/DWDataReaderLibTypes.h"

#ifdef DW_IMPL_DLL_FUNCS
    /* For implementation file where functions are loaded */
    #define DW_FUNC_PTR(ret, name, params) \
            typedef ret (*_##name)params; \
            _##name name
#else
    /* For header-only files */
    #define DW_FUNC_PTR(ret, name, params) \
            typedef ret (*_##name)params; \
            extern _##name name
#endif

/* Function declarations using our macro */
DW_FUNC_PTR(enum DWStatus, DWGetLastStatus, (enum DWStatus* status, char* statusMsg, int* statusMsgSize));
DW_FUNC_PTR(enum DWStatus, DWInit, (void));
DW_FUNC_PTR(enum DWStatus, DWDeInit, (void));
DW_FUNC_PTR(enum DWStatus, DWAddReader, (void));
DW_FUNC_PTR(enum DWStatus, DWGetNumReaders, (int* num_readers));
DW_FUNC_PTR(enum DWStatus, DWSetActiveReader, (int index));
DW_FUNC_PTR(int, DWGetVersion, (void));
DW_FUNC_PTR(enum DWStatus, DWOpenDataFile, (char* file_name, struct DWFileInfo* file_info));
DW_FUNC_PTR(enum DWStatus, DWCloseDataFile, (void));
DW_FUNC_PTR(int, DWGetMultiFileIndex, (void));
DW_FUNC_PTR(enum DWStatus, DWGetMeasurementInfo, (struct DWMeasurementInfo* file_info));
DW_FUNC_PTR(int, DWGetChannelListCount, (void));
DW_FUNC_PTR(enum DWStatus, DWGetChannelList, (struct DWChannel* channel_list));
DW_FUNC_PTR(enum DWStatus, DWGetChannelFactors, (int ch_index, double* scale, double* offset));
DW_FUNC_PTR(enum DWStatus, DWGetChannelProps, (int ch_index, enum DWChannelProps ch_prop, void* buffer, int* max_len));
DW_FUNC_PTR(__int64, DWGetBinarySamplesCount, (int ch_index));
DW_FUNC_PTR(enum DWStatus, DWGetBinarySamples, (int ch_index, __int64 sampleIndex, char* data, double* time_stamp, int* datalen));
DW_FUNC_PTR(enum DWStatus, DWGetBinarySamplesEx, (int ch_index, __int64 position, int count, char* data, double* time_stamp, int* datalen));
DW_FUNC_PTR(int, DWGetBinChannelListCount, (void));
DW_FUNC_PTR(enum DWStatus, DWGetBinChannelList, (struct DWChannel* channel_list));
DW_FUNC_PTR(enum DWStatus, DWGetBinRecSamples, (int ch_index, __int64 sampleIndex, int count, struct DWBinarySample* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWGetBinData, (int ch_index, struct DWBinarySample* sample, char* data, __int64* absPos, int binBufSize));
DW_FUNC_PTR(__int64, DWGetScaledSamplesCount, (int ch_index));
DW_FUNC_PTR(enum DWStatus, DWGetScaledSamples, (int ch_index, __int64 position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(__int64, DWGetRawSamplesCount, (int ch_index));
DW_FUNC_PTR(enum DWStatus, DWGetRawSamples, (int ch_index, __int64 position, int count, void* data, double* time_stamp));
DW_FUNC_PTR(int, DWGetComplexChannelListCount, (void));
DW_FUNC_PTR(enum DWStatus, DWGetComplexChannelList, (struct DWChannel* channel_list));
DW_FUNC_PTR(__int64, DWGetComplexScaledSamplesCount, (int ch_index));
DW_FUNC_PTR(enum DWStatus, DWGetComplexScaledSamples, (int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp));
DW_FUNC_PTR(__int64, DWGetComplexRawSamplesCount, (int ch_index));
DW_FUNC_PTR(enum DWStatus, DWGetComplexRawSamples, (int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp));
DW_FUNC_PTR(int, DWGetEventListCount, (void));
DW_FUNC_PTR(enum DWStatus, DWGetEventList, (struct DWEvent* event_list));
DW_FUNC_PTR(enum DWStatus, DWGetStream, (char* stream_name, char* buffer, int* max_len));
DW_FUNC_PTR(enum DWStatus, DWExportHeader, (char* file_name));
DW_FUNC_PTR(int, DWGetTextChannelListCount, (void));
DW_FUNC_PTR(enum DWStatus, DWGetTextChannelList, (struct DWChannel* channel_list));
DW_FUNC_PTR(__int64, DWGetTextValuesCount, (int ch_index));
DW_FUNC_PTR(enum DWStatus, DWGetTextValues, (int ch_index, int position, int count, char* text_values, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWGetReducedValuesCount, (int ch_index, int* count, double* block_size));
DW_FUNC_PTR(enum DWStatus, DWGetReducedValues, (int ch_index, int position, int count, struct DWReducedValue* data));
DW_FUNC_PTR(enum DWStatus, DWGetReducedValuesBlock, (int* ch_ids, int ch_count, int position, int count, int ib_level, struct DWReducedValue* data));
DW_FUNC_PTR(int, DWGetHeaderEntryCount, (void));
DW_FUNC_PTR(enum DWStatus, DWGetHeaderEntryList, (struct DWChannel* channel_list));
DW_FUNC_PTR(enum DWStatus, DWGetHeaderEntryText, (int ch_index, char* text_value, int text_value_size));
DW_FUNC_PTR(int, DWGetStoringType, (void));
DW_FUNC_PTR(int, DWGetArrayInfoCount, (int ch_index));
DW_FUNC_PTR(enum DWStatus, DWGetArrayInfoList, (int ch_index, struct DWArrayInfo* array_inf_list));
DW_FUNC_PTR(enum DWStatus, DWGetArrayIndexValue, (int ch_index, int array_info_index, int array_value_index, char* value, int value_size));
DW_FUNC_PTR(enum DWStatus, DWGetArrayIndexValueF, (int ch_index, int array_info_index, int array_value_index, double* value));
DW_FUNC_PTR(enum DWStatus, DWGetChannelListItem, (int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWGetComplexChannelListItem, (int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWGetHeaderEntryListItem, (int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWGetEventListItem, (int event_Index, int* event_type, double* time_stamp, char* event_text, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWGetReducedAveValues, (int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWGetReducedMinValues, (int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWGetReducedMaxValues, (int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWGetReducedRMSValues, (int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWGetHeaderEntryTextF, (int entry_number, char* text_value, int text_value_size));
DW_FUNC_PTR(enum DWStatus, DWGetHeaderEntryNameF, (int entry_number, char* name, int name_size));
DW_FUNC_PTR(enum DWStatus, DWGetHeaderEntryIDF, (int entry_number, char* ID, int name_size));
DW_FUNC_PTR(double, DWGetEventTimeF, (int event_number));
DW_FUNC_PTR(enum DWStatus, DWGetEventTextF, (int event_number, char* text, int text_size));
DW_FUNC_PTR(int, DWGetEventTypeF, (int event_number));
DW_FUNC_PTR(int, DWGetReducedDataChannelCountF, (void));
DW_FUNC_PTR(enum DWStatus, DWGetReducedDataChannelNameF, (int Channel_Number, char* name, int name_size));
DW_FUNC_PTR(int, DWGetReducedDataChannelIndexF, (char* name));
DW_FUNC_PTR(enum DWStatus, DWGetRecudedDataChannelInfoF, (int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, int* Channel_Length, double* ch_rate));
DW_FUNC_PTR(enum DWStatus, DWGetRecudedDataF, (int Channel_Number, double* X_Axis, double* Y_Axis, int position, int count));
DW_FUNC_PTR(enum DWStatus, DWGetRecudedYDataF, (int Channel_Number, double* Y_Axis, int position, int count));
DW_FUNC_PTR(enum DWStatus, DWGetRecudedDataAllF, (int Channel_Number, double* Y_MIN_Axis, double* Y_AVE_Axis, double* Y_MAX_Axis, double* Y_RMS_Axis, int position, int count));
DW_FUNC_PTR(int, DWGetTriggerDataTriggerCountF, (void));
DW_FUNC_PTR(double, DWGetTriggerDataTriggerTimeF, (int Trigger_Number));
DW_FUNC_PTR(enum DWStatus, DWGetTriggerDataChannelNameF, (int Channel_Number, char* name, int name_size));
DW_FUNC_PTR(int, DWGetTriggerDataChannelIndexF, (char* name));
DW_FUNC_PTR(enum DWStatus, DWGetTriggerDataChannelInfoF, (int Trigger_Number, int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, double* Channel_Length, double* ch_rate, int* ch_type));
DW_FUNC_PTR(enum DWStatus, DWGetTriggerDataF, (int Trigger_Number, int Channel_Number, double* Y_Axis, double* X_Axis, double position, int count));

/* Instance-based API */
DW_FUNC_PTR(enum DWStatus, DWICreateReader, (READER_HANDLE* handle));
DW_FUNC_PTR(enum DWStatus, DWIDestroyReader, (READER_HANDLE handle));
DW_FUNC_PTR(enum DWStatus, DWGetVersionEx, (int* major, int* minor, int* patch));
DW_FUNC_PTR(enum DWStatus, DWIOpenDataFile, (READER_HANDLE handle, char* file_name, struct DWFileInfo* file_info));
DW_FUNC_PTR(enum DWStatus, DWICloseDataFile, (READER_HANDLE handle));
DW_FUNC_PTR(enum DWStatus, DWIGetMultiFileIndex, (READER_HANDLE handle, int* index));
DW_FUNC_PTR(enum DWStatus, DWIGetMeasurementInfo, (READER_HANDLE handle, struct DWMeasurementInfo* file_info));
DW_FUNC_PTR(enum DWStatus, DWIGetChannelListCount, (READER_HANDLE handle, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetChannelList, (READER_HANDLE handle, struct DWChannel* channel_list));
DW_FUNC_PTR(enum DWStatus, DWIGetChannelFactors, (READER_HANDLE handle, int ch_index, double* scale, double* offset));
DW_FUNC_PTR(enum DWStatus, DWIGetChannelProps, (READER_HANDLE handle, int ch_index, enum DWChannelProps ch_prop, void* buffer, int* max_len));
DW_FUNC_PTR(enum DWStatus, DWIGetBinarySamplesCount, (READER_HANDLE handle, int ch_index, __int64* count));
DW_FUNC_PTR(enum DWStatus, DWIGetBinarySamples, (READER_HANDLE handle, int ch_index, __int64 sampleIndex, char* data, double* time_stamp, int* datalen));
DW_FUNC_PTR(enum DWStatus, DWIGetBinarySamplesEx, (READER_HANDLE handle, int ch_index, __int64 position, int count, char* data, double* time_stamp, int* datalen));
DW_FUNC_PTR(enum DWStatus, DWIGetBinChannelListCount, (READER_HANDLE handle, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetBinChannelList, (READER_HANDLE handle, struct DWChannel* channel_list));
DW_FUNC_PTR(enum DWStatus, DWIGetBinRecSamples, (READER_HANDLE handle, int ch_index, __int64 sampleIndex, int count, struct DWBinarySample* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetBinData, (READER_HANDLE handle, int ch_index, struct DWBinarySample* sample, char* data, __int64* absPos, int binBufSize));
DW_FUNC_PTR(enum DWStatus, DWIGetScaledSamplesCount, (READER_HANDLE handle, int ch_index, __int64* count));
DW_FUNC_PTR(enum DWStatus, DWIGetScaledSamples, (READER_HANDLE handle, int ch_index, __int64 position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetRawSamplesCount, (READER_HANDLE handle, int ch_index, __int64* count));
DW_FUNC_PTR(enum DWStatus, DWIGetRawSamples, (READER_HANDLE handle, int ch_index, __int64 position, int count, void* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetComplexChannelListCount, (READER_HANDLE handle, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetComplexChannelList, (READER_HANDLE handle, struct DWChannel* channel_list));
DW_FUNC_PTR(enum DWStatus, DWIGetComplexScaledSamplesCount, (READER_HANDLE handle, int ch_index, __int64* count));
DW_FUNC_PTR(enum DWStatus, DWIGetComplexScaledSamples, (READER_HANDLE handle, int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetComplexRawSamplesCount, (READER_HANDLE handle, int ch_index, __int64* count));
DW_FUNC_PTR(enum DWStatus, DWIGetComplexRawSamples, (READER_HANDLE handle, int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetEventListCount, (READER_HANDLE handle, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetEventList, (READER_HANDLE handle, struct DWEvent* event_list));
DW_FUNC_PTR(enum DWStatus, DWIGetStream, (READER_HANDLE handle, char* stream_name, char* buffer, int* max_len));
DW_FUNC_PTR(enum DWStatus, DWIExportHeader, (READER_HANDLE handle, char* file_name));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedValuesCount, (READER_HANDLE handle, int ch_index, int* count, double* block_size));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedValues, (READER_HANDLE handle, int ch_index, int position, int count, struct DWReducedValue* data));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedValuesBlock, (READER_HANDLE handle, int* ch_ids, int ch_count, int position, int count, int ib_level, struct DWReducedValue* data));
DW_FUNC_PTR(enum DWStatus, DWIGetHeaderEntryCount, (READER_HANDLE handle, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetHeaderEntryList, (READER_HANDLE handle, struct DWChannel* channel_list));
DW_FUNC_PTR(enum DWStatus, DWIGetHeaderEntryText, (READER_HANDLE handle, int ch_index, char* text_value, int text_value_size));
DW_FUNC_PTR(enum DWStatus, DWIGetStoringType, (READER_HANDLE handle, int* storingType));
DW_FUNC_PTR(enum DWStatus, DWIGetArrayInfoCount, (READER_HANDLE handle, int ch_index, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetArrayInfoList, (READER_HANDLE handle, int ch_index, struct DWArrayInfo* array_inf_list));
DW_FUNC_PTR(enum DWStatus, DWIGetArrayIndexValue, (READER_HANDLE handle, int ch_index, int array_info_index, int array_value_index, char* value, int value_size));
DW_FUNC_PTR(enum DWStatus, DWIGetArrayIndexValueF, (READER_HANDLE handle, int ch_index, int array_info_index, int array_value_index, double* value));
DW_FUNC_PTR(enum DWStatus, DWIGetChannelListItem, (READER_HANDLE handle, int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWIGetComplexChannelListItem, (READER_HANDLE handle, int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWIGetHeaderEntryListItem, (READER_HANDLE handle, int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWIGetEventListItem, (READER_HANDLE handle, int event_Index, int* event_type, double* time_stamp, char* event_text, int max_char_size));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedAveValues, (READER_HANDLE handle, int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedMinValues, (READER_HANDLE handle, int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedMaxValues, (READER_HANDLE handle, int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedRMSValues, (READER_HANDLE handle, int ch_index, int position, int count, double* data, double* time_stamp));
DW_FUNC_PTR(enum DWStatus, DWIGetHeaderEntryTextF, (READER_HANDLE handle, int entry_number, char* text_value, int text_value_size));
DW_FUNC_PTR(enum DWStatus, DWIGetHeaderEntryNameF, (READER_HANDLE handle, int entry_number, char* name, int name_size));
DW_FUNC_PTR(enum DWStatus, DWIGetHeaderEntryIDF, (READER_HANDLE handle, int entry_number, char* ID, int name_size));
DW_FUNC_PTR(enum DWStatus, DWIGetEventTimeF, (READER_HANDLE handle, int event_number, double* eventTime));
DW_FUNC_PTR(enum DWStatus, DWIGetEventTextF, (READER_HANDLE handle, int event_number, char* text, int text_size));
DW_FUNC_PTR(enum DWStatus, DWIGetEventTypeF, (READER_HANDLE handle, int event_number, enum DWEventType* eventType));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedDataChannelCountF, (READER_HANDLE handle, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedDataChannelNameF, (READER_HANDLE handle, int Channel_Number, char* name, int name_size));
DW_FUNC_PTR(enum DWStatus, DWIGetReducedDataChannelIndexF, (READER_HANDLE handle, char* name, int* index));
DW_FUNC_PTR(enum DWStatus, DWIGetRecudedDataChannelInfoF, (READER_HANDLE handle, int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, int* Channel_Length, double* ch_rate));
DW_FUNC_PTR(enum DWStatus, DWIGetRecudedDataF, (READER_HANDLE handle, int Channel_Number, double* X_Axis, double* Y_Axis, int position, int count));
DW_FUNC_PTR(enum DWStatus, DWIGetRecudedYDataF, (READER_HANDLE handle, int Channel_Number, double* Y_Axis, int position, int count));
DW_FUNC_PTR(enum DWStatus, DWIGetRecudedDataAllF, (READER_HANDLE handle, int Channel_Number, double* Y_MIN_Axis, double* Y_AVE_Axis, double* Y_MAX_Axis, double* Y_RMS_Axis, int position, int count));
DW_FUNC_PTR(enum DWStatus, DWIGetTriggerDataTriggerCountF, (READER_HANDLE handle, int* count));
DW_FUNC_PTR(enum DWStatus, DWIGetTriggerDataTriggerTimeF, (READER_HANDLE handle, int Trigger_Number, double* time));
DW_FUNC_PTR(enum DWStatus, DWIGetTriggerDataChannelNameF, (READER_HANDLE handle, int Channel_Number, char* name, int name_size));
DW_FUNC_PTR(enum DWStatus, DWIGetTriggerDataChannelIndexF, (READER_HANDLE handle, char* name, int* index));
DW_FUNC_PTR(enum DWStatus, DWIGetTriggerDataChannelInfoF, (READER_HANDLE handle, int Trigger_Number, int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, double* Channel_Length, double* ch_rate, int* ch_type));
DW_FUNC_PTR(enum DWStatus, DWIGetTriggerDataF, (READER_HANDLE handle, int Trigger_Number, int Channel_Number, double* Y_Axis, double* X_Axis, double position, int count));

int LoadDWDLL();
int CloseDWDLL();