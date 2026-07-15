#pragma once
#include "DWDataReaderLibDef.h"
#include "DWDataReaderLibTypes.h"

/**
 * @file DWDataReaderLibFuncs.h
 *
 * Functions exposed from DWDataReader library.
 */

 /**
  * @brief Retrieves the status and error message from last operation
  *
  * This function can be used to check for errors or other status information after
  * performing operations with the library.
  *
  * @param[out] status Pointer to an enum DWStatus where the last status will be stored.
  * @param[out] statusMsg Pointer to a character array where the status message will be stored.
  * @param[in,out] statusMsgSize Pointer to an integer representing the size of the status message buffer.
  *                              The function will update this value with the actual size of the message.
  *
  * @return An enumeration value of type DWStatus indicating the result of the operation.
  */
DWLIB_API enum DWStatus DWGetLastStatus(enum DWStatus* status, char* statusMsg, int* statusMsgSize);

/**
  * @brief Initializes the DWDataReader library
  *
  * This function must be called before any other DWDataReader library functions.
  * It performs necessary setup and initialization of internal resources.
  *
  * @return An enumeration value of type DWStatus indicating the result of the operation.
  *
  * @deprecated This function is deprecated and will be removed in a future release.
  * Please use @ref DWICreateReader instead to create instance-based readers.
  */
DWLIB_API enum DWStatus DWInit();

/**
 * @brief Deinitializes the DWDataReader library
 *
 * This function should be called when the application is finished using
 * the DWDataReader library to properly release all resources and perform cleanup.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIDestroyReader instead to destroy specific reader instances.
 */
DWLIB_API enum DWStatus DWDeInit();

/**
 * @brief Creates a new reader within the shared reader pool
 * 
 * This function creates a new reader instance in the application's shared reader pool
 * and sets it as the active reader. The DWInit function must be called before using
 * this function.
 * 
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 * 
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWICreateReader instead to create independent reader instances.
 */
DWLIB_API enum DWStatus DWAddReader();

/**
 * @brief Retrieves the number of readers in the shared reader pool
 * 
 * This function returns the count of reader instances that have been created
 * in the application's shared reader pool.
 * 
 * @param[out] num_readers Pointer to an integer where the number of readers will be stored.
 * 
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 * 
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use instance-based readers with @ref DWICreateReader instead of the shared reader pool.
 */
DWLIB_API enum DWStatus DWGetNumReaders(int* num_readers);

/**
 * @brief Sets the active reader in the shared reader pool
 *
 * @param[in] index The reader index from the shared reader pool to be set as active.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use instance-based readers with @ref DWICreateReader instead of the shared reader pool.
 */
DWLIB_API enum DWStatus DWSetActiveReader(int index);

/**
 * @brief Creates a new reader instance handle
 *
 * The handle can be used to perform various operations on the data file with instanced functions.
 *
 * @param[out] handle A pointer to a READER_HANDLE where the created instance will be stored.
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWICreateReader(READER_HANDLE* handle);

/**
 * @brief Destroys the specified reader instance
 *
 * This function releases all resources associated with the specified reader instance.
 *
 * @param[in] handle The READER_HANDLE of the instance to be destroyed.
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIDestroyReader(READER_HANDLE handle);

/**
 * @brief Gets the version number of the DWDataReader library
 *
 * Returns the version number of the currently loaded DWDataReader library.
 * The version format depends on the library implementation.
 *
 * @return An integer representing the library version.
 *
 * @remark Version is hashed into an integer value in the manner of `MAJOR * 1.000.000 + MINOR * 1.000 + PATCH`
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use `DWGetVersionEx` instead.
 */
DWLIB_API int DWGetVersion();

/**
 * @brief Gets the version number of the DWDataReader library in major, minor, and patch format
 *
 * Returns the version number of the currently loaded DWDataReader library.
 * The version format is split into major, minor, and patch components.
 *
 * @param[out] major Pointer to an integer where the major version will be stored.
 * @param[out] minor Pointer to an integer where the minor version will be stored.
 * @param[out] patch Pointer to an integer where the patch version will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWGetVersionEx(int* major, int* minor, int* patch);

/**
 * @brief Opens the specified file and fills the file_info structure with
 * information about the file contents.
 *
 * @param[in] file_name Path to the file to be opened
 * @param[out] file_info Pointer to a preallocated DWFileInfo structure to read file information
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIOpenDataFile instead.
 */
DWLIB_API enum DWStatus DWOpenDataFile(char* file_name, struct DWFileInfo* file_info);

/**
 * @brief Opens the specified file and fills the file_info structure with
 * information about the file contents using a specific reader instance.
 *
 * This function opens a data file specified by `file_name` using the provided reader instance
 * and populates the `file_info` structure with details about the file contents.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] file_name Path to the file to be opened
 * @param[out] file_info Pointer to a preallocated DWFileInfo structure to read file information
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIOpenDataFile(READER_HANDLE reader, char* file_name, struct DWFileInfo* file_info);

/**
 * @brief Closes the currently open data file.
 *
 * This function is used to close a data file that has been previously opened.
 * It ensures that all resources associated with the file are properly released before opening a new file.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWICloseDataFile instead.
 */
DWLIB_API enum DWStatus DWCloseDataFile();

/**
 * @brief Closes the currently open data file for a specific reader instance.
 *
 * This function closes a data file that has been previously opened with the specified reader instance.
 * It ensures that all resources associated with the file are properly released.
 *
 * @param[in] reader The reader instance handle associated with the file to close.
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWICloseDataFile(READER_HANDLE reader);

/**
 * @brief Retrieves detailed information about the current measurement.
 *
 * This function populates a DWMeasurementInfo structure with details
 * such as the sample rate, start times for measurement and storage, and
 * the duration of the measurement. This information is useful for understanding
 * the timing and scale of recorded data.
 *
 * @param[out] measurement_info A pointer to a DWMeasurementInfo structure that will be
 *                              filled with the measurement details. The structure must be
 *                              pre-allocated before calling this function.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetMeasurementInfo instead.
 */
DWLIB_API enum DWStatus DWGetMeasurementInfo(struct DWMeasurementInfo* measurement_info);

/**
 * @brief Retrieves detailed information about the current measurement using a specific reader instance.
 *
 * This function populates a DWMeasurementInfo structure with details such as sample rate,
 * start times for measurement and storage, and duration using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] measurement_info A pointer to a DWMeasurementInfo structure that will be
 *                              filled with the measurement details. The structure must be
 *                              pre-allocated before calling this function.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetMeasurementInfo(READER_HANDLE reader, struct DWMeasurementInfo* measurement_info);

/**
 * @brief Retrieves the number of available channels.
 *
 * @return The number of channels available.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetChannelListCount instead.
 */
DWLIB_API int DWGetChannelListCount();

/**
 * @brief Retrieves the number of available channels using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] count Pointer to an integer where the channel count will be stored.
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetChannelListCount(READER_HANDLE reader, int* count);

/**
 * @brief Retrieves the number of available complex channels.
 *
 * @return The number of complex channels available.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetComplexChannelListCount instead.
 */
DWLIB_API int DWGetComplexChannelListCount();

/**
 * @brief Retrieves the number of available complex channels using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] count Pointer to an integer where the complex channel count will be stored.
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetComplexChannelListCount(READER_HANDLE reader, int* count);

/**
 * @brief Retrieves the list of available complex channels.
 *
 * This function populates an array of DWChannel structures with information about
 * the available complex channels. Each DWChannel structure contains
 * details such as the channel's index, name, unit, description, and other properties.
 *
 * @param[out] channel_list A pointer to an array of DWChannel structures to be filled
 *                      with channel information. The array must be pre-allocated with
 *                      sufficient size to hold the data.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @remark Size of `channel_list` can be determined by calling the DWGetComplexChannelListCount function.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetComplexChannelList instead.
 */
DWLIB_API enum DWStatus DWGetComplexChannelList(struct DWChannel* channel_list);

/**
 * @brief Retrieves the list of available complex channels using a specific reader instance.
 *
 * This function populates an array of DWChannel structures with information about
 * the available complex channels using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] channel_list A pointer to an array of DWChannel structures to be filled
 *                      with channel information. The array must be pre-allocated.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetComplexChannelList(READER_HANDLE reader, struct DWChannel* channel_list);

/**
 * @brief Retrieves the list of available channels.
 *
 * This function populates an array of DWChannel structures with information about
 * the available channels.
 *
 * @param[out] channel_list A pointer to an array of DWChannel structures to be filled
 *                      with channel information. The array must be pre-allocated with
 *                      sufficient size to hold the data.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @remark Size of `channel_list` can be determined by calling the DWGetChannelListCount() function.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetChannelList instead.
 */
DWLIB_API enum DWStatus DWGetChannelList(struct DWChannel* channel_list);

/**
 * @brief Retrieves the list of available channels using a specific reader instance.
 *
 * This function populates an array of DWChannel structures with information about
 * the available channels using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] channel_list A pointer to an array of DWChannel structures to be filled
 *                      with channel information. The array must be pre-allocated.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetChannelList(READER_HANDLE reader, struct DWChannel* channel_list);

/**
 * @brief Retrieves scaling factors for a specified channel.
 *
 * This function retrieves the scale and offset values associated with a channel identified by `ch_index`.
 * These values are used for converting raw data to scaled units through the formula:
 * scaled_value = (raw_value * scale) + offset
 *
 * @param[in]  ch_index The index of the channel for which to retrieve scaling factors.
 * @param[out] scale    A pointer to a double where the scale factor will be stored.
 *                      This must be pre-allocated before calling this function.
 * @param[out] offset   A pointer to a double where the offset value will be stored.
 *                      This must be pre-allocated before calling this function.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetChannelFactors instead.
 */
DWLIB_API enum DWStatus DWGetChannelFactors(int ch_index, double* scale, double* offset);

