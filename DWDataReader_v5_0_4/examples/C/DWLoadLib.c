#define DW_IMPL_DLL_FUNCS
#include "DWLoadLib.h"

#if defined(_WIN32)
	#include <Windows.h>
	#define DW_HANDLE HMODULE
	#define DW_LOAD_LIBRARY(name) LoadLibrary(name)
	#define DW_GET_PROC_ADDRESS(handle, name) GetProcAddress(handle, name)
	#define DW_FREE_LIBRARY(handle) FreeLibrary(handle)
#else
	#include <dlfcn.h>
	#define DW_HANDLE void*
	#define DW_LOAD_LIBRARY(name) dlopen(name, RTLD_LAZY)
	#define DW_GET_PROC_ADDRESS(handle, name) dlsym(handle, name)
	#define DW_FREE_LIBRARY(handle) dlclose(handle)
#endif

#define DW_LOAD_FUNC(handle, func) \
	func = (_##func)DW_GET_PROC_ADDRESS(handle, #func); \
	if (!func) { \
		return 0; \
	}

static DW_HANDLE hInstLibrary = 0;

const char* get_dw_library_name()
{
#if defined(_WIN32)
	#include "Windows.h"
	#ifdef _WIN64
		return TEXT("DWDataReaderLib64.dll");
	#else
		return TEXT("DWDataReaderLib.dll");
	#endif
#elif defined(__linux__)
	#if defined(__x86_64__) || defined(_M_X64) || defined(__aarch64__) || defined(__ppc64__)
		return "DWDataReaderLib64.so";
	#else
		return "DWDataReaderLib.so";
	#endif
#elif defined(__APPLE__)
	#if defined(__x86_64__) || defined(__aarch64__)
		return "DWDataReaderLib64.dylib";
	#else
		return "DWDataReaderLib.dylib";
	#endif
#endif
}

int LoadDWDLL()
{
	const char* lib_name = get_dw_library_name();
    hInstLibrary = DW_LOAD_LIBRARY(lib_name);
	if (!hInstLibrary)
		return 0;

	DW_LOAD_FUNC(hInstLibrary, DWGetLastStatus);
	DW_LOAD_FUNC(hInstLibrary, DWInit);
	DW_LOAD_FUNC(hInstLibrary, DWDeInit);
	DW_LOAD_FUNC(hInstLibrary, DWAddReader);
	DW_LOAD_FUNC(hInstLibrary, DWGetNumReaders);
	DW_LOAD_FUNC(hInstLibrary, DWSetActiveReader);
	DW_LOAD_FUNC(hInstLibrary, DWGetVersion);
	DW_LOAD_FUNC(hInstLibrary, DWOpenDataFile);
	DW_LOAD_FUNC(hInstLibrary, DWCloseDataFile);
	DW_LOAD_FUNC(hInstLibrary, DWGetMultiFileIndex);
	DW_LOAD_FUNC(hInstLibrary, DWGetMeasurementInfo);
	DW_LOAD_FUNC(hInstLibrary, DWGetChannelListCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetChannelList);
	DW_LOAD_FUNC(hInstLibrary, DWGetChannelFactors);
	DW_LOAD_FUNC(hInstLibrary, DWGetChannelProps);
	DW_LOAD_FUNC(hInstLibrary, DWGetBinarySamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetBinarySamples);
	DW_LOAD_FUNC(hInstLibrary, DWGetBinarySamplesEx);
	DW_LOAD_FUNC(hInstLibrary, DWGetBinChannelListCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetBinChannelList);
	DW_LOAD_FUNC(hInstLibrary, DWGetBinRecSamples);
	DW_LOAD_FUNC(hInstLibrary, DWGetBinData);
	DW_LOAD_FUNC(hInstLibrary, DWGetScaledSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetScaledSamples);
	DW_LOAD_FUNC(hInstLibrary, DWGetRawSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetRawSamples);
	DW_LOAD_FUNC(hInstLibrary, DWGetComplexChannelListCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetComplexChannelList);
	DW_LOAD_FUNC(hInstLibrary, DWGetComplexScaledSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetComplexScaledSamples);
	DW_LOAD_FUNC(hInstLibrary, DWGetComplexRawSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetComplexRawSamples);
	DW_LOAD_FUNC(hInstLibrary, DWGetEventListCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetEventList);
	DW_LOAD_FUNC(hInstLibrary, DWGetStream);
	DW_LOAD_FUNC(hInstLibrary, DWExportHeader);
	DW_LOAD_FUNC(hInstLibrary, DWGetTextChannelListCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetTextChannelList);
	DW_LOAD_FUNC(hInstLibrary, DWGetTextValuesCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetTextValues);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedValuesCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedValues);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedValuesBlock);
	DW_LOAD_FUNC(hInstLibrary, DWGetHeaderEntryCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetHeaderEntryList);
	DW_LOAD_FUNC(hInstLibrary, DWGetHeaderEntryText);
	DW_LOAD_FUNC(hInstLibrary, DWGetStoringType);
	DW_LOAD_FUNC(hInstLibrary, DWGetArrayInfoCount);
	DW_LOAD_FUNC(hInstLibrary, DWGetArrayInfoList);
	DW_LOAD_FUNC(hInstLibrary, DWGetArrayIndexValue);
	DW_LOAD_FUNC(hInstLibrary, DWGetArrayIndexValueF);
	DW_LOAD_FUNC(hInstLibrary, DWGetChannelListItem);
	DW_LOAD_FUNC(hInstLibrary, DWGetComplexChannelListItem);
	DW_LOAD_FUNC(hInstLibrary, DWGetHeaderEntryListItem);
	DW_LOAD_FUNC(hInstLibrary, DWGetEventListItem);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedAveValues);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedMinValues);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedMaxValues);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedRMSValues);
	DW_LOAD_FUNC(hInstLibrary, DWGetHeaderEntryTextF);
	DW_LOAD_FUNC(hInstLibrary, DWGetHeaderEntryNameF);
	DW_LOAD_FUNC(hInstLibrary, DWGetHeaderEntryIDF);
	DW_LOAD_FUNC(hInstLibrary, DWGetEventTimeF);
	DW_LOAD_FUNC(hInstLibrary, DWGetEventTextF);
	DW_LOAD_FUNC(hInstLibrary, DWGetEventTypeF);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedDataChannelCountF);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedDataChannelNameF);
	DW_LOAD_FUNC(hInstLibrary, DWGetReducedDataChannelIndexF);
	DW_LOAD_FUNC(hInstLibrary, DWGetRecudedDataChannelInfoF);
	DW_LOAD_FUNC(hInstLibrary, DWGetRecudedDataF);
	DW_LOAD_FUNC(hInstLibrary, DWGetRecudedYDataF);
	DW_LOAD_FUNC(hInstLibrary, DWGetRecudedDataAllF);
	DW_LOAD_FUNC(hInstLibrary, DWGetTriggerDataTriggerCountF);
	DW_LOAD_FUNC(hInstLibrary, DWGetTriggerDataTriggerTimeF);
	DW_LOAD_FUNC(hInstLibrary, DWGetTriggerDataChannelNameF);
	DW_LOAD_FUNC(hInstLibrary, DWGetTriggerDataChannelIndexF);
	DW_LOAD_FUNC(hInstLibrary, DWGetTriggerDataChannelInfoF);
	DW_LOAD_FUNC(hInstLibrary, DWGetTriggerDataF);

	DW_LOAD_FUNC(hInstLibrary, DWICreateReader);
	DW_LOAD_FUNC(hInstLibrary, DWIDestroyReader);
	DW_LOAD_FUNC(hInstLibrary, DWGetVersionEx);
	DW_LOAD_FUNC(hInstLibrary, DWIOpenDataFile);
	DW_LOAD_FUNC(hInstLibrary, DWICloseDataFile);
	DW_LOAD_FUNC(hInstLibrary, DWIGetMultiFileIndex);
	DW_LOAD_FUNC(hInstLibrary, DWIGetMeasurementInfo);
	DW_LOAD_FUNC(hInstLibrary, DWIGetChannelListCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetChannelList);
	DW_LOAD_FUNC(hInstLibrary, DWIGetChannelFactors);
	DW_LOAD_FUNC(hInstLibrary, DWIGetChannelProps);
	DW_LOAD_FUNC(hInstLibrary, DWIGetBinarySamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetBinarySamples);
	DW_LOAD_FUNC(hInstLibrary, DWIGetBinarySamplesEx);
	DW_LOAD_FUNC(hInstLibrary, DWIGetBinChannelListCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetBinChannelList);
	DW_LOAD_FUNC(hInstLibrary, DWIGetBinRecSamples);
	DW_LOAD_FUNC(hInstLibrary, DWIGetBinData);
	DW_LOAD_FUNC(hInstLibrary, DWIGetScaledSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetScaledSamples);
	DW_LOAD_FUNC(hInstLibrary, DWIGetRawSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetRawSamples);
	DW_LOAD_FUNC(hInstLibrary, DWIGetComplexChannelListCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetComplexChannelList);
	DW_LOAD_FUNC(hInstLibrary, DWIGetComplexScaledSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetComplexScaledSamples);
	DW_LOAD_FUNC(hInstLibrary, DWIGetComplexRawSamplesCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetComplexRawSamples);
	DW_LOAD_FUNC(hInstLibrary, DWIGetEventListCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetEventList);
	DW_LOAD_FUNC(hInstLibrary, DWIGetStream);
	DW_LOAD_FUNC(hInstLibrary, DWIExportHeader);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedValuesCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedValues);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedValuesBlock);
	DW_LOAD_FUNC(hInstLibrary, DWIGetHeaderEntryCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetHeaderEntryList);
	DW_LOAD_FUNC(hInstLibrary, DWIGetHeaderEntryText);
	DW_LOAD_FUNC(hInstLibrary, DWIGetStoringType);
	DW_LOAD_FUNC(hInstLibrary, DWIGetArrayInfoCount);
	DW_LOAD_FUNC(hInstLibrary, DWIGetArrayInfoList);
	DW_LOAD_FUNC(hInstLibrary, DWIGetArrayIndexValue);
	DW_LOAD_FUNC(hInstLibrary, DWIGetArrayIndexValueF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetChannelListItem);
	DW_LOAD_FUNC(hInstLibrary, DWIGetComplexChannelListItem);
	DW_LOAD_FUNC(hInstLibrary, DWIGetHeaderEntryListItem);
	DW_LOAD_FUNC(hInstLibrary, DWIGetEventListItem);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedAveValues);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedMinValues);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedMaxValues);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedRMSValues);
	DW_LOAD_FUNC(hInstLibrary, DWIGetHeaderEntryTextF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetHeaderEntryNameF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetHeaderEntryIDF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetEventTimeF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetEventTextF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetEventTypeF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedDataChannelCountF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedDataChannelNameF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetReducedDataChannelIndexF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetRecudedDataChannelInfoF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetRecudedDataF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetRecudedYDataF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetRecudedDataAllF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetTriggerDataTriggerCountF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetTriggerDataTriggerTimeF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetTriggerDataChannelNameF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetTriggerDataChannelIndexF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetTriggerDataChannelInfoF);
	DW_LOAD_FUNC(hInstLibrary, DWIGetTriggerDataF);

	return 1;
}

int CloseDWDLL()
{
	return DW_FREE_LIBRARY(hInstLibrary);
}
