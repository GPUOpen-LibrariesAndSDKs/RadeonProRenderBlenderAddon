#include "stdafx.h"
#include <msi.h>
#include <msiquery.h>
#include <Shellapi.h>
#include "checkCompatibility.h"
#include "../../../.sdk/rpr/inc/RadeonProRender.h" // for get FR_API_VERSION
#include <comdef.h>
#include <Commdlg.h>
#include <Wbemidl.h>
#include <stdlib.h>

#include "common.h"
#include "PythonScriptsExecution.h"

#pragma comment(lib, "msi.lib")
#pragma comment(lib, "Shell32.lib")
#pragma comment(lib, "Ole32.lib")
#pragma comment(lib, "Version.lib")
#pragma comment(lib, "Comdlg32.lib")
#pragma comment(lib, "Advapi32.lib")


#define VERSION_MAJOR(ver) ((ver) >> 28)
#define VERSION_MINOR(ver) ((ver) & 0xfffffff)

const TCHAR REG_KEY_RPR_BLENDER_NAME[] = L"SOFTWARE\\AMD\\Radeon ProRender for Blender";
const HKEY  REG_KEY_ROOT = HKEY_CURRENT_USER;


/*
How it should work:

===== INSTALL =====
Install preparation  ("collectInstalledBlenderEntries"):

1. Check if data is already stored in MSI  ("readBlenderInfoFromMSI")
1.1. For every found version
1.1.1. create info structure
1.1.2. check if structure is valid installation info
= 1.1.1. create info classcheck for presence  ("isFilePresent")
= 1.1.2. get version  ("getBlenderFileVersion")
= 1.1.3. fill appropriate structure
2. If none found find via WMI methods  ("findInstalledBlenderEntriesByWMI")
2.1. For every found version
2.1.1. check for presence  ("isFilePresent")
2.1.2. get version  ("getBlenderFileVersion")
2.1.3. fill appropriate structure
2.1.4. Store path and presence flag in MSI  ("storeBlenderInfoToMSI")
3. If none found ask user to point at the blender executable file  ("askUserForBlenderExecutable")
3.1. get version  ("getBlenderFileVersion")
3.2. fill appropriate structure
3.3. Store path and presence flag in MSI  ("storeBlenderInfoToMSI")
4. If no compatible version found quit install

Install  ("postInstall")
1. Read data from MSI  ("readBlenderInfoFromMSI")
2. For every found version
2.1. Check for file presence  ("isFilePresent")
2.2. Call "boto3 install" script via Python  ("executePythonScript", usePythonExecutable=true)
2.3. Call "plugin register" script via Blender  ("executePythonScript")
2.4. Catch any exception raised by script execution (is it really needed?)
2.5. Add registry entry for Blender version  ("storeRegistryEntry")

===== UNINSTALL =====
Uninstall preparation  ("getInstalledBlenderEntriesForUninstall")
1. Read data from registry  ("readBlenderPathFromRegistry")
1.1. For each entry check info validity
1.2. Store path and presence infos in MSI for furture use  ("storeBl enderInfoToMSI")

Uninstall  ("postUninstall")
1. Load install info from MSI  ("readBlenderInfoFromMSI")
2. For each found entry
2.1. Check for file presence  ("isFilePresent")
2.2. Call "plugin disable" script via Blender  ("executePythonScript")
2.3. Wait some time so the DLLs are freed
2.4. Call "plugin remove" script via Blender  ("executePythonScript")
2.5. Catch any subprocess exception, quit removal if script call failed
2.6. Remove registry entry for Blender version  ("removeRegistryEntry")
*/


extern "C" __declspec(dllexport) UINT hardwareCheck(MSIHANDLE hInstall) {
	/* Check for hardware and OpenCL driver compatibility */
	LogSystem("hardwareCheck...");
	std::wstring hw_message;
	bool hw_res = checkCompatibility_hardware(hw_message);

	std::wstring sw_message;
	bool sw_res = checkCompatibility_driver(sw_message);

	MsiSetProperty(hInstall, L"HARDWARECHECK_RESULT", hw_res ? L"1" : L"0");
	MsiSetProperty(hInstall, L"SOFTWARECHECK_RESULT", sw_res ? L"1" : L"0");

	if (!hw_res || !sw_res)
	{
		std::wstring text;
		if (!hw_res)
			text += L"\r\n" + hw_message;

		if (!sw_res)
			text += L"\r\n" + sw_message;

		std::wstring s = L"Detail info:" + text;

		MsiSetProperty(hInstall, L"CHECK_RESULT_TEXT", s.c_str());
	}

	LogSystem("hardwareCheck finished.");
	return ERROR_SUCCESS;
}