/**
 * @brief Retrieves scaling factors for a specified channel using a specific reader instance.
 *
 * This function retrieves the scale and offset values associated with a channel
 * using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel for which to retrieve scaling factors.
 * @param[out] scale A pointer to a double where the scale factor will be stored.
 * @param[out] offset A pointer to a double where the offset value will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetChannelFactors(READER_HANDLE reader, int ch_index, double* scale, double* offset);

/**
 * @brief Retrieves the count of scaled samples available for a specified channel.
 *
 * This function returns the total number of scaled samples currently available for
 * the given channel index. Scaled samples refer to data that has been processed
 * to apply calibration or scaling factors, converting raw data into meaningful
 * engineering units.
 *
 * @param[in] ch_index The index of the channel for which to retrieve the sample count.
 *
 * @return The number of scaled samples available for the specified channel.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetScaledSamplesCount instead.
 */
DWLIB_API __int64 DWGetScaledSamplesCount(int ch_index);

/**
 * @brief Retrieves the count of scaled samples available for a specified channel using a specific reader instance.
 *
 * This function returns the total number of scaled samples currently available for
 * the given channel index using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel for which to retrieve the sample count.
 * @param[out] count Pointer to an __int64 where the sample count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetScaledSamplesCount(READER_HANDLE reader, int ch_index, __int64* count);

/**
 * @brief Retrieves the count of scaled samples available for a specified complex channel.
 *
 * This function returns the total number of scaled samples available for a complex data channel,
 * identified by its channel index. Complex scaled samples include both real and imaginary components that
 * have been processed and scaled from their raw form into meaningful units.
 *
 * @param[in] ch_index The index of the complex channel for which to retrieve the scaled sample count.
 *
 * @return The number of scaled complex samples available for the specified channel.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetComplexScaledSamplesCount instead.
 */
DWLIB_API __int64 DWGetComplexScaledSamplesCount(int ch_index);

/**
 * @brief Retrieves the count of scaled samples available for a specified complex channel using a specific reader instance.
 *
 * This function returns the total number of scaled samples available for a complex data channel
 * using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the complex channel for which to retrieve the scaled sample count.
 * @param[out] count Pointer to an __int64 where the sample count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetComplexScaledSamplesCount(READER_HANDLE reader, int ch_index, __int64* count);

/**
 * @brief Retrieves a series of scaled samples and their timestamps for a specified channel.
 *
 * This function fetches a specified number of scaled samples starting from a given position
 * for the channel identified by `ch_index`. The retrieved samples are stored in the provided
 * data array along with their corresponding timestamps in the time_stamp array.
 *
 * @param[in]  ch_index   The index of the channel from which to retrieve scaled samples.
 * @param[in]  position   The starting position within the channel's data to begin retrieval.
 * @param[in]  count      The number of samples to retrieve.
 * @param[out] data       A pointer to an array where the retrieved sample values will be stored.
 *                        This array must be pre-allocated to hold at least `count` samples.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *                        This array must also be pre-allocated and match the size of the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetScaledSamples instead.
 */
