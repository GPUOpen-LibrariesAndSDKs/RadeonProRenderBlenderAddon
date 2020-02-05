#include "stdafx.h"
#include "checkCompatibility.h"
#include <comdef.h>
#include <Wbemidl.h>
#include "CL/cl.h"


#pragma comment(lib, "wbemuuid.lib")


typedef cl_int(*PclGetPlatformIDs)(cl_uint          /* num_entries */,
	cl_platform_id * /* platforms */,
	cl_uint *        /* num_platforms */);

typedef cl_int(*PclGetPlatformInfo)(cl_platform_id   /* platform */,
	cl_platform_info /* param_name */,
	size_t           /* param_value_size */,
	void *           /* param_value */,
	size_t *         /* param_value_size_ret */);

typedef cl_int(*PclGetDeviceIDs)(cl_platform_id   /* platform */,
	cl_device_type   /* device_type */,
	cl_uint          /* num_entries */,
	cl_device_id *   /* devices */,
	cl_uint *        /* num_devices */);

typedef cl_int(*PclGetDeviceInfo)(cl_device_id    /* device */,
	cl_device_info  /* param_name */,
	size_t          /* param_value_size */,
	void *          /* param_value */,
	size_t *        /* param_value_size_ret */);


INSTALLER_SYSTEM_INFO g_systemInfo;


int toInt(const std::wstring& str)
/*
Convert string to long int
*/
{
	wchar_t* end_ptr;
	long val = wcstol(str.c_str(), &end_ptr, 10);
	if (*end_ptr)
		throw std::exception("invalid_string");

	if ((val == LONG_MAX || val == LONG_MIN) && errno == ERANGE)
		throw std::exception("overflow");

	return val;
}