std::wstring getBlenderPathByUser()
	/* Open dialog and ask user to point out at the blender.exe */
{
	LogSystem("getBlenderPathByUser...");

	OPENFILENAME openFileName;
	TCHAR szFileName[MAX_PATH] = L"";

	ZeroMemory(&openFileName, sizeof(openFileName));

	openFileName.lStructSize = sizeof(openFileName);
	openFileName.hwndOwner = NULL;
	openFileName.lpstrFilter = L"Blender executable (blender.exe)\0blender.exe\0All Files (*.*)\0*.*\0";
	openFileName.lpstrFile = szFileName;
	openFileName.nMaxFile = MAX_PATH;
	openFileName.Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_HIDEREADONLY | OFN_PATHMUSTEXIST;

	openFileName.lpstrTitle = L"Please select the Blender executable file";

	if (!GetOpenFileName(&openFileName))
	{
		LogSystem("GetOpenFileName returned false");
		return std::wstring();
	}

	std::wstring res = std::wstring(openFileName.lpstrFile);
	LogSystem("GetOpenFileName: %s", WstringToString(res).c_str());
	return res;
}


std::wstring getAddonZipPath(MSIHANDLE hInstall)
{
	/* Full addon.zip path */
	TCHAR installFolder[MAX_PATH];
	DWORD keyLen = MAX_PATH;

	keyLen = MAX_PATH;
	MsiGetProperty(hInstall, L"INSTALLFOLDER", installFolder, &keyLen);
	std::wstring addonZipPath = std::wstring(installFolder) + L"addon.zip";
	LogSystem("getAddonArchivePath: %s", WstringToString(addonZipPath).c_str());

	return addonZipPath;
}


std::wstring getBlenderPathFromEnv()
	/* Use debug environment variable value */
{
	LogSystem("getBlenderPathFromEnv...");
	size_t n;
	wchar_t szFileName[MAX_PATH] = L"";
	_wgetenv_s(&n, szFileName, MAX_PATH, L"BLENDER_28X_EXE");
	auto result = std::wstring(szFileName);

	LogSystem("getBlenderPathFromEnv finished.");
	return result;
}


inline bool isVersionMarkededForInstall(MSIHANDLE hInstall, const std::wstring& versionName)
/* Check if user has selected(by default) Blender version as "installed addon for it" */
{
	// TODO use feature install level check here

	return true;
}


void storeBlenderInfoToMSI(MSIHANDLE hInstall, InstalledBlender& info)
/* Store by version name */
{
	LogSystem("storeBlenderInfoToMSI...");
	auto versionName = info.versionName();

	auto propertyFolderName = getVersionFolderPropertyName(versionName);

	LogSystem("  %s: %s", WstringToString(propertyFolderName).c_str(), WstringToString(info.installFolder).c_str());
	MsiSetProperty(hInstall, propertyFolderName.c_str(), info.installFolder.c_str());

	LogSystem("storeBlenderInfoToMSI finished.");
}


std::vector<InstalledBlender> readBlenderInfoFromMSI(MSIHANDLE hInstall)
/* Retrieve by target versions */
{
	LogSystem("readBlenderInfoFromMSI...");
	std::vector<InstalledBlender> entries;

	for (auto const& versionName : KNOWN_SUPPORTED_VERSIONS)
	{
		TCHAR blenderInstall[MAX_PATH];
		DWORD keyLen = MAX_PATH;

		auto propertyFolder = getVersionFolderPropertyName(versionName);

		// look for appropriate info in MSI
		auto res = MsiGetProperty(hInstall, propertyFolder.c_str(), blenderInstall, &keyLen);
		if (res != ERROR_SUCCESS)
		{
			LogSystem("  unable to find MSI entry for version '%s'", WstringToString(versionName).c_str());
			continue;
		}

		std::wstring blenderInstallFolder = blenderInstall;
		std::wstring installPath{ blenderInstallFolder + L"blender.exe" };
		LogSystem("  readBlenderInfoFromMSI[%s]: %s",
			WstringToString(versionName).c_str(), WstringToString(blenderInstallFolder).c_str());

		// store info entry if valid
		InstalledBlender info{ installPath };

		if (info.isValid())
			entries.push_back(info);
	}

	LogSystem("readBlenderInfoFromMSI finished.");
	return entries;
};