DWLIB_API enum DWStatus DWGetScaledSamples(int ch_index, __int64 position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves a series of scaled samples and their timestamps for a specified channel using a specific reader instance.
 *
 * This function fetches scaled samples using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve scaled samples.
 * @param[in] position The starting position within the channel's data to begin retrieval.
 * @param[in] count The number of samples to retrieve.
 * @param[out] data A pointer to an array where the retrieved sample values will be stored.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetScaledSamples(READER_HANDLE reader, int ch_index, __int64 position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves a series of complex scaled samples and their timestamps for a specified channel.
 *
 * This function fetches a specified number of complex scaled samples starting from a given
 * position for the channel identified by `ch_index`. The retrieved samples, each with real and
 * imaginary components, are stored in the provided `data` array along with their corresponding
 * timestamps in the `time_stamp` array.
 *
 * @param[in]  ch_index   The index of the complex channel from which to retrieve scaled samples.
 * @param[in]  position   The starting position within the channel's data to begin retrieval.
 * @param[in]  count      The number of complex samples to retrieve.
 * @param[out] data       A pointer to an array of `DWComplex` structures where the retrieved sample
 *                        values will be stored. This array must be pre-allocated to hold at least `count` samples.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps for each sample
 *                        will be stored. This array must also be pre-allocated and match the size of
 *                        the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetComplexScaledSamples instead.
 */
DWLIB_API enum DWStatus DWGetComplexScaledSamples(int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp);

/**
 * @brief Retrieves a series of complex scaled samples and their timestamps for a specified channel using a specific reader instance.
 *
 * This function fetches complex scaled samples using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the complex channel from which to retrieve scaled samples.
 * @param[in] position The starting position within the channel's data to begin retrieval.
 * @param[in] count The number of complex samples to retrieve.
 * @param[out] data A pointer to an array of `DWComplex` structures where the sample values will be stored.
 * @param[out] time_stamp A pointer to an array where the timestamps will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetComplexScaledSamples(READER_HANDLE reader, int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp);

/**
 * @brief Retrieves the count of events available in the current event list.
 *
 * This function returns the total number of events currently recorded in the system's
 * event list. This count can be used to determine the number of events that can be
 * accessed or processed in subsequent operations.
 *
 * @return The number of events available in the event list.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetEventListCount instead.
 */
DWLIB_API int DWGetEventListCount();

/**
 * @brief Retrieves the count of events available in the current event list using a specific reader instance.
 *
 * This function returns the number of events using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] count Pointer to an integer where the event count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetEventListCount(READER_HANDLE reader, int* count);

/**
 * @brief Retrieves the list of events from the current event list.
 *
 * This function fills an array of `DWEvent` structures with information about
 * each event recorded in the system. Events typically contain details such as
 * event type, timestamp, and descriptive text.
 *
 * @param[out] event_list A pointer to an array of `DWEvent` structures that will be
 *                        filled with the event data. The array must be pre-allocated and
 *                        sized based on the number of events (retrievable via `DWGetEventListCount`).
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetEventList instead.
 */
DWLIB_API enum DWStatus DWGetEventList(struct DWEvent* event_list);

/**
 * @brief Retrieves the list of events from the current event list using a specific reader instance.
 *
 * This function fills an array of `DWEvent` structures with event information using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] event_list A pointer to an array of `DWEvent` structures to be filled with event data.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetEventList(READER_HANDLE reader, struct DWEvent* event_list);

/**
 * @brief Exports the setup information to a specified file.
 *
 * This function exports the setup XML structure of the currently opened datafile to a new file specified by
 * the `file_name` parameter.
 *
 * @param[in] file_name A pointer to a null-terminated string specifying the path and name
 *                      of the file to which the header information will be exported.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIExportHeader instead.
 */
DWLIB_API enum DWStatus DWExportHeader(char* file_name);

/**
 * @brief Exports the setup information to a specified file using a specific reader instance.
 *
 * This function exports the setup XML structure using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] file_name A pointer to a null-terminated string specifying the export file path.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIExportHeader(READER_HANDLE reader, char* file_name);

/**
 * @brief Retrieves the count of text channels available in the current context.
 *
 * This function returns the total number of text channels that are currently available.
 * Text channels typically refer to channels handling non-numeric data, such as strings
 * or textual metadata.
 *
 * @return The number of text channels available.
 *
 * @deprecated Text channels are no longer used in DewesoftX. They have been replaced with binary channels.
 * See `DWGetBinChannelListCount` for binary channels.
 */
DWLIB_API int DWGetTextChannelListCount();

/**
 * @brief Retrieves a list of text channels available in the current context.
 *
 * This function populates an array of `DWChannel` structures with information about
 * each available text channel. Text channels are typically used for non-numeric data,
 * such as strings or descriptive metadata associated with data streams.
 *
 * @param[out] channel_list A pointer to an array of `DWChannel` structures that will be
 *                          filled with the text channel information. The array must be
 *                          pre-allocated and should have enough space to store information
 *                          for the available text channels.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated Text channels are no longer used in DewesoftX. They have been replaced with binary channels.
 * See `DWGetBinChannelListCount` for binary channels.
 */
DWLIB_API enum DWStatus DWGetTextChannelList(struct DWChannel* channel_list);

/**
 * @brief Retrieves the count of text values available for a specified text channel.
 *
 * This function returns the total number of text values currently available for
 * the text channel identified by `ch_index`. Text channels handle non-numeric data,
 * such as strings or textual metadata.
 *
 * @param[in] ch_index The index of the text channel for which to retrieve the text value count.
 *
 * @return The number of text values available for the specified channel.
 *
 * @deprecated Text channels are no longer used in DewesoftX. They have been replaced with binary channels.
 * See `DWGetBinarySamplesCount` for binary channels.
 */
DWLIB_API __int64 DWGetTextValuesCount(int ch_index);

/**
 * @brief Retrieves a series of text values and their timestamps for a specified text channel.
 *
 * This function fetches a specified number of text values starting from a given position
 * for the channel identified by `ch_index`. The retrieved text values are stored in the
 * `text_values` buffer, and their corresponding timestamps are stored in the `time_stamp` array.
 *
 * @param[in]  ch_index    The index of the text channel from which to retrieve text values.
 * @param[in]  position    The starting position within the channel's data to begin retrieval.
 * @param[in]  count       The number of text values to retrieve.
 * @param[out] text_values A pointer to a buffer where the retrieved text values will be stored.
 *                         The buffer should be large enough to hold all text values.
 *                         Text values might be null-terminated strings depending on the format.
 * @param[out] time_stamp  A pointer to an array where the corresponding timestamps for each text value
 *                         will be stored. This array must be pre-allocated and should match the size of
 *                         the `count` parameter.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated Text channels are no longer used in DewesoftX. They have been replaced with binary channels.
 * See `DWGetBinarySamples` and `DWGetBinarySamplesEx` for binary channels.
 */
DWLIB_API enum DWStatus DWGetTextValues(int ch_index, int position, int count, char* text_values, double* time_stamp);

/**
 * @brief Retrieves the count of reduced values and the block size for a specified channel.
 *
 * This function provides the number of reduced values available for a given channel identified by `ch_index`.
 * It also returns the block size, which indicates the size of data blocks used when calculating reduced values.
 * Reduced values typically summarize data over intervals using statistical measures, such as average, min, max, etc.
 *
 * @param[in]  ch_index   The index of the channel for which to retrieve the reduced value count.
 * @param[out] count      A pointer to an integer where the function will store the number of reduced values available.
 * @param[out] block_size A pointer to a double where the function will store the size of data blocks, in seconds,
 *                        used for calculating reduced values.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedValuesCount instead.
 */
DWLIB_API enum DWStatus DWGetReducedValuesCount(int ch_index, int* count, double* block_size);

/**
 * @brief Retrieves the count of reduced values and the block size using a specific reader instance.
 *
 * This function provides the number of reduced values and block size using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel for which to retrieve the reduced value count.
 * @param[out] count A pointer to an integer where the number of reduced values will be stored.
 * @param[out] block_size A pointer to a double where the block size will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedValuesCount(READER_HANDLE reader, int ch_index, int* count, double* block_size);

/**
 * @brief Retrieves a series of reduced values for a specified channel.
 *
 * This function fetches a specified number of reduced values starting from a given position
 * for the channel identified by `ch_index`. Reduced values provide summarized statistics such as
 * average, minimum, maximum, and RMS over defined intervals, and are stored in the provided `data` array.
 *
 * @param[in]  ch_index The index of the channel from which to retrieve reduced values.
 * @param[in]  position The starting position within the channel's reduced data to begin retrieval.
 * @param[in]  count    The number of reduced values to retrieve.
 * @param[out] data     A pointer to an array of `DWReducedValue` structures where the function will store
 *                      the retrieved reduced values. This array must be allocated to hold at least `count`
 *                      elements.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedValues instead.
 */
DWLIB_API enum DWStatus DWGetReducedValues(int ch_index, int position, int count, struct DWReducedValue* data);

/**
 * @brief Retrieves a series of reduced values for a specified channel using a specific reader instance.
 *
 * This function fetches reduced values using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve reduced values.
 * @param[in] position The starting position within the channel's reduced data.
 * @param[in] count The number of reduced values to retrieve.
 * @param[out] data A pointer to an array of `DWReducedValue` structures for the retrieved values.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedValues(READER_HANDLE reader, int ch_index, int position, int count, struct DWReducedValue* data);

/**
 * @brief Retrieves the count of entries in the current header.
 *
 * This function returns the total number of entries in the header of the current context.
 * Header entries typically contain metadata or configuration information about the data
 * being processed or analyzed.
 *
 * @return The number of entries in the header.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetHeaderEntryCount instead.
 */
DWLIB_API int DWGetHeaderEntryCount();

/**
 * @brief Retrieves the count of entries in the current header using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] count Pointer to an integer where the header entry count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetHeaderEntryCount(READER_HANDLE reader, int* count);

/**
 * @brief Retrieves the list of entries in the current header.
 *
 * This function populates an array with information about each entry in the
 * header of the current context. Header entries typically contain metadata or
 * configuration information that describes the data's properties, structure, or context.
 *
 * @param[out] entry_list A pointer to an array or buffer that will be filled with the header entries.
 *                        This must be pre-allocated and should have sufficient capacity to store all
 *                        header entries, based on the count retrieved from `DWGetHeaderEntryCount()`.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetHeaderEntryList instead.
 */
DWLIB_API enum DWStatus DWGetHeaderEntryList(struct DWChannel* channel_list);

/**
 * @brief Retrieves the list of entries in the current header using a specific reader instance.
 *
 * This function populates an array with header entry information using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] entry_list A pointer to an array to be filled with the header entries.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetHeaderEntryList(READER_HANDLE reader, struct DWChannel* entry_list);

/**
 * @brief Retrieves the textual content of a specific header entry by index.
 *
 * This function retrieves the text value associated with a particular header
 * entry identified by `ch_index`. The text is copied into the provided buffer,
 * ensuring that it does not exceed the buffer's allocated size.
 *
 * @param[in]  ch_index        The index of the header entry to retrieve.
 * @param[out] text_value      A pointer to a char buffer where the text value of the header entry
 *                             will be stored. This buffer must be pre-allocated.
 * @param[in]  text_value_size The size of the `text_value` buffer, indicating the maximum number
 *                             of characters (including null-terminator) that can be safely stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetHeaderEntryText instead.
 */
DWLIB_API enum DWStatus DWGetHeaderEntryText(int ch_index, char* text_value, int text_value_size);

/**
 * @brief Retrieves the textual content of a header entry using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the header entry to retrieve.
 * @param[out] text_value A pointer to a char buffer where the text value will be stored.
 * @param[in] text_value_size The maximum size of the text_value buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetHeaderEntryText(READER_HANDLE reader, int ch_index, char* text_value, int text_value_size);

/**
 * @brief Retrieves the index of the currently open multifile.
 *
 * @return The index of the current multi-file data set.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetMultiFileIndex instead.
 */
DWLIB_API int DWGetMultiFileIndex();

/**
 * @brief Retrieves the index of the currently open multifile using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] index Pointer to an integer where the multifile index will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetMultiFileIndex(READER_HANDLE reader, int* index);

/**
 * @brief Retrieves the current data storing type.
 *
 * This function returns the mode or type of data storing currently in use.
 * The data storing type indicates how data is being recorded or managed,
 * such as whether it is stored continuously, on a trigger, or with other specific conditions.
 *
 * @return An integer value indicating \ref StoringTypes.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetStoringType instead.
 */
DWLIB_API int DWGetStoringType();

/**
 * @brief Retrieves the current data storing type using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] storingType Pointer to a DWStoringType enum where the storing type will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetStoringType(READER_HANDLE reader, enum DWStoringType* storingType);

/**
 * @brief Retrieves the count of array information entries for a specified channel.
 *
 * This function returns the number of array information entries available for the
 * channel identified by `ch_index`.
 *
 * @param[in] ch_index The index of the channel for which to retrieve the array information count.
 *
 * @return The number of array information entries for the specified channel.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetArrayInfoCount instead.
 */
DWLIB_API int DWGetArrayInfoCount(int ch_index);

/**
 * @brief Retrieves the count of array information entries using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel to query.
 * @param[out] count Pointer to an integer where the array info count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetArrayInfoCount(READER_HANDLE reader, int ch_index, int* count);

/**
 * @brief Retrieves a list of array information entries for a specified channel.
 *
 * This function populates an array of `DWArrayInfo` structures with metadata
 * about each array dimension or axis of the channel identified by `ch_index`.
 *
 * @param[in]  ch_index       The index of the channel for which to retrieve the array information list.
 * @param[out] array_inf_list A pointer to an array of `DWArrayInfo` structures that will be filled
 *                            with the array information. The array must be pre-allocated and should
 *                            have enough capacity to store all the entries retrieved, based on
 *                            `DWGetArrayInfoCount()`.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetArrayInfoList instead.
 */
DWLIB_API enum DWStatus DWGetArrayInfoList(int ch_index, struct DWArrayInfo* array_inf_list);

/**
 * @brief Retrieves a list of array information entries using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel for array information retrieval.
 * @param[out] array_inf_list A pointer to an array of DWArrayInfo structures to be filled.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetArrayInfoList(READER_HANDLE reader, int ch_index, struct DWArrayInfo* array_inf_list);

/**
 * @brief Retrieves a specific value from an array's index for a specified channel.
 *
 * This function retrieves the value at a specified index from an array associated
 * with a channel. The array is identified by `array_info_index`, and the exact value
 * is located using `array_value_index`. The retrieved value is copied into the provided
 * `value` buffer, ensuring it does not exceed the allocated size.
 *
 * @param[in]  ch_index          The index of the channel associated with the array.
 * @param[in]  array_info_index  The index of the array information entry from which to retrieve the value.
 * @param[in]  array_value_index The index within the array to retrieve the value.
 * @param[out] value             A pointer to a char buffer where the retrieved value will be stored.
 *                               This buffer must be pre-allocated.
 * @param[in]  value_size        The size of the `value` buffer, indicating the maximum number of characters
 *                               (including null-terminator) that can be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetArrayIndexValue instead.
 */
DWLIB_API enum DWStatus DWGetArrayIndexValue(int ch_index, int array_info_index, int array_value_index, char* value, int value_size);

/**
 * @brief Retrieves a specific value from an array's index using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel associated with the array.
 * @param[in] array_info_index The index of the array information entry.
 * @param[in] array_value_index The index within the array to retrieve the value.
 * @param[out] value A pointer to a char buffer to store the retrieved value.
 * @param[in] value_size The size of the value buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetArrayIndexValue(READER_HANDLE reader, int ch_index, int array_info_index, int array_value_index, char* value, int value_size);

/**
 * @brief Retrieves information about a specific channel from the channel list.
 *
 * This function provides detailed information about a channel identified by `array_index`.
 * The channel's properties such as index, name, unit, description, color, and array size
 * are populated into the provided parameters.
 *
 * @param[in]  array_index  The index of the channel in the channel list to retrieve information for.
 * @param[out] index        A pointer to an integer where the channel's unique identifier will be stored.
 * @param[out] name         A pointer to a char buffer where the channel's name will be stored.
 *                          This buffer must be pre-allocated and have enough space to store the name,
 *                          including null-terminator.
 * @param[out] unit         A pointer to a char buffer where the channel's unit will be stored.
 *                          This buffer must be pre-allocated and have enough space to store the unit,
 *                          including null-terminator.
 * @param[out] description  A pointer to a char buffer where the channel's description will be stored.
 *                          This buffer must be pre-allocated and have enough space to store the description,
 *                          including null-terminator.
 * @param[out] color        A pointer to an integer where the channel's color will be stored.
 * @param[out] array_size   A pointer to an integer where the channel's array size will be stored.
 * @param[in]  max_char_size The maximum size of the char buffers for `name`, `unit`, and `description`,
 *                           including the null-terminator.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetChannelListItem instead.
 */
DWLIB_API enum DWStatus DWGetChannelListItem(int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size);

/**
 * @brief Retrieves information about a specific channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] array_index The index of the channel in the list.
 * @param[out] index Pointer to store the channel's unique identifier.
 * @param[out] name Buffer to store the channel's name.
 * @param[out] unit Buffer to store the channel's unit.
 * @param[out] description Buffer to store the channel's description.
 * @param[out] color Pointer to store the channel's color.
 * @param[out] array_size Pointer to store the channel's array size.
 * @param[in] max_char_size Maximum size for the string buffers.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetChannelListItem(READER_HANDLE reader, int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size);

/**
 * @brief Retrieves information about a specific complex channel from the channel list.
 *
 * This function provides detailed information about a complex channel identified by `array_index`.
 * Complex channels typically involve data with both real and imaginary components, and this function
 * retrieves properties such as index, name, unit, description, color, and array size.
 *
 * @param[in]  array_index  The index of the complex channel in the channel list to retrieve information for.
 * @param[out] index        A pointer to an integer where the channel's unique identifier will be stored.
 * @param[out] name         A pointer to a char buffer where the channel's name will be stored.
 *                          This buffer must be pre-allocated and be large enough to include the null-terminator.
 * @param[out] unit         A pointer to a char buffer where the channel's unit will be stored.
 *                          This buffer must be pre-allocated and include space for the null-terminator.
 * @param[out] description  A pointer to a char buffer where the channel's description will be stored.
 *                          This buffer must be pre-allocated and have space for the null-terminator.
 * @param[out] color        A pointer to an integer where the channel's display color will be stored.
 * @param[out] array_size   A pointer to an integer where the channel's array size will be stored.
 * @param[in]  max_char_size The maximum allowable size for char buffers `name`, `unit`, and `description`,
 *                           including the null-terminator.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetComplexChannelListItem instead.
 */
DWLIB_API enum DWStatus DWGetComplexChannelListItem(int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size);

/**
 * @brief Retrieves information about a specific complex channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] array_index The index of the complex channel in the list.
 * @param[out] index Pointer to store the channel's identifier.
 * @param[out] name Buffer to store the channel's name.
 * @param[out] unit Buffer to store the channel's unit.
 * @param[out] description Buffer to store the channel's description.
 * @param[out] color Pointer to store the channel's color.
 * @param[out] array_size Pointer to store the channel's array size.
 * @param[in] max_char_size Maximum size for the string buffers.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetComplexChannelListItem(READER_HANDLE reader, int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size);

/**
 * @brief Retrieves information about a specific header entry from the header list.
 *
 * This function retrieves detailed information about a header entry identified by `array_index`.
 * Header entries typically contain metadata such as names, units, descriptions, and possibly display attributes.
 *
 * @param[in]  array_index  The index of the header entry in the header list to retrieve information for.
 * @param[out] index        A pointer to an integer where the header entry's identifier will be stored.
 * @param[out] name         A pointer to a char buffer where the header entry's name will be stored.
 *                          This buffer must be pre-allocated and sized to accommodate the name, including the null-terminator.
 * @param[out] unit         A pointer to a char buffer where the header entry's unit will be stored.
 *                          This buffer must be pre-allocated and accommodate the unit, including the null-terminator.
 * @param[out] description  A pointer to a char buffer where the header entry's description will be stored.
 *                          This buffer must be pre-allocated and accommodate the description, including the null-terminator.
 * @param[out] color        A pointer to an integer where the header entry's color (if applicable) will be stored.
 * @param[out] array_size   A pointer to an integer where the header entry's array size will be stored, if applicable.
 * @param[in]  max_char_size The maximum size for the char buffers `name`, `unit`, and `description`, including the null-terminator.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetHeaderEntryListItem instead.
 */
DWLIB_API enum DWStatus DWGetHeaderEntryListItem(int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size);

/**
 * @brief Retrieves information about a specific header entry using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] array_index The index of the header entry in the list.
 * @param[out] index Pointer to store the entry's identifier.
 * @param[out] name Buffer to store the entry's name.
 * @param[out] unit Buffer to store the entry's unit.
 * @param[out] description Buffer to store the entry's description.
 * @param[out] color Pointer to store the entry's color.
 * @param[out] array_size Pointer to store the entry's array size.
 * @param[in] max_char_size Maximum size for the string buffers.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetHeaderEntryListItem(READER_HANDLE reader, int array_index, int* index, char* name, char* unit, char* description, int* color, int* array_size, int max_char_size);

/**
 * @brief Retrieves information about a specific event from the event list.
 *
 * This function extracts detailed information about an event identified by `event_Index`.
 * The function provides details such as event type, timestamp, and associated text description.
 *
 * @param[in]  event_Index  The index of the event in the event list to retrieve details for.
 * @param[out] event_type   A pointer to an integer where the type of the event will be stored.
 *                          Event types typically correspond to predefined constants (e.g., start, stop).
 * @param[out] time_stamp   A pointer to a double where the timestamp of the event will be stored,
 *                          representing the time relative to the start of data recording.
 * @param[out] event_text   A pointer to a char buffer where the event's text description will be stored.
 *                          This buffer must be pre-allocated and should be large enough to store the text,
 *                          including the null-terminator.
 * @param[in]  max_char_size The maximum size of the `event_text` buffer, including the null-terminator,
 *                           to prevent buffer overflow.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetEventListItem instead.
 */
DWLIB_API enum DWStatus DWGetEventListItem(int event_Index, int* event_type, double* time_stamp, char* event_text, int max_char_size);

/**
 * @brief Retrieves information about a specific event using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] event_Index The index of the event in the event list.
 * @param[out] event_type Pointer to store the event type.
 * @param[out] time_stamp Pointer to store the event timestamp.
 * @param[out] event_text Buffer to store the event's text description.
 * @param[in] max_char_size Maximum size of the event_text buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetEventListItem(READER_HANDLE reader, int event_Index, int* event_type, double* time_stamp, char* event_text, int max_char_size);

/**
 * @brief Retrieves a series of average reduced values and their timestamps for a specified channel.
 *
 * This function fetches a specified number of average reduced values, starting from a given position,
 * for the channel identified by `ch_index`. The average values are stored in the provided `data` array,
 * while the corresponding timestamps are stored in the `time_stamp` array.
 *
 * @param[in]  ch_index   The index of the channel from which to retrieve average reduced values.
 * @param[in]  position   The starting position within the channel's reduced data to begin retrieval.
 * @param[in]  count      The number of average reduced values to retrieve.
 * @param[out] data       A pointer to an array where the retrieved average values will be stored.
 *                        This array must be pre-allocated to hold at least `count` values.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *                        This array must also be pre-allocated and match the size of the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedAveValues instead.
 */
DWLIB_API enum DWStatus DWGetReducedAveValues(int ch_index, int position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves average reduced values and timestamps using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel.
 * @param[in] position The starting position for retrieval.
 * @param[in] count The number of values to retrieve.
 * @param[out] data Array to store the average values.
 * @param[out] time_stamp Array to store the timestamps.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedAveValues(READER_HANDLE reader, int ch_index, int position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves a series of minimum reduced values and their timestamps for a specified channel.
 *
 * This function fetches a specified number of minimum reduced values, starting from a given position,
 * for the channel identified by `ch_index`. The minimum values are stored in the provided `data` array,
 * while the corresponding timestamps are stored in the `time_stamp` array.
 *
 * @param[in]  ch_index   The index of the channel from which to retrieve minimum reduced values.
 * @param[in]  position   The starting position within the channel's reduced data to begin retrieval.
 * @param[in]  count      The number of minimum reduced values to retrieve.
 * @param[out] data       A pointer to an array where the retrieved minimum values will be stored.
 *                        This array must be pre-allocated to hold at least `count` values.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *                        This array must also be pre-allocated and match the size of the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedMinValues instead.
 */
DWLIB_API enum DWStatus DWGetReducedMinValues(int ch_index, int position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves minimum reduced values and timestamps using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel.
 * @param[in] position The starting position for retrieval.
 * @param[in] count The number of values to retrieve.
 * @param[out] data Array to store the minimum values.
 * @param[out] time_stamp Array to store the timestamps.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedMinValues(READER_HANDLE reader, int ch_index, int position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves a series of maximum reduced values and their timestamps for a specified channel.
 *
 * This function fetches a specified number of maximum reduced values, starting from a given position,
 * for the channel identified by `ch_index`. The maximum values are stored in the provided `data` array,
 * while the corresponding timestamps are stored in the `time_stamp` array.
 *
 * @param[in]  ch_index   The index of the channel from which to retrieve maximum reduced values.
 * @param[in]  position   The starting position within the channel's reduced data to begin retrieval.
 * @param[in]  count      The number of maximum reduced values to retrieve.
 * @param[out] data       A pointer to an array where the retrieved maximum values will be stored.
 *                        This array must be pre-allocated to hold at least `count` values.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *                        This array must also be pre-allocated and match the size of the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedMaxValues instead.
 */
DWLIB_API enum DWStatus DWGetReducedMaxValues(int ch_index, int position, int count, double* data, double* time_stamp);

DWLIB_API enum DWStatus DWIGetReducedMaxValues(READER_HANDLE reader, int ch_index, int position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves a series of RMS reduced values and their timestamps for a specified channel.
 *
 * This function fetches a specified number of RMS reduced values, starting from a given position,
 * for the channel identified by `ch_index`. The RMS values are stored in the provided `data` array,
 * while the corresponding timestamps are stored in the `time_stamp` array.
 *
 * @param[in]  ch_index   The index of the channel from which to retrieve RMS reduced values.
 * @param[in]  position   The starting position within the channel's reduced data to begin retrieval.
 * @param[in]  count      The number of RMS reduced values to retrieve.
 * @param[out] data       A pointer to an array where the retrieved RMS values will be stored.
 *                        This array must be pre-allocated to hold at least `count` values.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *                        This array must also be pre-allocated and match the size of the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedRMSValues instead.
 */
DWLIB_API enum DWStatus DWGetReducedRMSValues(int ch_index, int position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves RMS reduced values and timestamps using a specific reader instance.
 *
 * This function fetches RMS reduced values using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve RMS values.
 * @param[in] position The starting position for retrieval.
 * @param[in] count The number of values to retrieve.
 * @param[out] data Array to store the RMS values.
 * @param[out] time_stamp Array to store the timestamps.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedRMSValues(READER_HANDLE reader, int ch_index, int position, int count, double* data, double* time_stamp);

/**
 * @brief Retrieves the number of available binary channels.
 *
 * This function returns the total number of binary channels currently available in the system.
 * Binary channels typically handle raw binary data or structured binary formats.
 *
 * @return The number of binary channels available.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetBinChannelListCount instead.
 */
DWLIB_API int DWGetBinChannelListCount();

/**
 * @brief Retrieves the number of available binary channels using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] count Pointer to an integer where the binary channel count will be stored.
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetBinChannelListCount(READER_HANDLE reader, int* count);

/**
 * @brief Retrieves the count of samples available for a specified binary channel.
 *
 * This function returns the total number of binary samples currently available for
 * the given channel index. Binary samples contain structured binary data that may
 * represent complex information or formatting.
 *
 * @param[in] ch_index The index of the binary channel for which to retrieve the sample count.
 *
 * @return The number of binary samples available for the specified channel.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetBinarySamplesCount instead.
 */
DWLIB_API __int64 DWGetBinarySamplesCount(int ch_index);

/**
 * @brief Retrieves the count of samples available for a specified binary channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the binary channel to query.
 * @param[out] count Pointer to an __int64 where the binary sample count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetBinarySamplesCount(READER_HANDLE reader, int ch_index, __int64* count);

/**
 * @brief Retrieves a single binary sample and its timestamp for a specified channel.
 *
 * This function fetches a binary sample at the specified sampleIndex for the channel
 * identified by `ch_index`. The binary data is stored in the provided `data` buffer,
 * and the timestamp is stored in the `time_stamp` parameter.
 *
 * @param[in]  ch_index    The index of the channel from which to retrieve the binary sample.
 * @param[in]  sampleIndex The index of the sample to retrieve.
 * @param[out] data        A pointer to a buffer where the binary data will be stored.
 *                         This buffer must be pre-allocated.
 * @param[out] time_stamp  A pointer to a double where the timestamp of the sample will be stored.
 * @param[out] datalen     A pointer to an integer where the length of the retrieved binary data will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetBinarySamples instead.
 */
DWLIB_API enum DWStatus DWGetBinarySamples(int ch_index, __int64 sampleIndex, char* data, double* time_stamp, int* datalen);

/**
 * @brief Retrieves a single binary sample and its timestamp using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve the binary sample.
 * @param[in] sampleIndex The index of the sample to retrieve.
 * @param[out] data A pointer to a buffer where the binary data will be stored.
 * @param[out] time_stamp A pointer to a double where the timestamp will be stored.
 * @param[out] datalen A pointer to an integer where the data length will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetBinarySamples(READER_HANDLE reader, int ch_index, __int64 sampleIndex, char* data, double* time_stamp, int* datalen);

/**
 * @brief Retrieves multiple binary samples and their timestamps for a specified channel.
 *
 * This function fetches a specified number of binary samples starting from a given position
 * for the channel identified by `ch_index`. The binary data is stored in the provided
 * `data` buffer, and the timestamps are stored in the `time_stamp` array.
 *
 * @param[in]  ch_index    The index of the channel from which to retrieve binary samples.
 * @param[in]  position    The starting position within the channel's data to begin retrieval.
 * @param[in]  count       The number of binary samples to retrieve.
 * @param[out] data        A pointer to a buffer where the binary data will be stored.
 *                         This buffer must be pre-allocated.
 * @param[out] time_stamp  A pointer to an array where the timestamps will be stored.
 *                         This array must be pre-allocated to hold at least `count` timestamps.
 * @param[out] datalen     A pointer to an integer where the total length of all retrieved binary data will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetBinarySamplesEx instead.
 */
DWLIB_API enum DWStatus DWGetBinarySamplesEx(int ch_index, __int64 position, int count, char* data, double* time_stamp, int* datalen);

/**
 * @brief Retrieves multiple binary samples and their timestamps using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve the binary samples.
 * @param[in] position The starting position within the channel's data.
 * @param[in] count The number of samples to retrieve.
 * @param[out] data A pointer to a buffer where the binary data will be stored.
 * @param[out] time_stamp A pointer to an array where the timestamps will be stored.
 * @param[out] datalen A pointer to an integer where the total data length will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetBinarySamplesEx(READER_HANDLE reader, int ch_index, __int64 position, int count, char* data, double* time_stamp, int* datalen);

/**
 * @brief Retrieves binary record samples and their timestamps for a specified channel.
 *
 * This function fetches a specified number of binary record samples starting from the given
 * sampleIndex for the channel identified by `ch_index`. The records are stored in the
 * provided `data` buffer, and the timestamps are stored in the `time_stamp` array.
 *
 * @param[in]  ch_index    The index of the channel from which to retrieve the binary record samples.
 * @param[in]  sampleIndex The starting sample index to begin retrieval.
 * @param[in]  count       The number of record samples to retrieve.
 * @param[out] data        A pointer to a buffer where the binary record data will be stored.
 *                         This buffer must be pre-allocated.
 * @param[out] time_stamp  A pointer to an array where the timestamps will be stored.
 *                         This array must be pre-allocated to hold at least `count` timestamps.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetBinRecSamples instead.
 */
DWLIB_API enum DWStatus DWGetBinRecSamples(int ch_index, __int64 sampleIndex, int count, char* data, double* time_stamp);

/**
 * @brief Retrieves binary record samples and their timestamps using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve the binary records.
 * @param[in] sampleIndex The starting sample index.
 * @param[in] count The number of record samples to retrieve.
 * @param[out] data A pointer to an array of DWBinarySample structures to store the binary records.
 * @param[out] time_stamp A pointer to an array where the timestamps will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetBinRecSamples(READER_HANDLE reader, int ch_index, __int64 sampleIndex, int count, struct DWBinarySample* data, double* time_stamp);

/**
 * @brief Retrieves binary data for a specified channel and sample.
 *
 * This function retrieves the binary data associated with a specific sample in the
 * channel identified by `ch_index`. The data is stored in the provided `data` buffer,
 * and the absolute position is updated in the `absPos` parameter.
 *
 * @param[in]  ch_index    The index of the channel from which to retrieve binary data.
 * @param[in]  sample      A pointer to a sample descriptor that identifies the target sample.
 * @param[out] data        A pointer to a buffer where the binary data will be stored.
 *                         This buffer must be pre-allocated.
 * @param[in,out] absPos   A pointer to an __int64 that will be updated with the absolute position of the data.
 * @param[in]  binBufSize  The size of the `data` buffer in bytes.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetBinData instead.
 */
DWLIB_API enum DWStatus DWGetBinData(int ch_index, char* sample, char* data, __int64* absPos, int binBufSize);

/**
 * @brief Retrieves binary data for a specified channel and sample using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve binary data.
 * @param[in] sample A pointer to a DWBinarySample structure that identifies the target sample.
 * @param[out] data A pointer to a buffer where the binary data will be stored.
 * @param[in,out] absPos A pointer to an __int64 that will be updated with the absolute position.
 * @param[in] binBufSize The size of the data buffer in bytes.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetBinData(READER_HANDLE reader, int ch_index, struct DWBinarySample* sample, char* data, __int64* absPos, int binBufSize);

/**
 * @brief Retrieves the count of raw samples available for a specified channel.
 *
 * This function returns the total number of raw samples currently available for
 * the given channel index. Raw samples contain unprocessed data directly from the
 * data acquisition device.
 *
 * @param[in] ch_index The index of the channel for which to retrieve the raw sample count.
 *
 * @return The number of raw samples available for the specified channel.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetRawSamplesCount instead.
 */
DWLIB_API __int64 DWGetRawSamplesCount(int ch_index);

/**
 * @brief Retrieves the count of raw samples using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel to query.
 * @param[out] count Pointer to an __int64 where the raw sample count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetRawSamplesCount(READER_HANDLE reader, int ch_index, __int64* count);

/**
 * @brief Retrieves a series of raw samples and their timestamps for a specified channel.
 *
 * This function fetches a specified number of raw samples starting from a given position
 * for the channel identified by `ch_index`. The retrieved samples are stored in the provided
 * data array along with their corresponding timestamps in the time_stamp array.
 *
 * @param[in]  ch_index   The index of the channel from which to retrieve raw samples.
 * @param[in]  position   The starting position within the channel's data to begin retrieval.
 * @param[in]  count      The number of samples to retrieve.
 * @param[out] data       A pointer to a buffer where the retrieved sample values will be stored.
 *                        This buffer must be pre-allocated to hold at least `count` samples.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *                        This array must also be pre-allocated and match the size of the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetRawSamples instead.
 */
DWLIB_API enum DWStatus DWGetRawSamples(int ch_index, __int64 position, int count, void* data, double* time_stamp);

/**
 * @brief Retrieves a series of raw samples and timestamps using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel from which to retrieve raw samples.
 * @param[in] position The starting position within the channel's data.
 * @param[in] count The number of samples to retrieve.
 * @param[out] data A pointer to a buffer where the sample values will be stored.
 * @param[out] time_stamp A pointer to an array where the timestamps will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetRawSamples(READER_HANDLE reader, int ch_index, __int64 position, int count, void* data, double* time_stamp);

/**
 * @brief Retrieves the count of complex raw samples available for a specified channel.
 *
 * This function returns the total number of complex raw samples currently available for
 * the given channel index. Complex raw samples contain unprocessed data with both real
 * and imaginary components.
 *
 * @param[in] ch_index The index of the channel for which to retrieve the complex raw sample count.
 *
 * @return The number of complex raw samples available for the specified channel.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetComplexRawSamplesCount instead.
 */
DWLIB_API __int64 DWGetComplexRawSamplesCount(int ch_index);

/**
 * @brief Retrieves the count of complex raw samples using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel to query.
 * @param[out] count Pointer to an __int64 where the complex raw sample count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetComplexRawSamplesCount(READER_HANDLE reader, int ch_index, __int64* count);

/**
 * @brief Retrieves a series of complex raw samples and their timestamps for a specified channel.
 *
 * This function fetches a specified number of complex raw samples starting from a given position
 * for the channel identified by `ch_index`. The retrieved samples, each with real and imaginary
 * components, are stored in the provided `data` array along with their corresponding timestamps.
 *
 * @param[in]  ch_index   The index of the complex channel from which to retrieve raw samples.
 * @param[in]  position   The starting position within the channel's data to begin retrieval.
 * @param[in]  count      The number of complex samples to retrieve.
 * @param[out] data       A pointer to an array of `DWComplex` structures where the retrieved sample
 *                        values will be stored. This array must be pre-allocated to hold at least `count` samples.
 * @param[out] time_stamp A pointer to an array where the corresponding timestamps will be stored.
 *                        This array must also be pre-allocated and match the size of the `data` array.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetComplexRawSamples instead.
 */
DWLIB_API enum DWStatus DWGetComplexRawSamples(int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp);

/**
 * @brief Retrieves complex raw samples and timestamps using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the complex channel to retrieve samples from.
 * @param[in] position The starting position within the channel's data.
 * @param[in] count The number of complex samples to retrieve.
 * @param[out] data A pointer to an array of DWComplex structures for the sample values.
 * @param[out] time_stamp A pointer to an array where the timestamps will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetComplexRawSamples(READER_HANDLE reader, int ch_index, __int64 position, int count, struct DWComplex* data, double* time_stamp);

/**
 * @brief Retrieves a stream by name.
 *
 * This function retrieves a stream of data identified by `stream_name`. The stream data
 * is copied into the provided `buffer`, and the length of the data is updated in the
 * `max_len` parameter.
 *
 * @param[in]  stream_name The name of the stream to retrieve.
 * @param[out] buffer      A pointer to a buffer where the stream data will be stored.
 *                         This buffer must be pre-allocated.
 * @param[in,out] max_len  A pointer to an integer that, on input, indicates the maximum length of the buffer.
 *                         On output, it contains the actual length of the retrieved stream data.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetStream instead.
 */
DWLIB_API enum DWStatus DWGetStream(char* stream_name, char* buffer, int* max_len);

/**
 * @brief Retrieves a stream by name using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] stream_name The name of the stream to retrieve.
 * @param[out] buffer A pointer to a buffer where the stream data will be stored.
 * @param[in,out] max_len A pointer to an integer for the buffer's max length/actual length.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetStream(READER_HANDLE reader, char* stream_name, char* buffer, int* max_len);

/**
 * @brief Retrieves a block of reduced values for multiple channels.
 *
 * This function fetches a specified number of reduced values for multiple channels
 * identified by the array of channel IDs. The data is stored in the provided `data` array.
 *
 * @param[in]  ch_ids    A pointer to an array of channel IDs for which to retrieve reduced values.
 * @param[in]  ch_count  The number of channels in the `ch_ids` array.
 * @param[in]  position  The starting position within the channels' reduced data to begin retrieval.
 * @param[in]  count     The number of reduced values to retrieve for each channel.
 * @param[in]  ib_level  The interpolation block level to use.
 * @param[out] data      A pointer to an array of `DWReducedValue` structures where the retrieved values
 *                       will be stored. This array must be pre-allocated to hold at least `ch_count * count` elements.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedValuesBlock instead.
 */
DWLIB_API enum DWStatus DWGetReducedValuesBlock(int* ch_ids, int ch_count, int position, int count, int ib_level, struct DWReducedValue* data);

/**
 * @brief Retrieves a block of reduced values for multiple channels using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_ids A pointer to an array of channel IDs to retrieve values for.
 * @param[in] ch_count The number of channels in the ch_ids array.
 * @param[in] position The starting position within the reduced data.
 * @param[in] count The number of reduced values to retrieve per channel.
 * @param[in] ib_level The interpolation block level.
 * @param[out] data A pointer to an array of DWReducedValue structures for the values.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedValuesBlock(READER_HANDLE reader, int* ch_ids, int ch_count, int position, int count, int ib_level, struct DWReducedValue* data);

/**
 * @brief Retrieves a numeric value from an array's index for a specified channel.
 *
 * This function retrieves a double-precision floating-point value at a specified index
 * from an array associated with a channel. The array is identified by `array_info_index`,
 * and the exact value is located using `array_value_index`.
 *
 * @param[in]  ch_index          The index of the channel associated with the array.
 * @param[in]  array_info_index  The index of the array information entry from which to retrieve the value.
 * @param[in]  array_value_index The index within the array to retrieve the value.
 * @param[out] value             A pointer to a double where the retrieved value will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetArrayIndexValueF instead.
 */
DWLIB_API enum DWStatus DWGetArrayIndexValueF(int ch_index, int array_info_index, int array_value_index, double* value);

/**
 * @brief Retrieves a numeric value from an array's index using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel associated with the array.
 * @param[in] array_info_index The index of the array information entry.
 * @param[in] array_value_index The index within the array for the value.
 * @param[out] value A pointer to a double where the retrieved value will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetArrayIndexValueF(READER_HANDLE reader, int ch_index, int array_info_index, int array_value_index, double* value);

/**
 * @brief Retrieves the type of a specific event by event number.
 *
 * This function returns the event type value associated with a particular event identified
 * by `event_number`. The event type indicates the category or nature of the event.
 *
 * @param[in] event_number The number of the event for which the type is to be retrieved.
 *
 * @return An integer value representing the event type.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetEventTypeF instead.
 */
DWLIB_API int DWGetEventTypeF(int event_number);

/**
 * @brief Retrieves the type of a specific event using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] event_number The number of the event to query.
 * @param[out] event_type Pointer to an enum DWEventType where the event type will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetEventTypeF(READER_HANDLE reader, int event_number, enum DWEventType* event_type);

/**
 * @brief Retrieves Y-axis reduced data for a specified channel.
 *
 * This function fetches a series of Y-axis reduced data points for a channel identified
 * by `Channel_Number`. The data is retrieved starting at a specified position and fills
 * the provided Y_Axis array with the retrieved values.
 *
 * @param[in]  Channel_Number The number of the channel from which to retrieve data.
 * @param[out] Y_Axis         A pointer to an array where the Y-axis values will be stored.
 *                            This array must be pre-allocated to hold at least `count` values.
 * @param[in]  position       The starting position within the channel's data from which to begin retrieval.
 * @param[in]  count          The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetRecudedYDataF instead.
 */
DWLIB_API enum DWStatus DWGetRecudedYDataF(int Channel_Number, double* Y_Axis, int position, int count);

/**
 * @brief Retrieves Y-axis reduced data using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Channel_Number The channel number to retrieve data from.
 * @param[out] Y_Axis A pointer to an array where the Y-axis values will be stored.
 * @param[in] position The starting position for data retrieval.
 * @param[in] count The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetRecudedYDataF(READER_HANDLE reader, int Channel_Number, double* Y_Axis, int position, int count);

/**
 * @brief Retrieves all reduced data types (MIN, AVE, MAX, RMS) for a specified channel.
 *
 * This function fetches a series of reduced data points for a channel identified by
 * `Channel_Number`, including minimum, average, maximum, and RMS values. The data is
 * retrieved starting at a specified position and fills the provided arrays.
 *
 * @param[in]  Channel_Number The number of the channel from which to retrieve data.
 * @param[out] Y_MIN_Axis     A pointer to an array where the minimum values will be stored.
 *                            This array must be pre-allocated to hold at least `count` values.
 * @param[out] Y_AVE_Axis     A pointer to an array where the average values will be stored.
 *                            This array must be pre-allocated to hold at least `count` values.
 * @param[out] Y_MAX_Axis     A pointer to an array where the maximum values will be stored.
 *                            This array must be pre-allocated to hold at least `count` values.
 * @param[out] Y_RMS_Axis     A pointer to an array where the RMS values will be stored.
 *                            This array must be pre-allocated to hold at least `count` values.
 * @param[in]  position       The starting position within the channel's data from which to begin retrieval.
 * @param[in]  count          The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetRecudedDataAllF instead.
 */
DWLIB_API enum DWStatus DWGetRecudedDataAllF(int Channel_Number, double* Y_MIN_Axis, double* Y_AVE_Axis, double* Y_MAX_Axis, double* Y_RMS_Axis, int position, int count);

/**
 * @brief Retrieves all reduced data types using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Channel_Number The channel number to retrieve data from.
 * @param[out] Y_MIN_Axis A pointer to an array for the minimum values.
 * @param[out] Y_AVE_Axis A pointer to an array for the average values.
 * @param[out] Y_MAX_Axis A pointer to an array for the maximum values.
 * @param[out] Y_RMS_Axis A pointer to an array for the RMS values.
 * @param[in] position The starting position for data retrieval.
 * @param[in] count The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetRecudedDataAllF(READER_HANDLE reader, int Channel_Number, double* Y_MIN_Axis, double* Y_AVE_Axis, double* Y_MAX_Axis, double* Y_RMS_Axis, int position, int count);

/**
 * @brief Retrieves a list of available binary channels.
 *
 * This function populates an array of DWChannel structures with information about
 * the available binary channels. Binary channels typically handle structured binary data
 * or binary formats like video, images, or specialized data streams.
 *
 * @param[out] channel_list A pointer to an array of DWChannel structures to be filled
 *                          with binary channel information. The array must be pre-allocated with
 *                          sufficient size to hold the data.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetBinChannelList instead.
 */
DWLIB_API enum DWStatus DWGetBinChannelList(struct DWChannel* channel_list);

/**
 * @brief Retrieves a list of available binary channels using a specific reader instance.
 *
 * This function populates an array of DWChannel structures with information about
 * the available binary channels using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] channel_list A pointer to an array of DWChannel structures to be filled
 *                          with binary channel information. The array must be pre-allocated.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetBinChannelList(READER_HANDLE reader, struct DWChannel* channel_list);

/**
 * @brief Retrieves a specific property of a channel.
 *
 * This function fetches a specific property identified by `ch_prop` for the channel
 * identified by `ch_index`. The property value is stored in the provided buffer.
 *
 * @param[in] ch_index The index of the channel for which to retrieve the property.
 * @param[in] ch_prop The channel property to retrieve, specified as a DWChannelProps enum value.
 * @param[out] buffer A pointer to a buffer where the property value will be stored.
 *                    This buffer must be pre-allocated and of appropriate type for the property.
 * @param[in,out] max_len A pointer to an integer that, on input, indicates the maximum size of the buffer.
 *                        On output, it contains the actual size of the retrieved property data.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetChannelProps instead.
 */
DWLIB_API enum DWStatus DWGetChannelProps(int ch_index, enum DWChannelProps ch_prop, void* buffer, int* max_len);

/**
 * @brief Retrieves a specific property of a channel using a specific reader instance.
 *
 * This function fetches a specific property for a channel using the specified reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] ch_index The index of the channel for which to retrieve the property.
 * @param[in] ch_prop The channel property to retrieve, specified as a DWChannelProps enum value.
 * @param[out] buffer A pointer to a buffer where the property value will be stored.
 * @param[in,out] max_len A pointer to an integer for the buffer's max/actual size.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetChannelProps(READER_HANDLE reader, int ch_index, enum DWChannelProps ch_prop, void* buffer, int* max_len);

/**
 * @brief Retrieves the text value of a header entry by its entry number.
 *
 * This function fetches the text value for a header entry identified by `entry_number`.
 * The text is copied into the provided buffer, ensuring it does not exceed the allocated size.
 *
 * @param[in] entry_number The number of the header entry to retrieve.
 * @param[out] text_value A pointer to a char buffer where the text value will be stored.
 *                        This buffer must be pre-allocated.
 * @param[in] text_value_size The size of the `text_value` buffer, indicating the maximum number
 *                           of characters (including null-terminator) that can be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetHeaderEntryTextF instead.
 */
DWLIB_API enum DWStatus DWGetHeaderEntryTextF(int entry_number, char* text_value, int text_value_size);

/**
 * @brief Retrieves the text value of a header entry using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] entry_number The number of the header entry to retrieve.
 * @param[out] text_value A pointer to a char buffer for the text value.
 * @param[in] text_value_size The maximum size of the text_value buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetHeaderEntryTextF(READER_HANDLE reader, int entry_number, char* text_value, int text_value_size);

/**
 * @brief Retrieves the name of a header entry by its entry number.
 *
 * This function fetches the name of a header entry identified by `entry_number`.
 * The name is copied into the provided buffer, ensuring it does not exceed the allocated size.
 *
 * @param[in] entry_number The number of the header entry for which to retrieve the name.
 * @param[out] name A pointer to a char buffer where the entry name will be stored.
 *                  This buffer must be pre-allocated.
 * @param[in] name_size The size of the `name` buffer, indicating the maximum number
 *                      of characters (including null-terminator) that can be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetHeaderEntryNameF instead.
 */
DWLIB_API enum DWStatus DWGetHeaderEntryNameF(int entry_number, char* name, int name_size);

/**
 * @brief Retrieves the name of a header entry using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] entry_number The number of the header entry.
 * @param[out] name A pointer to a char buffer for the entry name.
 * @param[in] name_size The maximum size of the name buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetHeaderEntryNameF(READER_HANDLE reader, int entry_number, char* name, int name_size);

/**
 * @brief Retrieves the identifier (ID) of a header entry by its entry number.
 *
 * This function fetches the ID of a header entry identified by `entry_number`.
 * The ID is copied into the provided buffer, ensuring it does not exceed the allocated size.
 *
 * @param[in] entry_number The number of the header entry for which to retrieve the ID.
 * @param[out] ID A pointer to a char buffer where the entry ID will be stored.
 *                This buffer must be pre-allocated.
 * @param[in] name_size The size of the `ID` buffer, indicating the maximum number
 *                      of characters (including null-terminator) that can be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetHeaderEntryIDF instead.
 */
DWLIB_API enum DWStatus DWGetHeaderEntryIDF(int entry_number, char* ID, int name_size);

/**
 * @brief Retrieves the identifier (ID) of a header entry using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] entry_number The number of the header entry.
 * @param[out] ID A pointer to a char buffer for the entry ID.
 * @param[in] name_size The maximum size of the ID buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetHeaderEntryIDF(READER_HANDLE reader, int entry_number, char* ID, int name_size);

/**
 * @brief Retrieves the timestamp of a specific event by event number.
 *
 * This function returns the timestamp associated with a particular event identified
 * by `event_number`. The timestamp represents the time at which the event occurred,
 * relative to the start of data recording.
 *
 * @param[in] event_number The number of the event for which to retrieve the timestamp.
 *
 * @return A double-precision floating-point value representing the event timestamp in seconds.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetEventTimeF instead.
 */
DWLIB_API double DWGetEventTimeF(int event_number);

/**
 * @brief Retrieves the timestamp of a specific event using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] event_number The number of the event to query.
 * @param[out] time_stamp Pointer to a double where the event timestamp will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetEventTimeF(READER_HANDLE reader, int event_number, double* time_stamp);

/**
 * @brief Retrieves the text description of a specific event by event number.
 *
 * This function fetches the descriptive text associated with an event identified by `event_number`.
 * The text is copied into the provided buffer, ensuring it does not exceed the allocated size.
 *
 * @param[in] event_number The number of the event for which to retrieve the text description.
 * @param[out] text A pointer to a char buffer where the event text will be stored.
 *                  This buffer must be pre-allocated.
 * @param[in] text_size The size of the `text` buffer, indicating the maximum number
 *                     of characters (including null-terminator) that can be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetEventTextF instead.
 */
DWLIB_API enum DWStatus DWGetEventTextF(int event_number, char* text, int text_size);

/**
 * @brief Retrieves the text description of an event using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] event_number The number of the event to query.
 * @param[out] text A pointer to a char buffer for the event text.
 * @param[in] text_size The maximum size of the text buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetEventTextF(READER_HANDLE reader, int event_number, char* text, int text_size);

/**
 * @brief Retrieves the number of channels available for reduced data.
 *
 * This function returns the total number of channels that have reduced data available.
 * Reduced data channels contain summarized data for visualization and analysis.
 *
 * @return The number of reduced data channels available.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedDataChannelCountF instead.
 */
DWLIB_API int DWGetReducedDataChannelCountF();

/**
 * @brief Retrieves the number of channels available for reduced data using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] count Pointer to an integer where the reduced data channel count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedDataChannelCountF(READER_HANDLE reader, int* count);

/**
 * @brief Retrieves the name of a reduced data channel by its number.
 *
 * This function fetches the name of a reduced data channel identified by `Channel_Number`.
 * The name is copied into the provided buffer, ensuring it does not exceed the allocated size.
 *
 * @param[in] Channel_Number The number of the reduced data channel for which to retrieve the name.
 * @param[out] name A pointer to a char buffer where the channel name will be stored.
 *                  This buffer must be pre-allocated.
 * @param[in] name_size The size of the `name` buffer, indicating the maximum number
 *                      of characters (including null-terminator) that can be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedDataChannelNameF instead.
 */
DWLIB_API enum DWStatus DWGetReducedDataChannelNameF(int Channel_Number, char* name, int name_size);

/**
 * @brief Retrieves the name of a reduced data channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Channel_Number The number of the reduced data channel.
 * @param[out] name A pointer to a char buffer for the channel name.
 * @param[in] name_size The maximum size of the name buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedDataChannelNameF(READER_HANDLE reader, int Channel_Number, char* name, int name_size);

/**
 * @brief Retrieves the index of a reduced data channel by its name.
 *
 * This function searches for a reduced data channel with the specified name
 * and returns its corresponding index. This index can then be used in other
 * functions that accept a channel index parameter.
 *
 * @param[in] name A pointer to a null-terminated string containing the name of the
 *                  reduced data channel to find.
 *
 * @return The index of the reduced data channel if found.
 * @retval -1 if the channel is not found or an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetReducedDataChannelIndexF instead.
 */
DWLIB_API int DWGetReducedDataChannelIndexF(char* name);

/**
 * @brief Retrieves the index of a reduced data channel by its name using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] name A pointer to a null-terminated string with the channel name to find.
 * @param[out] index Pointer to an integer where the channel index will be stored if found.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetReducedDataChannelIndexF(READER_HANDLE reader, char* name, int* index);

/**
 * @brief Retrieves detailed information about a reduced data channel.
 *
 * This function provides information about a reduced data channel identified by `Channel_Number`,
 * including its axis units, offset, length, and sample rate.
 *
 * @param[in] Channel_Number The number of the reduced data channel to query.
 * @param[out] X_Axis_Units A buffer to store the X-axis units. Must be pre-allocated.
 * @param[in] X_Axis_Units_size The size of the X_Axis_Units buffer.
 * @param[out] Y_Axis_Units A buffer to store the Y-axis units. Must be pre-allocated.
 * @param[in] Y_Axis_Units_size The size of the Y_Axis_Units buffer.
 * @param[out] Chn_Offset A pointer to a double where the channel offset will be stored.
 * @param[out] Channel_Length A pointer to an integer where the channel length will be stored.
 * @param[out] ch_rate A pointer to a double where the channel sample rate will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetRecudedDataChannelInfoF instead.
 */
DWLIB_API enum DWStatus DWGetRecudedDataChannelInfoF(int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, int* Channel_Length, double* ch_rate);

/**
 * @brief Retrieves detailed information about a reduced data channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Channel_Number The number of the reduced data channel to query.
 * @param[out] X_Axis_Units A buffer to store the X-axis units.
 * @param[in] X_Axis_Units_size The size of the X_Axis_Units buffer.
 * @param[out] Y_Axis_Units A buffer to store the Y-axis units.
 * @param[in] Y_Axis_Units_size The size of the Y_Axis_Units buffer.
 * @param[out] Chn_Offset A pointer to a double for the channel offset.
 * @param[out] Channel_Length A pointer to an integer for the channel length.
 * @param[out] ch_rate A pointer to a double for the channel sample rate.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetRecudedDataChannelInfoF(READER_HANDLE reader, int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, int* Channel_Length, double* ch_rate);

/**
 * @brief Retrieves X and Y axis data for a reduced data channel.
 *
 * This function fetches both X and Y axis values for a reduced data channel identified by
 * `Channel_Number`. The data is retrieved starting at a specified position and fills
 * the provided X_Axis and Y_Axis arrays.
 *
 * @param[in] Channel_Number The number of the reduced data channel from which to retrieve data.
 * @param[out] X_Axis A pointer to an array where X-axis values will be stored. Must be pre-allocated.
 * @param[out] Y_Axis A pointer to an array where Y-axis values will be stored. Must be pre-allocated.
 * @param[in] position The starting position within the channel's data.
 * @param[in] count The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetRecudedDataF instead.
 */
DWLIB_API enum DWStatus DWGetRecudedDataF(int Channel_Number, double* X_Axis, double* Y_Axis, int position, int count);

/**
 * @brief Retrieves X and Y axis data for a reduced data channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Channel_Number The number of the reduced data channel.
 * @param[out] X_Axis A pointer to an array for X-axis values.
 * @param[out] Y_Axis A pointer to an array for Y-axis values.
 * @param[in] position The starting position within the channel's data.
 * @param[in] count The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetRecudedDataF(READER_HANDLE reader, int Channel_Number, double* X_Axis, double* Y_Axis, int position, int count);

/**
 * @brief Retrieves the number of triggers in the trigger data.
 *
 * This function returns the total number of triggers currently recorded in the data.
 * Triggers typically mark important events or conditions in the recorded data.
 *
 * @return The number of triggers available.
 * @retval -1 if an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetTriggerDataTriggerCountF instead.
 */
DWLIB_API int DWGetTriggerDataTriggerCountF();

/**
 * @brief Retrieves the number of triggers using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[out] count Pointer to an integer where the trigger count will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetTriggerDataTriggerCountF(READER_HANDLE reader, int* count);

/**
 * @brief Retrieves the timestamp of a specific trigger by its number.
 *
 * This function returns the timestamp associated with a trigger identified by `Trigger_Number`.
 * The timestamp represents the time at which the trigger occurred, relative to the start of data recording.
 *
 * @param[in] Trigger_Number The number of the trigger for which to retrieve the timestamp.
 *
 * @return A double-precision floating-point value representing the trigger timestamp in seconds.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetTriggerDataTriggerTimeF instead.
 */
DWLIB_API double DWGetTriggerDataTriggerTimeF(int Trigger_Number);

/**
 * @brief Retrieves the timestamp of a specific trigger using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Trigger_Number The number of the trigger to query.
 * @param[out] time_stamp Pointer to a double where the trigger timestamp will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetTriggerDataTriggerTimeF(READER_HANDLE reader, int Trigger_Number, double* time_stamp);

/**
 * @brief Retrieves the name of a trigger data channel by its number.
 *
 * This function fetches the name of a trigger data channel identified by `Channel_Number`.
 * The name is copied into the provided buffer, ensuring it does not exceed the allocated size.
 *
 * @param[in] Channel_Number The number of the trigger data channel for which to retrieve the name.
 * @param[out] name A pointer to a char buffer where the channel name will be stored.
 *                  This buffer must be pre-allocated.
 * @param[in] name_size The size of the `name` buffer, indicating the maximum number
 *                      of characters (including null-terminator) that can be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetTriggerDataChannelNameF instead.
 */
DWLIB_API enum DWStatus DWGetTriggerDataChannelNameF(int Channel_Number, char* name, int name_size);

/**
 * @brief Retrieves the name of a trigger data channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Channel_Number The number of the trigger data channel.
 * @param[out] name A pointer to a char buffer for the channel name.
 * @param[in] name_size The maximum size of the name buffer.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetTriggerDataChannelNameF(READER_HANDLE reader, int Channel_Number, char* name, int name_size);

/**
 * @brief Retrieves the index of a trigger data channel by its name.
 *
 * This function searches for a trigger data channel with the specified name
 * and returns its corresponding index. This index can then be used in other
 * functions that accept a channel index parameter.
 *
 * @param[in] name A pointer to a null-terminated string containing the name of the
 *                 trigger data channel to find.
 *
 * @return The index of the trigger data channel if found.
 * @retval -1 if the channel is not found or an error occurs.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetTriggerDataChannelIndexF instead.
 */
DWLIB_API int DWGetTriggerDataChannelIndexF(char* name);

/**
 * @brief Retrieves the index of a trigger data channel by its name using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] name A pointer to a null-terminated string with the channel name to find.
 * @param[out] index Pointer to an integer where the channel index will be stored if found.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetTriggerDataChannelIndexF(READER_HANDLE reader, char* name, int* index);

/**
 * @brief Retrieves detailed information about a trigger data channel.
 *
 * This function provides information about a trigger data channel for a specific trigger,
 * including its axis units, offset, length, sample rate, and channel type.
 *
 * @param[in] Trigger_Number The number of the trigger for which to retrieve channel information.
 * @param[in] Channel_Number The number of the channel within the trigger data.
 * @param[out] X_Axis_Units A buffer to store the X-axis units. Must be pre-allocated.
 * @param[in] X_Axis_Units_size The size of the X_Axis_Units buffer.
 * @param[out] Y_Axis_Units A buffer to store the Y-axis units. Must be pre-allocated.
 * @param[in] Y_Axis_Units_size The size of the Y_Axis_Units buffer.
 * @param[out] Chn_Offset A pointer to a double where the channel offset will be stored.
 * @param[out] Channel_Length A pointer to a double where the channel length will be stored.
 * @param[out] ch_rate A pointer to a double where the channel sample rate will be stored.
 * @param[out] ch_type A pointer to an integer where the channel type will be stored.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetTriggerDataChannelInfoF instead.
 */
DWLIB_API enum DWStatus DWGetTriggerDataChannelInfoF(int Trigger_Number, int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, double* Channel_Length, double* ch_rate, int* ch_type);

/**
 * @brief Retrieves detailed information about a trigger data channel using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Trigger_Number The number of the trigger.
 * @param[in] Channel_Number The number of the channel within the trigger data.
 * @param[out] X_Axis_Units A buffer to store the X-axis units.
 * @param[in] X_Axis_Units_size The size of the X_Axis_Units buffer.
 * @param[out] Y_Axis_Units A buffer to store the Y-axis units.
 * @param[in] Y_Axis_Units_size The size of the Y_Axis_Units buffer.
 * @param[out] Chn_Offset A pointer to a double for the channel offset.
 * @param[out] Channel_Length A pointer to a double for the channel length.
 * @param[out] ch_rate A pointer to a double for the channel sample rate.
 * @param[out] ch_type A pointer to an integer for the channel type.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetTriggerDataChannelInfoF(READER_HANDLE reader, int Trigger_Number, int Channel_Number, char* X_Axis_Units, int X_Axis_Units_size, char* Y_Axis_Units, int Y_Axis_Units_size, double* Chn_Offset, double* Channel_Length, double* ch_rate, int* ch_type);

/**
 * @brief Retrieves trigger data for a specific trigger and channel.
 *
 * This function fetches data for a specific channel within a trigger's data set.
 * The data includes both Y-axis values and their corresponding X-axis values.
 *
 * @param[in] Trigger_Number The number of the trigger for which to retrieve data.
 * @param[in] Channel_Number The number of the channel within the trigger data.
 * @param[out] Y_Axis A pointer to an array where Y-axis values will be stored. Must be pre-allocated.
 * @param[out] X_Axis A pointer to an array where X-axis values will be stored. Must be pre-allocated.
 * @param[in] position The starting position within the trigger data.
 * @param[in] count The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 *
 * @deprecated This function is deprecated and will be removed in a future release.
 * Please use @ref DWIGetTriggerDataF instead.
 */
DWLIB_API enum DWStatus DWGetTriggerDataF(int Trigger_Number, int Channel_Number, double* Y_Axis, double* X_Axis, double position, int count);

/**
 * @brief Retrieves trigger data using a specific reader instance.
 *
 * @param[in] reader The reader instance handle to use for this operation.
 * @param[in] Trigger_Number The number of the trigger.
 * @param[in] Channel_Number The number of the channel within the trigger data.
 * @param[out] Y_Axis A pointer to an array for Y-axis values.
 * @param[out] X_Axis A pointer to an array for X-axis values.
 * @param[in] position The starting position within the trigger data.
 * @param[in] count The number of data points to retrieve.
 *
 * @return An enumeration value of type DWStatus indicating the result of the operation.
 */
DWLIB_API enum DWStatus DWIGetTriggerDataF(READER_HANDLE reader, int Trigger_Number, int Channel_Number, double* Y_Axis, double* X_Axis, double position, int count);