void GetSystemInfo()
{
	LogSystem("GetSystemInfo begin...");
	HRESULT hres;

	hres = CoInitializeEx(0, COINIT_MULTITHREADED);
	if (FAILED(hres))
	{
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - CoInitializeEx");
		return;
	}

	LogSystem("   GetSystemInfo Step 1 - ok");

	IWbemLocator *pLoc = NULL;

	hres = CoCreateInstance(
		CLSID_WbemLocator,
		0,
		CLSCTX_INPROC_SERVER,
		IID_IWbemLocator, (LPVOID *)&pLoc);

	if (FAILED(hres))
	{
		CoUninitialize();
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - CoCreateInstance");
		return;
	}

	LogSystem("   GetSystemInfo Step 2 - ok");

	IWbemServices *pSvc = NULL;
	hres = pLoc->ConnectServer(
		_bstr_t(L"ROOT\\CIMV2"), // Object path of WMI namespace
		NULL,                    // User name. NULL = current user
		NULL,                    // User password. NULL = current
		0,                       // Locale. NULL indicates current
		NULL,                    // Security flags.
		0,                       // Authority (for example, Kerberos)
		0,                       // Context object
		&pSvc                    // pointer to IWbemServices proxy
	);

	if (FAILED(hres))
	{
		pLoc->Release();
		CoUninitialize();
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - pLoc->ConnectServer");
		return;
	}

	LogSystem("   GetSystemInfo Step 3 - ok");
	hres = CoSetProxyBlanket(
		pSvc,                        // Indicates the proxy to set
		RPC_C_AUTHN_WINNT,           // RPC_C_AUTHN_xxx
		RPC_C_AUTHZ_NONE,            // RPC_C_AUTHZ_xxx
		NULL,                        // Server principal name
		RPC_C_AUTHN_LEVEL_CALL,      // RPC_C_AUTHN_LEVEL_xxx
		RPC_C_IMP_LEVEL_IMPERSONATE, // RPC_C_IMP_LEVEL_xxx
		NULL,                        // client identity
		EOAC_NONE                    // proxy capabilities
	);

	if (FAILED(hres))
	{
		pSvc->Release();
		pLoc->Release();
		CoUninitialize();
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - CoSetProxyBlanket");
		return;
	}

	LogSystem("   GetSystemInfo Step 4 - ok");
	IEnumWbemClassObject* pEnumerator = NULL;
	hres = pSvc->ExecQuery(
		bstr_t("WQL"),
		//bstr_t("SELECT * FROM Win32_OperatingSystem"),
		bstr_t("SELECT * FROM Win32_VideoController"),
		WBEM_FLAG_FORWARD_ONLY | WBEM_FLAG_RETURN_IMMEDIATELY,
		NULL,
		&pEnumerator);

	if (FAILED(hres))
	{
		pSvc->Release();
		pLoc->Release();
		CoUninitialize();
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - pSvc->ExecQuery 1");
		return;
	}

	LogSystem("   GetSystemInfo Step 5 - ok");
	while (pEnumerator)
	{
		IWbemClassObject *pclsObj = NULL;
		ULONG uReturn = 0;

		HRESULT hr = pEnumerator->Next(WBEM_INFINITE, 1,
			&pclsObj, &uReturn);

		if (0 == uReturn)
		{
			break;
		}

		VARIANT vtProp_driverversion;
		hr = pclsObj->Get(L"DriverVersion", 0, &vtProp_driverversion, 0, 0);
		g_systemInfo.gpuDriver.push_back(std::wstring(vtProp_driverversion.bstrVal));
		VariantClear(&vtProp_driverversion);

		VARIANT vtProp_name;
		hr = pclsObj->Get(L"Name", 0, &vtProp_name, 0, 0);
		g_systemInfo.gpuName.push_back(std::wstring(vtProp_name.bstrVal));
		VariantClear(&vtProp_name);

		pclsObj->Release();
		pclsObj = NULL;
	}

	pEnumerator->Release();
	pEnumerator = NULL;

	hres = pSvc->ExecQuery(
		bstr_t("WQL"),
		bstr_t("SELECT * FROM Win32_OperatingSystem"),
		WBEM_FLAG_FORWARD_ONLY | WBEM_FLAG_RETURN_IMMEDIATELY,
		NULL,
		&pEnumerator);

	if (FAILED(hres))
	{
		pSvc->Release();
		pLoc->Release();
		CoUninitialize();
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - pSvc->ExecQuery 2");
		return;
	}

	LogSystem("   GetSystemInfo Step 6  - ok");

	while (pEnumerator)
	{
		IWbemClassObject *pclsObj = NULL;
		ULONG uReturn = 0;

		HRESULT hr = pEnumerator->Next(WBEM_INFINITE, 1,
			&pclsObj, &uReturn);

		if (0 == uReturn)
		{
			break;
		}

		VARIANT vtProp_osName;
		hr = pclsObj->Get(L"Version", 0, &vtProp_osName, 0, 0);
		g_systemInfo.osversion = L"win" + std::wstring(vtProp_osName.bstrVal);
		VariantClear(&vtProp_osName);

		pclsObj->Release();
		pclsObj = NULL;
	}

	LogSystem("   GetSystemInfo Step 7  - ok");

	pEnumerator->Release();
	pEnumerator = NULL;
	pSvc->Release();
	pSvc = NULL;
	pLoc->Release();
	pLoc = NULL;

	CoUninitialize();

	LogSystem("   GetSystemInfo cleanup  - ok");

	//try to load OpenCL lib and methods required for version check
	HMODULE openclLib = LoadLibrary(L"OpenCL.dll");
	if (openclLib == NULL)
	{
		g_systemInfo.getInfoSuccess = false;
		g_systemInfo.openCLLoadFailed = true;
		LogSystem("GetSystemInfo: FAILED - LoadLibrary OpenCL.dll");
		return;
	}

	TCHAR buffer[MAX_PATH];
	if (GetModuleFileName(openclLib, buffer, MAX_PATH))
	{
		std::wstring s(buffer);
		LogSystem("   GetSystemInfo: OpenCL.dll path - %s", WstringToString(s).c_str());
	}
	else
	{
		LogSystem("   GetSystemInfo: can't get OpenCL.dll path");
	}

	//loading required methods
	PclGetPlatformIDs GetPlatformIDs = (PclGetPlatformIDs)GetProcAddress(openclLib, "clGetPlatformIDs");
	PclGetPlatformInfo GetPlatformInfo = (PclGetPlatformInfo)GetProcAddress(openclLib, "clGetPlatformInfo");
	PclGetDeviceIDs GetDeviceIDs = (PclGetDeviceIDs)GetProcAddress(openclLib, "clGetDeviceIDs");
	PclGetDeviceInfo GetDeviceInfo = (PclGetDeviceInfo)GetProcAddress(openclLib, "clGetDeviceInfo");

	if (!GetPlatformIDs || !GetPlatformInfo || !GetDeviceIDs || !GetDeviceInfo)
	{
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - GetProcAddress opencl");
		return;
	}

	LogSystem("   GetSystemInfo load OpenCL.dll - ok");

	//look for device with newer OpenCL version
	cl_int error = CL_SUCCESS;
	// Query for platforms
	std::vector<cl_platform_id> platforms;
	cl_uint platf_count = 0;
	error = GetPlatformIDs(0, nullptr, &platf_count);
	LogSystem("   GetSystemInfo first call GetPlatformIDs");
	if (error != CL_SUCCESS)
	{
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - can't get OpenCL platforms");
		return;
	}
	if (platf_count == 0)
	{
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - there are no available OpenCL platforms");
		return;
	}

	platforms.resize(platf_count);
	error |= GetPlatformIDs(platf_count, platforms.data(), nullptr);
	LogSystem("   GetSystemInfo second call GetPlatformIDs");
	if (error != CL_SUCCESS)
	{
		g_systemInfo.getInfoSuccess = false;
		LogSystem("GetSystemInfo: FAILED - can't get OpenCL platforms 2");
		return;
	}

	g_systemInfo.gpuAvailableForOpenCL = false;
	g_systemInfo.openclVersion = 0.0f;

	LogSystem("   GetSystemInfo look at devices start");

	for (auto& plat : platforms)
	{
		cl_uint device_count = 0;
		error = GetDeviceIDs(plat, CL_DEVICE_TYPE_GPU, 0, nullptr, &device_count);
		if (error == CL_DEVICE_NOT_FOUND)
			continue;
		std::vector<cl_device_id> devices(device_count);
		error |= GetDeviceIDs(plat, CL_DEVICE_TYPE_GPU, device_count, devices.data(), nullptr);
		if (error != CL_SUCCESS)
		{
			g_systemInfo.getInfoSuccess = false;
			LogSystem("GetSystemInfo: FAILED - can't get OpenCL devices");
			return;
		}

		for (auto& dev : devices)
		{
			size_t version_size = 0;
			error = GetDeviceInfo(dev, CL_DEVICE_VERSION, NULL, nullptr, &version_size);
			std::vector<char> version(version_size);
			error |= GetDeviceInfo(dev, CL_DEVICE_VERSION, version_size, version.data(), nullptr);
			if (error != CL_SUCCESS)
			{
				g_systemInfo.getInfoSuccess = false;
				LogSystem("GetSystemInfo: FAILED - can't get devices OpenCL version");
				return;
			}

			std::string strVersion(version.begin(), version.end());
			std::istringstream buf(strVersion);
			std::istream_iterator<std::string> beg(buf), end;
			std::vector<std::string> tokens(beg, end);
			float devCLVersion = std::stof(tokens[1]); // expected version string in format OpenCL<space><major_version.minor_version><space><vendor-specific information>

			LogSystem("+1 GPU supports OpenCL %f", devCLVersion);

			if (devCLVersion > g_systemInfo.openclVersion)
				g_systemInfo.openclVersion = devCLVersion;

			g_systemInfo.gpuAvailableForOpenCL = true;
		}
	}

	g_systemInfo.getInfoSuccess = true;
	LogSystem("GetSystemInfo: SUCCESS.");
	return;

}