std::vector<InstalledBlender> parseInstallInfoEnumeratorForCompatibleVersions(IEnumWbemClassObject* pEnumerator)
/* Iterate each found entry, check for compatibile Blender versions */
{
	std::vector<InstalledBlender> entries;

	while (pEnumerator)
	{
		IWbemClassObject* pclsObj = NULL;
		ULONG uReturn = 0;

		LogSystem("pEnumerator->Next...");
		HRESULT hr = pEnumerator->Next(WBEM_INFINITE, 1,
			&pclsObj, &uReturn);

		if (0 == uReturn)
		{
			LogSystem("pEnumerator is empty");
			break;
		}

		LogSystem("pEnumerator->Next ok.");

		VARIANT vtProp_BlenderInstallFolder;
		hr = pclsObj->Get(L"InstallLocation", 0, &vtProp_BlenderInstallFolder, 0, 0);
		std::wstring installFolder = vtProp_BlenderInstallFolder.bstrVal;
		LogSystem("Found Blender Install Folder: %S", vtProp_BlenderInstallFolder.bstrVal);
		VariantClear(&vtProp_BlenderInstallFolder);

		std::wstring blenderPath{ installFolder + L"blender.exe" };
		LogSystem("  blenderPath: '%s'", WstringToString(blenderPath).c_str());

		/* create entry info */
		InstalledBlender entry{ blenderPath };
		/* check compatibility */
		if (entry.isValid())
		{
			LogSystem("Valid installed Blender version found: %s", WstringToString(entry.wstr()).c_str());
			entries.push_back(entry);
		}

		pclsObj->Release();
		pclsObj = NULL;
	}

	return entries;
}


std::vector<InstalledBlender> findInstalledBlenderEntriesByWMI()
/* Look for Blender installation in Windows installed application info */
{
	LogSystem("findInstalledBlenderEntriesByWMI...");
	std::vector<InstalledBlender> entries;

	/* Move adapted 'parseBlenderInstallationsInfo' code here */
	HRESULT hres = CoInitializeEx(0, COINIT_MULTITHREADED);
	if (!FAILED(hres))
	{
		LogSystem("   parseBlenderInstallationsInfo Step 1 - ok");

		IWbemLocator* pLoc = NULL;

		hres = CoCreateInstance(
			CLSID_WbemLocator,
			0,
			CLSCTX_INPROC_SERVER,
			IID_IWbemLocator, (LPVOID*)&pLoc);

		if (!FAILED(hres))
		{
			LogSystem("   parseBlenderInstallationsInfo Step 2 - ok");

			IWbemServices* pSvc = NULL;
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

			if (!FAILED(hres))
			{
				LogSystem("   parseBlenderInstallationsInfo Step 3 - ok");
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

				if (!FAILED(hres))
				{
					LogSystem("   parseBlenderInstallationsInfo Step 4 - ok");

					IEnumWbemClassObject* pEnumerator = NULL;
					hres = pSvc->ExecQuery(
						bstr_t("WQL"),
						bstr_t("SELECT * FROM Win32_Product WHERE Name LIKE 'Blender'"),
						WBEM_FLAG_FORWARD_ONLY | WBEM_FLAG_RETURN_IMMEDIATELY,
						NULL,
						&pEnumerator);

					if (!FAILED(hres))
					{
						LogSystem("   parseBlenderInstallationsInfo Step 5 - ok");

						/* Iterate each found entry, check for compatibility */
						entries = parseInstallInfoEnumeratorForCompatibleVersions(pEnumerator);

						// cleanup
						pEnumerator->Release();
						pEnumerator = NULL;
					}
					else
						LogSystem("parseBlenderInstallationsInfo: FAILED - pSvc->ExecQuery 1");
				}
				else
					LogSystem("parseBlenderInstallationsInfo: FAILED - CoSetProxyBlanket");

				pSvc->Release();
				pSvc = NULL;
			}
			else
				LogSystem("parseBlenderInstallationsInfo: FAILED - pLoc->ConnectServer");

			pLoc->Release();
			pLoc = NULL;
		}
		else
			LogSystem("parseBlenderInstallationsInfo: FAILED - CoCreateInstance");

		CoUninitialize();
	}
	else
		LogSystem("parseBlenderInstallationsInfo: FAILED - CoInitializeEx");

	LogSystem("findInstalledBlenderEntriesByWMI finished.");
	return entries;
}


InstalledBlender askUserForBlenderExecutable()
{
	LogSystem("askUserForBlenderExecutable...");
	auto blenderPath = getBlenderPathByUser();
	auto result = InstalledBlender(blenderPath);

	LogSystem("askUserForBlenderExecutable finished.");
	return result;
}


