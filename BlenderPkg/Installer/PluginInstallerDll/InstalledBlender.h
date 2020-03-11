/**********************************************************************
* Copyright 2020 Advanced Micro Devices, Inc
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* 
*     http://www.apache.org/licenses/LICENSE-2.0
* 
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
********************************************************************/
#pragma once


#include "stdafx.h"
#include "common.h"

#pragma comment(lib, "Version.lib")


/*
Checks and keeps Blender installation info to simplify multiple installations info handling.
*/
class InstalledBlender
{
public:
	bool compatible{ false };
	long versionMajor{ -1 };
	long versionMinor{ -1 };
	std::wstring installFolder{ L"" };
	std::wstring blenderPath{ L"" };

	InstalledBlender() {};
	InstalledBlender(const std::wstring& filePath)
		/* Construct Blender installation info from file */
	{
		std::wstring blenderInstallFolder = filePath;
		long major;
		long minor;

		this->compatible = getBlenderVersionFromFile(filePath, major, minor);
		if (!this->compatible)
			return;

		// Store compatible version info for furture use
		this->versionMajor = major;
		this->versionMinor = minor;

		this->blenderPath = filePath;

		blenderInstallFolder.resize(blenderInstallFolder.length() - strlen("blender.exe"));
		this->installFolder = blenderInstallFolder;
	};

	bool isValid()
		/* Check if stored file info is still valid */
	{
		long major;
		long minor;
		if (!fileExists(this->blenderPath))
			return false;

		auto stillCompatible = getBlenderVersionFromFile(this->blenderPath, major, minor);
		if (stillCompatible && major == this->versionMajor && minor == this->versionMinor)
			return true;

		return false;
	}

	std::wstring versionName()
		/* Use '#major#minor' as internal version name for version #major.#minor */
	{
		return std::wstring(std::to_wstring(this->versionMajor) + std::to_wstring(this->versionMinor));
	}

	std::wstring versionFolderName()
		/* Blender folders are using '#major.#minor' name format for version #major.#minor */
	{
		return std::wstring(std::to_wstring(this->versionMajor) + L"." + std::to_wstring(this->versionMinor));
	}

	std::wstring wstr()
		/* wstring representation of stored data */
	{
		std::wstring text{ this->compatible ? L"version " : L"[incompatible] version" };
		text += std::to_wstring(this->versionMajor) + L"." + std::to_wstring(this->versionMinor);
		text += L"; folder '" + this->installFolder + L"'";
		return text;
	}

private:
	bool getBlenderVersionFromFile(const std::wstring& filePath, long& major, long& minor)
		/* Use Win API to get executable file version numbers */
	{
		major = 0;
		minor = 0;
		DWORD dwDummy;
		DWORD size = GetFileVersionInfoSize(filePath.c_str(), &dwDummy);
		if (size == 0) {
			return false;
		}

		LPBYTE pInfo = new BYTE[size];
		DWORD result = GetFileVersionInfo(filePath.c_str(), 0, size, pInfo);
		if (result == 0) {
			delete[] pInfo;
			return false;
		}

		UINT uLen;
		VS_FIXEDFILEINFO* pFileInfo;
		result = VerQueryValue(pInfo, L"\\", (LPVOID*)&pFileInfo, &uLen);
		if (result == 0) {
			delete[] pInfo;
			return false;
		}

		DWORD dwFileVersionMS = pFileInfo->dwFileVersionMS;
		DWORD dwFileVersionLS = pFileInfo->dwFileVersionLS;
		delete[] pInfo;

		// Version number stored as #1.#2.#3.#4 => convert to #1.#2#3. Ignore build number #4
		DWORD dwLeftMost = HIWORD(dwFileVersionMS);
		DWORD dwSecondLeft = LOWORD(dwFileVersionMS);
		DWORD dwSecondRight = HIWORD(dwFileVersionLS);
		DWORD dwRightMost = LOWORD(dwFileVersionLS);

		major = dwLeftMost;
		minor = dwSecondLeft * 10 + dwSecondRight;

		return major >= BLENDER_MAJOR_VERSION_REQ && minor >= BLENDER_MINOR_VERSION_REQ;
	}

	bool fileExists(const std::wstring& filePath)
	{
		DWORD dwAttrib = GetFileAttributes(filePath.c_str());

		return (dwAttrib != INVALID_FILE_ATTRIBUTES &&
			!(dwAttrib & FILE_ATTRIBUTE_DIRECTORY));
	}
};