bool IsDeviceNameBlacklisted(const std::wstring &deviceName)
{
	//this is the list of uncompatible devices known by the Radeon ProRender team.
	std::vector<std::wstring> listOfKnownUncompatibleDevices;
	listOfKnownUncompatibleDevices.push_back(L"NVIDIA GTX 570");
	listOfKnownUncompatibleDevices.push_back(L"NVIDIA GTX 670");
	listOfKnownUncompatibleDevices.push_back(L"Intel HD4600 series");
	listOfKnownUncompatibleDevices.push_back(L"Intel Graphics 502");

	std::vector<std::wstring>::iterator it;

	for (it = listOfKnownUncompatibleDevices.begin(); it != listOfKnownUncompatibleDevices.end(); ++it)
	{
		if ( deviceName == (*it)) //uncompatible device found
			return true;
	}

	return false;
}


bool checkCompatibility_hardware(std::wstring &retMessage)
{
	LogSystem("checkCompatibility_hardware begin...");
	retMessage = L"";

	GetSystemInfo();

	bool displaWarningMessage_cantGetInfo = false;
	bool displaWarningMessage_openCLLoadFailed = false;
	bool displaWarningMessage_incompatibleOpenCL = false;
	std::vector<std::wstring> displaWarningMessage_blacklistedDevice_names;

	if (!g_systemInfo.getInfoSuccess)
	{
		displaWarningMessage_cantGetInfo = true;
		LogSystem("displaWarningMessage_cantGetInfo = true");
	}

	if (g_systemInfo.openCLLoadFailed)
	{
		displaWarningMessage_openCLLoadFailed = true;
		LogSystem("displaWarningMessage_cantGetInfo = true");
	}

	if (g_systemInfo.getInfoSuccess && (!g_systemInfo.gpuAvailableForOpenCL || g_systemInfo.openclVersion < 1.2f))
	{
		displaWarningMessage_incompatibleOpenCL = true;
		LogSystem("displaWarningMessage_incompatibleOpenCL = true");
	}


	for (int iGpu = 0; iGpu<g_systemInfo.gpuName.size(); iGpu++)
	{
		const std::wstring &gpuNameA = g_systemInfo.gpuName[iGpu];

		if ( g_systemInfo.getInfoSuccess && IsDeviceNameBlacklisted(gpuNameA))
		{
			displaWarningMessage_blacklistedDevice_names.push_back(g_systemInfo.gpuName[iGpu]);
			LogSystem("incompatible device += %s", g_systemInfo.gpuName[iGpu].c_str());
		}
	}

	if (displaWarningMessage_openCLLoadFailed)
	{
		retMessage = L"Unable to load OpenCL.DLL. You may need to update your graphics driver.";
		LogSystem("!Warning: %s", WstringToString(retMessage).c_str());
		return false;
	}

	if (displaWarningMessage_cantGetInfo)
	{
		retMessage = L"Installer is not able to check the system compatibility.";
		LogSystem("!Warning: %s", WstringToString(retMessage).c_str());
		return false;
	}

	if (displaWarningMessage_incompatibleOpenCL)
	{
		retMessage = L"Your system seems incompatible with Radeon ProRender for OpenCL.\r\nOnly the CPU rendering mode may run correctly. ";
		LogSystem("!Warning: %s", WstringToString(retMessage).c_str());
		return false;
	}

	if (!displaWarningMessage_blacklistedDevice_names.empty())
	{
		retMessage = L"Some of your devices:\r\n";
		for (size_t i = 0; i < displaWarningMessage_blacklistedDevice_names.size(); i++)
		{
			retMessage += L"   " + displaWarningMessage_blacklistedDevice_names[i] + L"\r\n";
		}
		retMessage += L"are known as incompatible by the Radeon ProRender Team.";
		LogSystem("!Warning: %s", WstringToString(retMessage).c_str());
		return false;
	}

	LogSystem("checkCompatibility_hardware end.");
	return true;
}