extern "C" __declspec(dllexport) UINT collectInstalledBlenderEntries(MSIHANDLE hInstall)
{
	LogSystem("collectInstalledBlenderEntries...");

	// look if info is already stored in MSI
	auto entries = readBlenderInfoFromMSI(hInstall);

	if (!entries.empty())
		return ERROR_SUCCESS;

	// Look for installation info,
	entries = findInstalledBlenderEntriesByWMI();
	if (entries.empty())
	{
		// The last hope - ask user for the exact Blender location
		auto blenderInfo = askUserForBlenderExecutable();
		if (blenderInfo.compatible)
			entries.push_back(blenderInfo);
	}

	// couldn't proceed any furter without correct Blender version installed or unpacked
	if (entries.empty())
	{
		LogSystem("collectInstalledBlenderEntries: no Blender installations found, can not proceed");
		return ERROR_FILE_NOT_FOUND;
	}

	// store any valid info to MSI properties
	for (auto value : entries)
	{
		auto text{ WstringToString(value.wstr()).c_str() };
		LogSystem("  storing entry info: '%s'", text);
		storeBlenderInfoToMSI(hInstall, value);
	}

	return ERROR_SUCCESS;
}


void removeBlenderPathFromRegistry(const std::wstring& versionName)
/* Remove version path entry from addon registry section */
{
	LogSystem("removeBlenderPathFromRegistry [%s]...", WstringToString(versionName).c_str());
	auto keyValueName = getVersionRegistryKeyName(versionName);

	HKEY key;

	if (RegOpenKeyEx(REG_KEY_ROOT, REG_KEY_RPR_BLENDER_NAME, 0, KEY_ALL_ACCESS, &key) != ERROR_SUCCESS)
	{
		LogSystem("RPR for Blender addon registry key not found");
		return;
	}

	RegDeleteValue(key, keyValueName.c_str());

	LogSystem("removeBlenderPathFromRegistry finished.");
}


void writeBlenderPathToRegistry(const std::wstring& versionName, const std::wstring& path)
/* Store path to Blender version used for addon installation. Info used for uninstall */
{
	HKEY	key;
	DWORD	dwDisposition;
	LogSystem("writeBlenderPathToRegistry [%s]...", WstringToString(versionName).c_str());

	auto keyValueName = getVersionRegistryKeyName(versionName);

	if (RegCreateKeyEx(REG_KEY_ROOT, REG_KEY_RPR_BLENDER_NAME, 0, NULL, REG_OPTION_NON_VOLATILE, KEY_ALL_ACCESS, NULL, &key, &dwDisposition) != ERROR_SUCCESS)
		return;

	RegSetValueEx(key, keyValueName.c_str(), 0, REG_SZ, reinterpret_cast<const BYTE*>(&path[0]), (DWORD)(path.length() * sizeof(wchar_t)));
	RegCloseKey(key);

	LogSystem("writeBlenderPathToRegistry finished.");
}


std::wstring readBlenderPathFromRegistry(const std::wstring& versionName)
/* Check if Blender version executable path is stored in addon registry for uninstall */
{
	DWORD	dwSize;
	HKEY	key;
	DWORD	dwTypeData;
	DWORD	dwDisposition;

	LogSystem("readBlenderPathFromRegistry: %s", WstringToString(versionName).c_str());

	if (RegCreateKeyEx(REG_KEY_ROOT, REG_KEY_RPR_BLENDER_NAME, 0, NULL, REG_OPTION_NON_VOLATILE, KEY_ALL_ACCESS, NULL, &key, &dwDisposition) != ERROR_SUCCESS)
		return std::wstring();

	const auto keyName = getVersionRegistryKeyName(versionName);

	if (RegQueryValueEx(key, keyName.c_str(), NULL, &dwTypeData, NULL, &dwSize) != ERROR_SUCCESS)
	{
		RegCloseKey(key);
		return std::wstring();
	}

	if (dwTypeData != REG_SZ)
	{
		RegCloseKey(key);
		return std::wstring();
	}

	std::wstring value(dwSize / sizeof(wchar_t), L'\0');
	if (RegQueryValueEx(key, keyName.c_str(), NULL, NULL, reinterpret_cast<BYTE*>(&value[0]), &dwSize) == ERROR_SUCCESS)
	{
		size_t firstNull = value.find_first_of(L'\0');
		if (firstNull != std::string::npos)
			value.resize(firstNull);
	}
	else
	{
		value = L"";
	}

	RegCloseKey(key);
	LogSystem("readBlenderPathFromRegistry result: '%s'", WstringToString(value).c_str());
	return value;
}


