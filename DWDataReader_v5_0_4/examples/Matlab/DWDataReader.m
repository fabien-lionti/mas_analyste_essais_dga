%% DWDataReader.m
% MATLAB/Octave wrapper for DWDataReader library
% This file provides functions to interact with Dewesoft data files
% using the DWDataReaderLib library

classdef DWDataReader < handle
    % Properties to store library and reader handles
    properties (Access = private)
        LibraryLoaded = false;
        LibraryHandle = 0;
        ReaderHandle = 0;
        IsReaderCreated = false;
        CurrentFileName = '';
    end
    
    % Constants for status codes
    properties (Constant)
        % Status codes
        DWSTAT_OK = 0;
        DWSTAT_ERROR = 1;
        DWSTAT_ERROR_FILE_CANNOT_OPEN = 2;
        DWSTAT_ERROR_FILE_ALREADY_IN_USE = 3;
        DWSTAT_ERROR_FILE_CORRUPT = 4;
        DWSTAT_ERROR_NO_MEMORY_ALLOC = 5;
        DWSTAT_ERROR_CREATE_DEST_FILE = 6;
        DWSTAT_ERROR_EXTRACTING_FILE = 7;
        DWSTAT_ERROR_CANNOT_OPEN_EXTRACTED_FILE = 8;
        DWSTAT_ERROR_INVALID_IB_LEVEL = 9;
        DWSTAT_ERROR_CAN_NOT_SUPPORTED = 10;
        DWSTAT_ERROR_INVALID_READER = 11;
        DWSTAT_ERROR_INVALID_INDEX = 12;
        DWSTAT_ERROR_INSUFFICENT_BUFFER = 13;
    end
    
    methods
        function obj = DWDataReader()
            % Constructor - Initialize the library
            obj.loadLibrary();
        end
        
        function delete(obj)
            % Destructor - Clean up resources
            obj.close();
            obj.unloadLibrary();
        end
        
        function numericStatus = convertEnumToNumeric(obj, enumValue)
            % Convert enum text to numeric value
            if isnumeric(enumValue)
                % Already numeric
                numericStatus = enumValue;
                return;
            end
            
            if ischar(enumValue) || isstring(enumValue)
                enumStr = char(enumValue);
                switch enumStr
                    case 'DWSTAT_OK'
                        numericStatus = obj.DWSTAT_OK;
                    case 'DWSTAT_ERROR'
                        numericStatus = obj.DWSTAT_ERROR;
                    case 'DWSTAT_ERROR_FILE_CANNOT_OPEN'
                        numericStatus = obj.DWSTAT_ERROR_FILE_CANNOT_OPEN;
                    case 'DWSTAT_ERROR_FILE_ALREADY_IN_USE'
                        numericStatus = obj.DWSTAT_ERROR_FILE_ALREADY_IN_USE;
                    case 'DWSTAT_ERROR_FILE_CORRUPT'
                        numericStatus = obj.DWSTAT_ERROR_FILE_CORRUPT;
                    case 'DWSTAT_ERROR_NO_MEMORY_ALLOC'
                        numericStatus = obj.DWSTAT_ERROR_NO_MEMORY_ALLOC;
                    case 'DWSTAT_ERROR_CREATE_DEST_FILE'
                        numericStatus = obj.DWSTAT_ERROR_CREATE_DEST_FILE;
                    case 'DWSTAT_ERROR_EXTRACTING_FILE'
                        numericStatus = obj.DWSTAT_ERROR_EXTRACTING_FILE;
                    case 'DWSTAT_ERROR_CANNOT_OPEN_EXTRACTED_FILE'
                        numericStatus = obj.DWSTAT_ERROR_CANNOT_OPEN_EXTRACTED_FILE;
                    case 'DWSTAT_ERROR_INVALID_IB_LEVEL'
                        numericStatus = obj.DWSTAT_ERROR_INVALID_IB_LEVEL;
                    case 'DWSTAT_ERROR_CAN_NOT_SUPPORTED'
                        numericStatus = obj.DWSTAT_ERROR_CAN_NOT_SUPPORTED;
                    case 'DWSTAT_ERROR_INVALID_READER'
                        numericStatus = obj.DWSTAT_ERROR_INVALID_READER;
                    case 'DWSTAT_ERROR_INVALID_INDEX'
                        numericStatus = obj.DWSTAT_ERROR_INVALID_INDEX;
                    case 'DWSTAT_ERROR_INSUFFICENT_BUFFER'
                        numericStatus = obj.DWSTAT_ERROR_INSUFFICENT_BUFFER;
                    otherwise
                        % Unknown enum, try to parse as number
                        numericStatus = str2double(enumStr);
                        if isnan(numericStatus)
                            numericStatus = -1; % Unknown error
                        end
                end
            else
                numericStatus = -1; % Unknown type
            end
        end
        
        function success = loadLibrary(obj)
            % Load the DWDataReader library
            if obj.LibraryLoaded
                success = true;
                return;
            end

            % Path to header file and DLL
            headerPath = fullfile(pwd, 'DWDataReaderLibFuncs.h');

            if contains(computer('arch'), '64')
                libName = 'DWDataReaderLib64';
            else
                libName = 'DWDataReaderLib';
            end

            if ~libisloaded(libName)
                % Load the library
                
                if ispc || ismac || isunix
                    try
                        [notfound, warnings] = loadlibrary(fullfile(pwd, 'DWDataReaderLib64.dll'), headerPath, 'alias', 'DWReader', 'debug');
                        if ~isempty(notfound)
                            warning('Some functions not found: %s', strjoin(notfound, ', '));
                        end
                        obj.LibraryLoaded = true;
                        success = true;
                        fprintf('DWDataReader library loaded successfully\n');
                    catch ME
                        fprintf('Error loading library: %s\n', ME.message);
                        success = false;
                        return;
                    end
                else
                    fprintf('Error: Unknown platform!');
                    success = false;
                    return;
                end

            else
                obj.LibraryLoaded = true;
                success = true;
                fprintf('DWDataReader library already loaded\n');
            end

            % Create a reader instance
            obj.createReader();
        end
        
        function unloadLibrary(obj)
            % Unload the library
            if obj.LibraryLoaded
                if obj.IsReaderCreated
                    obj.destroyReader();
                end
                
                try
                    unloadlibrary('DWReader');
                    obj.LibraryLoaded = false;
                    fprintf('DWDataReader library unloaded\n');
                catch ME
                    fprintf('Error unloading library: %s\n', ME.message);
                end
            end
        end
        
        function success = createReader(obj)
            % Create a reader instance
            if ~obj.LibraryLoaded
                error('Library not loaded');
            end
            
            if obj.IsReaderCreated
                success = true;
                return;
            end

            % Create reader
            [status, readerHandlePtr] = calllib('DWReader', 'DWICreateReader', libpointer('voidPtrPtr'));
            status = obj.convertEnumToNumeric(status);
            
            if status == obj.DWSTAT_OK
                obj.ReaderHandle = readerHandlePtr;
                obj.IsReaderCreated = true;
                success = true;
                fprintf('Reader created successfully\n');
            else
                success = false;
                [errorStatus, errorMsg] = obj.getLastError();
                fprintf('Failed to create reader. Status: %d, Error: %s\n', errorStatus, errorMsg);
            end
        end
        
        function destroyReader(obj)
            % Destroy the reader instance
            if obj.IsReaderCreated
                status = calllib('DWReader', 'DWIDestroyReader', obj.ReaderHandle);
                status = obj.convertEnumToNumeric(status);
                
                if status == obj.DWSTAT_OK
                    obj.IsReaderCreated = false;
                    obj.ReaderHandle = 0;
                    fprintf('Reader destroyed successfully\n');
                else
                    [errorStatus, errorMsg] = obj.getLastError();
                    fprintf('Failed to destroy reader. Status: %d, Error: %s\n', errorStatus, errorMsg);
                end
            end
        end
        
        function [major, minor, patch] = getVersion(obj)
            % Get the version of the library
            if ~obj.LibraryLoaded
                error('Library not loaded');
            end

            [status, major, minor, patch] = calllib('DWReader', 'DWGetVersionEx', libpointer('int32Ptr', 0), libpointer('int32Ptr', 0), libpointer('int32Ptr', 0));
            status = obj.convertEnumToNumeric(status);
            
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get version. Status: %d, Error: %s', errorStatus, errorMsg);
            end
        end
        
        function [status, errorMsg] = getLastError(obj)
            % Get the last error message
            if ~obj.LibraryLoaded
                error('Library not loaded');
            end

            errorBufferSize = 1024;
            [~, status, errorBuffer, errorBufferSizePtr] = calllib('DWReader', 'DWGetLastStatus', libpointer('DWStatus', obj.DWSTAT_OK), blanks(errorBufferSize), libpointer('int32Ptr', errorBufferSize));
            
            status = obj.convertEnumToNumeric(status);
            errorMsg = errorBuffer;
        end
        
        function [success, fileInfo] = openFile(obj, fileName)
            % Open a Dewesoft data file
            if ~obj.IsReaderCreated
                error('Reader not created');
            end
            
            % Open file
            [status, ~, ~, fileInfoPtr] = calllib('DWReader', 'DWIOpenDataFile', obj.ReaderHandle, fileName, struct());
            status = obj.convertEnumToNumeric(status);
            
            if status == obj.DWSTAT_OK
                obj.CurrentFileName = fileName;
                fileInfo = struct(...
                    'sample_rate', fileInfoPtr.sample_rate, ...
                    'start_store_time', fileInfoPtr.start_store_time, ...
                    'duration', fileInfoPtr.duration);
                success = true;
                fprintf('File opened successfully: %s\n', fileName);
            else
                success = false;
                [errorStatus, errorMsg] = obj.getLastError();
                fprintf('Failed to open file. Status: %d, Error: %s\n', errorStatus, errorMsg);
                fileInfo = struct();
            end
        end
        
        function success = close(obj)
            % Close the current file
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                success = true;  % Nothing to close
                return;
            end
            
            status = calllib('DWReader', 'DWICloseDataFile', obj.ReaderHandle);
            status = obj.convertEnumToNumeric(status);
            
            if status == obj.DWSTAT_OK
                obj.CurrentFileName = '';
                success = true;
                fprintf('File closed successfully\n');
            else
                success = false;
                [errorStatus, errorMsg] = obj.getLastError();
                fprintf('Failed to close file. Status: %d, Error: %s\n', errorStatus, errorMsg);
            end
        end
        
        function measurementInfo = getMeasurementInfo(obj)
            % Get measurement info
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                error('No file is open');
            end
            
            [status, ~, infoPtr] = calllib('DWReader', 'DWIGetMeasurementInfo', obj.ReaderHandle, struct());
            status = obj.convertEnumToNumeric(status);
            
            if status == obj.DWSTAT_OK
                measurementInfo = struct(...
                    'sample_rate', infoPtr.sample_rate, ...
                    'start_measure_time', infoPtr.start_measure_time, ...
                    'start_store_time', infoPtr.start_store_time, ...
                    'duration', infoPtr.duration);
            else
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get measurement info. Status: %d, Error: %s', errorStatus, errorMsg);
            end
        end
        
        function channels = getChannelList(obj)
            % Get list of channels in the file
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                error('No file is open');
            end

            [status, ~, count] = calllib('DWReader', 'DWIGetChannelListCount', obj.ReaderHandle, libpointer('int32Ptr', 0));
            status = obj.convertEnumToNumeric(status);
            
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get channel count. Status: %d, Error: %s', errorStatus, errorMsg);
            end
            
            if count <= 0
                channels = [];
                return;
            end
            
            % Get channels using DWIGetChannelListItem
            channels = struct('index', {}, 'name', {}, 'unit', {}, ...
                             'description', {}, 'color', {}, 'array_size', {});
            
            for i = 1:count
                % Pre-allocate buffers for string outputs
                maxCharSize = 200; % Adjust based on expected string lengths
                nameBuffer = blanks(maxCharSize);
                unitBuffer = blanks(maxCharSize);
                descriptionBuffer = blanks(maxCharSize);
                
                % Call DWIGetChannelListItem for each channel
                [status, ~, index, name, unit, description, color, array_size] = ...
                    calllib('DWReader', 'DWIGetChannelListItem', ...
                            obj.ReaderHandle, ...
                            i-1, ...  % Convert MATLAB 1-based to C 0-based indexing
                            libpointer('int32Ptr', 0), ...     % index output
                            nameBuffer, ...                     % name buffer
                            unitBuffer, ...                     % unit buffer  
                            descriptionBuffer, ...              % description buffer
                            libpointer('int32Ptr', 0), ...     % color output
                            libpointer('int32Ptr', 0), ...     % array_size output
                            maxCharSize);                       % max_char_size
                
                status = obj.convertEnumToNumeric(status);
                
                if status == obj.DWSTAT_OK
                    % Store the channel information
                    channels(i).index = index;
                    channels(i).name = strtrim(name);           % Remove trailing spaces
                    channels(i).unit = strtrim(unit);
                    channels(i).description = strtrim(description);
                    channels(i).color = color;
                    channels(i).array_size = array_size;
                else
                    [errorStatus, errorMsg] = obj.getLastError();
                    error('Failed to get channel %d. Status: %d, Error: %s', i-1, errorStatus, errorMsg);
                end
            end
        end
        
        function [data, timestamps] = getScaledData(obj, channel, startPos, count)
            % Get scaled data from a channel
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                error('No file is open');
            end
            
            % Get sample count if not provided
            if nargin < 4
                [status, ~, count] = calllib('DWReader', 'DWIGetScaledSamplesCount', obj.ReaderHandle, channel.index, libpointer('int64Ptr', 0));
                status = obj.convertEnumToNumeric(status);
                
                if status ~= obj.DWSTAT_OK
                    [errorStatus, errorMsg] = obj.getLastError();
                    error('Failed to get sample count. Status: %d, Error: %s', errorStatus, errorMsg);
                end
            end
            
            % Set default start position if not provided
            if nargin < 3
                startPos = 0;
            end
            
            % Allocate memory for data and timestamps
            dataPtr = libpointer('doublePtr', zeros(count*int64(channel.array_size),1));
            timestampsPtr = libpointer('doublePtr', zeros(count,1));
            
            % Get data
            status = calllib('DWReader', 'DWIGetScaledSamples', obj.ReaderHandle, ...
                             channel.index, int64(startPos), count, dataPtr, timestampsPtr);
            status = obj.convertEnumToNumeric(status);
            
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get scaled samples. Status: %d, Error: %s', errorStatus, errorMsg);
            end

            data = reshape(dataPtr.Value, count, channel.array_size);
            timestamps = timestampsPtr.Value;
        end
        
        function [data, timestamps] = getComplexData(obj, channelIndex, startPos, count)
            % Get complex data from a channel
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                error('No file is open');
            end
            
            % Get sample count if not provided
            if nargin < 4
                countPtr = libpointer('int64Ptr', 0);
                [status, ~, ~, count] = calllib('DWReader', 'DWIGetComplexScaledSamplesCount', obj.ReaderHandle, channelIndex, countPtr);
                status = obj.convertEnumToNumeric(status);
                
                if status ~= obj.DWSTAT_OK
                    [errorStatus, errorMsg] = obj.getLastError();
                    error('Failed to get complex sample count. Status: %d, Error: %s', errorStatus, errorMsg);
                end
            end
            
            % Set default start position if not provided
            if nargin < 3
                startPos = 0;
            end
            
            % Allocate memory for complex data and timestamps
            complexDataPtr = libpointer('DWComplex', zeros(count, 2)); % re, im
            timestampsPtr = libpointer('doublePtr', zeros(count, 1));
            
            % Get complex data
            [status, ~, ~, ~, ~, complexData, timestamps] = calllib('DWReader', 'DWIGetComplexScaledSamples', obj.ReaderHandle, ...
                             channelIndex, startPos, count, complexDataPtr, timestampsPtr);
            status = obj.convertEnumToNumeric(status);
            
            if status == obj.DWSTAT_OK                
                % Convert to complex numbers in MATLAB
                data = complex([complexData.re], [complexData.im])';
            else
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get complex scaled samples. Status: %d, Error: %s', errorStatus, errorMsg);
            end
        end
        
        function events = getEvents(obj)
            % Get all events in the file
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                error('No file is open');
            end
            
            % Get event count
            countPtr = libpointer('int32Ptr', 0);
            [status, ~, count] = calllib('DWReader', 'DWIGetEventListCount', obj.ReaderHandle, countPtr);
            status = obj.convertEnumToNumeric(status);
            
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get event count. Status: %d, Error: %s', errorStatus, errorMsg);
            end
            
            if count <= 0
                events = [];
                return;
            end
            
           % Get events using DWGetEventListItem
            events = struct('event_type', {}, 'time_stamp', {}, 'event_text', {});
            
            for i = 1:count
                % Pre-allocate buffer for event text
                maxCharSize = 200; % Based on DWEvent struct definition
                eventTextBuffer = blanks(maxCharSize);
                
                % Call DWGetEventListItem for each event
                [status, ~, event_type, time_stamp, event_text] = ...
                    calllib('DWReader', 'DWIGetEventListItem', ...
                            obj.ReaderHandle, ...
                            i-1, ...  % Convert MATLAB 1-based to C 0-based indexing
                            libpointer('int32Ptr', 0), ...     % event_type output
                            libpointer('doublePtr', 0), ...    % time_stamp output
                            eventTextBuffer, ...               % event_text buffer
                            maxCharSize);                      % max_char_size
                
                status = obj.convertEnumToNumeric(status);
                
                if status == obj.DWSTAT_OK
                    % Store the event information
                    events(i).event_type = event_type;
                    events(i).time_stamp = time_stamp;
                    events(i).event_text = strtrim(event_text);  % Remove trailing spaces
                else
                    [errorStatus, errorMsg] = obj.getLastError();
                    error('Failed to get event %d. Status: %d, Error: %s', i-1, errorStatus, errorMsg);
                end
            end
        end
        
        function [values, blockSize] = getReducedValues(obj, channel, startPos, count)
            % Get reduced values from a channel
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                error('No file is open');
            end
            
            % Get reduced values count and block size
            countPtr = libpointer('int32Ptr', 0);
            blockSizePtr = libpointer('doublePtr', 0);
            
            [status, ~, totalCount, blockSize] = calllib('DWReader', 'DWIGetReducedValuesCount', ...
                            obj.ReaderHandle, channel.index, countPtr, blockSizePtr);
            status = obj.convertEnumToNumeric(status);
            
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get reduced values count. Status: %d, Error: %s', errorStatus, errorMsg);
            end
            
            % Set default values if not provided
            if nargin < 4
                count = totalCount;
            end
            
            if nargin < 3
                startPos = 0;
            end
            
            count = min(count, totalCount - startPos);
            
            if count <= 0
                values = [];
                return;
            end
            
            % Allocate memory for reduced values
            timestampsPtr = libpointer('doublePtr', zeros(count, 1));
            minPtr = libpointer('doublePtr', zeros(count, 1));
            maxPtr = libpointer('doublePtr', zeros(count, 1));
            avePtr = libpointer('doublePtr', zeros(count, 1));
            rmsPtr = libpointer('doublePtr', zeros(count, 1));
            values = struct('time_stamp', {}, 'ave', {}, 'min', {}, 'max', {}, 'rms', {});
            
            % Get MIN values
            [status, ~, minValues, timestamps] = calllib('DWReader', 'DWIGetReducedMinValues', ...
                            obj.ReaderHandle, channel.index, startPos, count, minPtr, timestampsPtr);

            status = obj.convertEnumToNumeric(status);
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get reduced values. Status: %d, Error: %s', errorStatus, errorMsg);
            end

            % Get MAX values
            [status, ~, maxValues, ~] = calllib('DWReader', 'DWIGetReducedMaxValues', ...
                            obj.ReaderHandle, channel.index, startPos, count, maxPtr, timestampsPtr);

            status = obj.convertEnumToNumeric(status);
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get reduced values. Status: %d, Error: %s', errorStatus, errorMsg);
            end

            % Get AVE values
            [status, ~, aveValues, ~] = calllib('DWReader', 'DWIGetReducedAveValues', ...
                            obj.ReaderHandle, channel.index, startPos, count, avePtr, timestampsPtr);

            status = obj.convertEnumToNumeric(status);
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get reduced values. Status: %d, Error: %s', errorStatus, errorMsg);
            end

            % Get RMS values
            [status, ~, rmsValues, ~] = calllib('DWReader', 'DWIGetReducedRMSValues', ...
                            obj.ReaderHandle, channel.index, startPos, count, rmsPtr, timestampsPtr);

            status = obj.convertEnumToNumeric(status);
            if status ~= obj.DWSTAT_OK
                [errorStatus, errorMsg] = obj.getLastError();
                error('Failed to get reduced values. Status: %d, Error: %s', errorStatus, errorMsg);
            end
            
            % Convert to MATLAB struct array                
            for i = 1:count
                values(i).time_stamp = timestamps(i);
                values(i).min = minValues(i);
                values(i).max = maxValues(i);
                values(i).ave = aveValues(i);
                values(i).rms = rmsValues(i);
            end
        end
        
        function success = exportHeader(obj, outputFileName)
            % Export header to XML file
            if ~obj.IsReaderCreated || isempty(obj.CurrentFileName)
                error('No file is open');
            end
            
            status = calllib('DWReader', 'DWIExportHeader', obj.ReaderHandle, outputFileName);
            status = obj.convertEnumToNumeric(status);
            
            if status == obj.DWSTAT_OK
                success = true;
                fprintf('Header exported successfully to: %s\n', outputFileName);
            else
                success = false;
                [errorStatus, errorMsg] = obj.getLastError();
                fprintf('Failed to export header. Status: %d, Error: %s\n', errorStatus, errorMsg);
            end
        end
    end
    
    % Static methods for demonstration
    methods (Static)
        function demo(filename)
            % Demonstration of using the DWDataReader class
            if nargin < 1
                error('Please provide a filename');
            end
            
            % Create reader object
            reader = DWDataReader();
            
            try
                % Get version
                [major, minor, patch] = reader.getVersion();
                fprintf('DWDataReader version: %d.%d.%d\n', major, minor, patch);
                
                % Open file
                [success, fileInfo] = reader.openFile(filename);
                if ~success
                    error('Failed to open file: %s', filename);
                end
                
                fprintf('File info:\n');
                disp(fileInfo);
                
                % Get measurement info
                measurementInfo = reader.getMeasurementInfo();
                fprintf('Measurement info:\n');
                disp(measurementInfo);
                
                % Get channels
                channels = reader.getChannelList();
                fprintf('Found %d channels\n', numel(channels));
                
                % Display first few channels
                if ~isempty(channels)
                    fprintf('First %d channels:\n', min(5, numel(channels)));
                    for i = 1:min(5, numel(channels))
                        fprintf('Channel %d: %s (%s)\n', ...
                            channels(i).index, channels(i).name, channels(i).unit);
                    end
                    
                    % Get data from first channel as example
                    if numel(channels) > 0
                        fprintf('\nRetrieving sample data from channel %d (%s)...\n', ...
                            channels(1).index, channels(1).name);
                        [data, timestamps] = reader.getScaledData(channels(1), 0, 10);
                        
                        fprintf('First %d samples:\n', min(10, numel(data)));
                        for i = 1:min(10, numel(data))
                            fprintf('Time: %.6f, Value: %.6f\n', timestamps(i), data(i));
                        end


                        fprintf('\nRetrieving reduced data from channel %d (%s)...\n', ...
                            channels(1).index, channels(1).name);
                        reducedData = reader.getReducedValues(channels(1), 0, 10);
                        fprintf('First %d blocks:\n', min(10, numel(data)));
                        for i = 1:min(10, numel(data))
                            fprintf('Time: %.6f, Min: %.6f, Max: %.6f, Ave: %.6f, RMS: %.6f\n', reducedData(i).time_stamp, reducedData(i).min, reducedData(i).max, reducedData(i).ave, reducedData(i).rms);
                        end
                    end
                end
                
                % Get events
                events = reader.getEvents();
                fprintf('\nFound %d events\n', numel(events));
                
                % Display first few events
                if ~isempty(events)
                    fprintf('First %d events:\n', min(5, numel(events)));
                    for i = 1:min(5, numel(events))
                        fprintf('Event %d: Type %d, Time %.6f, Text: %s\n', ...
                            i, events(i).event_type, events(i).time_stamp, events(i).event_text);
                    end
                end
                
                % Export header
                reader.exportHeader('exported_header.xml');
                
                % Close file
                reader.close();
                
            catch ME
                fprintf('Error: %s\n', ME.message);
                reader.close();
            end
        end
    end
end