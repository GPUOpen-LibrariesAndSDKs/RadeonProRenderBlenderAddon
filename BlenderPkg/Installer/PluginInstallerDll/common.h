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