std::vector<InstalledBlender> getPluginInstallsFromRegistry(MSIHANDLE hInstall)
/* Collect addon installation info from Windows Registry, check if stored path is still correct, keep compatible */
{
	std::vector<InstalledBlender> result;

	LogSystem("getPluginInstallsFromRegistry...");

	// TODO: discuss if there is a better way to get list of all supported versions
	for (const auto versionName : KNOWN_SUPPORTED_VERSIONS)
	{
		// use readBlenderPathFromRegistry
		const auto path = readBlenderPathFromRegistry(versionName);

		InstalledBlender info(path);
		LogSystem("    registry entry-based info: %s", WstringToString(info.wstr()).c_str());

		// Note: couldn't do anything if user renamed/moved folder by the time uninstall called. Ignore such invalid entries.
		// Should installer remove such registry values on uninstall?
		if (info.isValid())
			result.push_back(info);
	}

	LogSystem("getPluginInstallsFromRegistry finished.");
	return result;
}


extern "C" __declspec(dllexport) UINT getBlenderEntriesForUninstall(MSIHANDLE hInstall)
/* Check if installed versions info is stored in MSI. If none found load it from registry and store in MSI. */
{
	LogSystem("getBlenderEntriesForUninstall...");

	auto info = readBlenderInfoFromMSI(hInstall);

	if (info.empty())
	{
		// load from registry
		info = getPluginInstallsFromRegistry(hInstall);

		// store any valid info to MSI properties
		for (auto& value : info)
		{
			// assuming path with executable is stored in registry value
			LogSystem("  storing entry info: '%s'", WstringToString(value.wstr()).c_str());
			storeBlenderInfoToMSI(hInstall, value);
		}
	}

	LogSystem("getBlenderEntriesForUninstall finished.");
	return ERROR_SUCCESS;
}


extern "C" __declspec(dllexport) UINT postInstall(MSIHANDLE hInstall)
/* For each actual compatible Blender version install and enable addon in Blender, write info to registry */
{
	LogSystem("postInstall..");

	auto info = readBlenderInfoFromMSI(hInstall);
	if (info.empty())
	{
		// No registry entry corresponding to compatible Blender version found. Could be user has removed any of it.
		// Can't do anything about it.
		LogSystem("Unable to find any compatible Blender version to install addon on.");
		return ERROR_SUCCESS;
	}

	auto tempFolder = getTempFolder();
	auto addonZipPath = getAddonZipPath(hInstall);
	const auto pyBlenderPip = createInstallPipScript(tempFolder);  // TODO: discuss if this step is needed with latest addon.zip changes
	const auto pyActivateAddon = createActivationScript(tempFolder, addonZipPath);

	for (auto entry : info)
	{
		auto versionName = entry.versionName();
		auto versionFolderName = entry.versionFolderName();
		auto blenderPath = entry.blenderPath;

		LogSystem("  installing addon for Blender version %s...", WstringToString(versionFolderName).c_str());
		// apply version post install
		disableBlenderAddOn(tempFolder, blenderPath, versionFolderName);

		executeBlenderScript(blenderPath, versionFolderName, pyBlenderPip, true);
		executeBlenderScript(blenderPath, versionFolderName, pyActivateAddon);

		// write registry entry for this version
		writeBlenderPathToRegistry(versionName, blenderPath);

		LogSystem("  version '%s' install finished.", WstringToString(versionFolderName).c_str());
	}

	LogSystem("postInstall finished.");

	return ERROR_SUCCESS;
}


extern "C" __declspec(dllexport) UINT postUnInstall(MSIHANDLE hInstall)
{
	// Should it be done in MODIFY/repair mode?
	LogSystem("postUnInstall..");

	auto info = getPluginInstallsFromRegistry(hInstall);
	if (info.empty())
	{
		// No registry entry corresponding to compatible Blender version found. Could be user has removed any of it.
		// Shikata ga nai.
		LogSystem("Unable to find any registry entry or compatible Blender on saved path. Nothing to remove.");
		return ERROR_SUCCESS;
	}

	auto tempFolder = getTempFolder();

	for (auto entry : info)
	{
		auto blenderPath = entry.blenderPath;
		auto versionName = entry.versionName();
		auto versionFolderName = entry.versionFolderName();
		LogSystem(" removing version %s", WstringToString(versionFolderName).c_str());

		disableBlenderAddOn(tempFolder, blenderPath, versionFolderName);

		removeBlenderPathFromRegistry(versionName);
	}

	LogSystem("postUnInstall finished.");

	return ERROR_SUCCESS;
}