bool ParseNVIDIADriver(const std::wstring & rawDriver, int& publicVersionOut)
{
	publicVersionOut = 0;

	try
	{
		std::vector<std::wstring> separatedNumbers = split(rawDriver, L'.');
		if (separatedNumbers.size() != 4)
		{
			LogSystem("ParseNVIDIADriver : ERROR Length");
			return false;
		}

		int n0 = toInt(separatedNumbers[0]);
		int n1 = toInt(separatedNumbers[1]);
		int n2 = toInt(separatedNumbers[2]);

		if (separatedNumbers[2].length() < 1)
		{
			LogSystem("ParseNVIDIADriver : ERROR format[2]");
			return false;
		}

		const std::wstring &s = separatedNumbers[2];
		std::wstring sLastNumber;
		sLastNumber += s[s.length() - 1];
		int n2_lastNumber = toInt(sLastNumber);
		int n3 = toInt(separatedNumbers[3]);

		publicVersionOut = n3 + n2_lastNumber * 10000;
		return true;
	}
	catch (...)
	{
		LogSystem("ParseNVIDIADriver : ERROR Exception");
	}

	return false;
}


bool checkCompatibility_driver(std::wstring &retMessage)
{
	LogSystem("checkCompatibility_driver begin...");
	retMessage = L"";

	const int Supported_AMD_driverMajor = 15;
	const int Supported_AMD_driverMinor = 301;

	const std::wstring Supported_NVIDIA_driver_string = L"368.39";
	const int Supported_NVIDIA_driver = 36839;

	GetSystemInfo();

	int driverCompatible = 0; // 0=not able to know version    1=not compatible    2=compatible
	bool hardwareIsAMD = false;
	bool hardwareIsNV = false;

	try
	{
		assert(g_systemInfo.gpuDriver.size() == g_systemInfo.gpuName.size());
		for (size_t i = 0; i < g_systemInfo.gpuDriver.size(); i++)
		{
			const std::wstring &driver = g_systemInfo.gpuDriver[i];
			const std::wstring &name = g_systemInfo.gpuName[i];

			if (name.find(L"AMD") != std::string::npos)
			{
				hardwareIsAMD = true;
				if (driver.length() >= std::wstring(L"XX.XXX").length() && driver[2] == '.')
				{
					const std::wstring strVersionMajor = driver.substr(0, 2);
					const std::wstring strVersionMinor = driver.substr(3, 3);

					int VersionMajorInt = toInt(strVersionMajor);
					int VersionMinorInt = toInt(strVersionMinor);

					if (VersionMajorInt < Supported_AMD_driverMajor)
					{
						driverCompatible = 1;
						LogSystem("checkCompatibility_driver : WARNING: driver not compatible because major.");
					}
					else if (VersionMajorInt == Supported_AMD_driverMajor && VersionMinorInt < Supported_AMD_driverMinor)
					{
						driverCompatible = 1;
						LogSystem("checkCompatibility_driver : WARNING: driver not compatible because minor.");
					}
					else
					{
						driverCompatible = 2;
						LogSystem("checkCompatibility_driver : AMD driver compatible");
						break;
					}
				}
				else
				{
					LogSystem("checkCompatibility_driver : WARNING: bad AMD driver format");
				}
			}
			else if (name.find(L"NVIDIA") != std::string::npos)
			{
				hardwareIsNV = true;

				int nvidiaPublicDriver = 0;
				bool successParseNVdriver = ParseNVIDIADriver(driver, nvidiaPublicDriver);

				if (successParseNVdriver)
				{
					LogSystem("checkCompatibility_driver : nvidiaPublicDriver = %d", nvidiaPublicDriver);

					if (nvidiaPublicDriver < Supported_NVIDIA_driver)
					{
						driverCompatible = 1;
						LogSystem("checkCompatibility_driver : WARNING: NV driver too old.");
					}
					else
					{
						driverCompatible = 2;
						LogSystem("checkCompatibility_driver : NVIDIA driver compatible");
						break;
					}
				}
				else
				{
					LogSystem("checkCompatibility_driver : WARNING: bad NVIDIA driver format");
				}
			}
			else
			{
				LogSystem("checkCompatibility_driver : WARNING: No AMD or NV Found.");
			}
		}
	}
	catch (...)
	{
		LogSystem("ParseNVIDIADriver : ERROR Exception");
	}


	if (driverCompatible == 1)
	{
		retMessage = L"Your Graphic driver seems incompatible with Radeon ProRender.\r\n";

		if (hardwareIsAMD)
		{
			wchar_t buffer[MAX_PATH];
			wsprintf(buffer, L"%d.%d", Supported_AMD_driverMajor, Supported_AMD_driverMinor);
			retMessage += L"For AMD, you need " + std::wstring(buffer) + L" or higher.";
		}
		else if (hardwareIsNV)
		{
			retMessage += L"For NVIDIA, you need " + Supported_NVIDIA_driver_string + L" or higher.";
		}

		LogSystem("!Warning: %s", WstringToString(retMessage).c_str());
		return false;
	}

	LogSystem("checkCompatibility_driver end.");
	return true;
}
