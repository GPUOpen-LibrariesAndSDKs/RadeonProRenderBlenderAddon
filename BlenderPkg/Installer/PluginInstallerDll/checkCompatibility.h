#pragma once

#include <vector>
#include <string>

struct INSTALLER_SYSTEM_INFO
{
	INSTALLER_SYSTEM_INFO()
	{
		getInfoSuccess = false;
		openclVersion = 0.0;
		gpuAvailableForOpenCL = false;
		openCLLoadFailed = false;
	}

	bool getInfoSuccess;
	bool openCLLoadFailed;
	std::vector<std::wstring> gpuName;
	std::vector<std::wstring> gpuDriver;
	std::wstring osversion;
	bool gpuAvailableForOpenCL;
	float openclVersion;
};

extern INSTALLER_SYSTEM_INFO g_systemInfo;

void GetSystemInfo();

bool checkCompatibility_hardware(std::wstring &retMessage);
bool checkCompatibility_driver(std::wstring &retMessage);
