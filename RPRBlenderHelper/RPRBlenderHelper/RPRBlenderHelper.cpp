#include "stdafx.h"
#include "RprTools.h"
#include <string>

#if defined(WIN32)

#include <cassert>
#include <vector>
#include <ShlObj.h>
#include <comdef.h>
#include <Wbemidl.h>

#pragma comment(lib, "wbemuuid.lib")


std::vector<std::wstring> split(const std::wstring &s, wchar_t delim)
{
    std::vector<std::wstring> elems;
    for (size_t p = 0, q = 0; p != s.npos; p = q)
        elems.push_back(s.substr(p + (p != 0), (q = s.find(delim, p + 1)) - p - (p != 0)));

    return elems;
}


int toInt(const std::wstring &s)
{
    wchar_t* end_ptr;
    long val = wcstol(s.c_str(), &end_ptr, 10);
    if (*end_ptr)
        throw "invalid_string";

    if ((val == LONG_MAX || val == LONG_MIN) && errno == ERANGE)
        throw "overflow";

    return val;
}

struct Device
{
    std::string name;
};

struct Driver
{
    std::wstring name;
    std::wstring deviceName;
    bool isAMD = false;
    bool isNVIDIA = false;
    bool compatible = true;
};


std::vector<Device> _devices;
std::vector<Driver> _drivers;


bool parseNVIDIADriver(const std::wstring & rawDriver, int& publicVersionOut)
{
    publicVersionOut = 0;

    try
    {
        std::vector<std::wstring> separatedNumbers = split(rawDriver, L'.');
        if (separatedNumbers.size() != 4)
            return false;

        int n0 = toInt(separatedNumbers[0]);
        int n1 = toInt(separatedNumbers[1]);
        int n2 = toInt(separatedNumbers[2]);

        if (separatedNumbers[2].length() < 1)
            return false;

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
    }

    return false;
}



void updateDriverCompatibility()
{
    std::wstring retmessage = L"";

    // This check only supports Windows.
    // Return true for other operating systems.
    const int Supported_AMD_driverMajor = 15;
    const int Supported_AMD_driverMinor = 301;

    const std::wstring Supported_NVIDIA_driver_string = L"368.39";
    const int Supported_NVIDIA_driver = 36839;

    try
    {
        for (Driver& driver : _drivers)
        {
            const std::wstring &driverName = driver.name;
            const std::wstring &deviceName = driver.deviceName;

            // Process AMD drivers.
            if (deviceName.find(L"AMD") != std::string::npos 
                || deviceName.find(L"Radeon") != std::string::npos
                )
            {
                driver.isAMD = true;

                if (driverName.length() >= std::wstring(L"XX.XXX").length() && driverName[2] == '.')
                {
                    const std::wstring strVersionMajor = driverName.substr(0, 2);
                    const std::wstring strVersionMinor = driverName.substr(3, 3);

                    int VersionMajorInt = toInt(strVersionMajor);
                    int VersionMinorInt = toInt(strVersionMinor);

                    // Driver is incompatible if the major version is too low.
                    if (VersionMajorInt < Supported_AMD_driverMajor)
                        driver.compatible = false;

                    // Driver is incompatible if the major version is okay, but the minor version is too low.
                    else if (VersionMajorInt == Supported_AMD_driverMajor && VersionMinorInt < Supported_AMD_driverMinor)
                        driver.compatible = false;

                    // The driver is compatible.
                    else
                        break;
                }
            }

            // Process NVIDIA drivers.
            else if (deviceName.find(L"NVIDIA") != std::string::npos)
            {
                driver.isNVIDIA = true;

                int nvidiaPublicDriver = 0;
                bool successParseNVdriver = parseNVIDIADriver(driverName, nvidiaPublicDriver);

                if (successParseNVdriver)
                {
                    // Driver is incompatible.
                    if (nvidiaPublicDriver < Supported_NVIDIA_driver)
                        driver.compatible = false;

                    // Driver is compatible.
                    else
                        break;
                }
            }
        }
    }
    catch (...)
    {
        // NVidia driver parse exception.
    }
}





void populateDrivers()
{
    HRESULT hres;

    IWbemLocator *pLoc = NULL;

    hres = CoCreateInstance(
        CLSID_WbemLocator,
        0,
        CLSCTX_INPROC_SERVER,
        IID_IWbemLocator, (LPVOID *)&pLoc);

    if (FAILED(hres))
        return;


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
        return;
    }

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
        return;
    }

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
        return;
    }

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

        Driver driver;

        VARIANT vtProp_driverversion;
        hr = pclsObj->Get(L"DriverVersion", 0, &vtProp_driverversion, 0, 0);
        driver.name = std::wstring(vtProp_driverversion.bstrVal);
        VariantClear(&vtProp_driverversion);

        VARIANT vtProp_name;
        hr = pclsObj->Get(L"Name", 0, &vtProp_name, 0, 0);
        driver.deviceName = std::wstring(vtProp_name.bstrVal);
        VariantClear(&vtProp_name);

        _drivers.push_back(driver);

        pclsObj->Release(); 
		pclsObj = NULL;
    }

    pEnumerator->Release(); 
	pEnumerator = NULL;
    pSvc->Release(); 
	pSvc = NULL;
    pLoc->Release();
	pLoc = NULL;
}


std::wstring get_wstring(const std::string & s)
{
    const char * cs = s.c_str();
    const size_t wn = std::mbsrtowcs(NULL, &cs, 0, NULL);

    if (wn == size_t(-1))
        return L"";

    std::vector<wchar_t> buf(wn + 1);
    const size_t wn_again = std::mbsrtowcs(buf.data(), &cs, wn + 1, NULL);

    if (wn_again == size_t(-1))
        return L"";

    assert(cs == NULL);

    return std::wstring(buf.data(), wn);
}


bool compareDeviceNames(std::wstring& a, std::wstring& b)
{
    return a == b || a.find(b) >= 0 || b.find(a) >= 0;
}


bool isDriverCompatible(std::string deviceName)
{
    // Convert to wstring for device name comparison.
    std::wstring deviceNameW = get_wstring(deviceName);

    // Find a matching device and return driver compatibility.
    for (Driver& driver : _drivers)
        if (compareDeviceNames(deviceNameW, driver.deviceName))
            return driver.compatible;

    // The driver is considered compatible if not found.
    return true;
}

#endif


std::string g_addon_path;

extern "C" EXPORT void init(const char * addon_path)
{
	g_addon_path = addon_path;
#if defined(WIN32)
    populateDrivers();
    updateDriverCompatibility();
#endif
}

extern "C" EXPORT bool check_driver(const char * deviceName)
{
#if defined(WIN32)
    return isDriverCompatible(deviceName);
#else
        return true;
#endif
}

extern "C" EXPORT RPR_TOOLS_COMPATIBILITY check_device(const rpr_char* rendererDLL, bool doWhiteListTest, RPR_TOOLS_DEVICE device, RPR_TOOLS_OS os)
{
    return  rprIsDeviceCompatible(rendererDLL, device, doWhiteListTest, os);
}
