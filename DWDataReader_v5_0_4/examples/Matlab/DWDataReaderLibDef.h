#pragma once 

#if defined(_WIN32) || defined(_WIN64)
    #ifdef DWLIB_BUILDING
        #define DWLIB_API __declspec(dllexport)
    #else
        #define DWLIB_API __declspec(dllimport)
    #endif
#else
    #define DWLIB_API
#endif