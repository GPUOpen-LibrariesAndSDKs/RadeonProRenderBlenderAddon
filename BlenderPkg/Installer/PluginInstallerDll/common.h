#pragma once


// Blender version constants
const int BLENDER_MAJOR_VERSION_REQ = 2;
const int BLENDER_MINOR_VERSION_REQ = 80;

const std::vector<std::wstring> KNOWN_SUPPORTED_VERSIONS{ L"280", L"281", L"282" };




inline std::wstring getVersionRegistryKeyName(const std::wstring& versionName)
{
	std::wstring keyName{ L"blender_path_" + versionName };
	return keyName;
}


inline std::wstring getVersionFolderPropertyName(const std::wstring& versionName)
{
	std::wstring propertyName{ L"BLENDER_" + versionName + L"_INSTALL_FOLDER" };
	return propertyName;
}
