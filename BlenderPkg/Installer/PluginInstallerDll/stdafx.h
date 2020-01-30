// stdafx.h : include file for standard system include files,
// or project specific include files that are used frequently, but
// are changed infrequently
//

#pragma once


#define WIN32_LEAN_AND_MEAN             // Exclude rarely-used stuff from Windows headers
// Windows Header Files:
#include <windows.h>
#include <string>
#include <stdio.h>
#include <vector>
#include <fstream>
#include <sstream>
#include <iterator>
#include <iostream>
#include <shlobj.h>
#include <assert.h>


#include "../PluginInstallerDll/Logger.h"
#include "InstalledBlender.h"

template <typename... Args>
inline void LogSystem(const char *format, const Args&... args)
{
	Logger::Printf(format, args...);
}

std::vector<std::wstring> split(const std::wstring &s, wchar_t delim);
void copyStringToClipboard(const std::wstring &str);
std::string WstringToString(const std::wstring& wstr);
std::wstring GetSystemFolderPaths(int csidl);
std::wstring & URLfirendly(std::wstring & str);

// TODO: reference additional headers your program requires here
