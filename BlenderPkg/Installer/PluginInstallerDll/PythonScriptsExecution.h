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


void executeBlenderScript(const std::wstring& blenderPath,
	const std::wstring& versionFolderName,
	const std::wstring& scriptFile,
	bool purePython = false)
	/* Execute Blender script.
	Use Python executable if purePython is true.
	Use Blender otherwise. */
{
	std::wstring pythonPath;
	std::wstring cmdParams;
	std::wstring outFile = scriptFile + L".txt";

	LogSystem("executeBlenderScript [%s], path: %s", WstringToString(versionFolderName).c_str(), WstringToString(blenderPath).c_str());

	if (purePython)
	{
		pythonPath = blenderPath.substr(0, blenderPath.find_last_of(L"/\\")) + L"/" + versionFolderName.c_str() + L"/python/bin/python.exe";
		cmdParams = pythonPath + L" \"" + scriptFile + L"\"";

		SHELLEXECUTEINFO si = { 0 };

		si.cbSize = sizeof(SHELLEXECUTEINFO);
		si.fMask = SEE_MASK_NOCLOSEPROCESS;
		si.hwnd = NULL;
		si.lpVerb = L"runas";
		si.lpFile = pythonPath.c_str();
		si.lpParameters = scriptFile.c_str();
		si.lpDirectory = NULL;
		si.nShow = SW_SHOWMINIMIZED;
		si.hInstApp = NULL;

		BOOL ret = ShellExecuteEx(&si);
		if (ret)
		{
			WaitForSingleObject(si.hProcess, INFINITE);
			CloseHandle(si.hProcess);
		}
	}
	else
	{
		cmdParams = blenderPath + L" -b --python \"" + scriptFile + L"\"";

		SECURITY_ATTRIBUTES sa;
		sa.nLength = sizeof(sa);
		sa.lpSecurityDescriptor = NULL;
		sa.bInheritHandle = TRUE;

		HANDLE h = CreateFile(outFile.c_str(),
			FILE_APPEND_DATA, FILE_SHARE_WRITE,
			&sa,
			OPEN_ALWAYS,
			FILE_ATTRIBUTE_NORMAL,
			NULL);

		PROCESS_INFORMATION pi;
		STARTUPINFO si;
		BOOL ret = FALSE;
		DWORD flags = CREATE_NO_WINDOW;

		ZeroMemory(&pi, sizeof(PROCESS_INFORMATION));
		ZeroMemory(&si, sizeof(STARTUPINFO));
		si.cb = sizeof(STARTUPINFO);
		si.dwFlags |= STARTF_USESTDHANDLES;
		si.hStdInput = h;
		si.hStdError = h;
		si.hStdOutput = h;

		LogSystem("executeBlenderScript : %s", WstringToString(cmdParams).c_str());
		ret = CreateProcess(NULL, &cmdParams[0], NULL, NULL, TRUE, flags, NULL, NULL, &si, &pi);

		if (ret)
		{
			WaitForSingleObject(pi.hProcess, INFINITE);

			CloseHandle(pi.hProcess);
			CloseHandle(pi.hThread);
		}
	}

	LogSystem("executeBLenderScript finished.");
}


/* Python script files creation */

std::wstring getTempFolder()
{
	TCHAR tempFolder[MAX_PATH];
	DWORD keyLen = MAX_PATH;

	GetTempPath(keyLen, tempFolder);

	return std::wstring(tempFolder);
}


std::wstring createInstallPipScript(const std::wstring& tempFolder)
{
	/* PIP+boto3 installer script */
	LogSystem("createInstallPipScript...");

	std::wstring scriptPath = tempFolder + L"blender_pip.py";
	std::fstream scriptFile(scriptPath, std::ios::out);
	scriptFile <<
		R""""(
import sys
import subprocess
import urllib.request
import tempfile
import os

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
python_exe = sys.executable

def try_install_pip():
	try:
		import pip
		print("Module pip is already installed")
		return

	except ImportError:
		pass

	print("Downloading get-pip.py")
	file_name = tempfile.gettempdir() + "/get-pip.py"
	urllib.request.urlretrieve(GET_PIP_URL, file_name)

	try:
		print("Installing pip")
		subprocess.check_call([python_exe, file_name])

	finally:
		os.remove(file_name)

def try_install_boto3():
	try:
		import boto3
		print("Module boto3 is already installed")
		return

	except ImportError:
		pass

	print("Installing boto3")
	subprocess.check_call([python_exe, '-m', 'pip', 'install', 'boto3'])

try_install_pip()
try_install_boto3()
)"""";
	scriptFile.close();

	LogSystem("createInstallPipScript finished.");
	return scriptPath;
}


std::wstring createActivationScript(const std::wstring& tempFolder, const std::wstring& addonZipPath)
{
	/* Register and activate plugin in Blender */
	LogSystem("createActivationScript...");

	std::wstring scriptPath = tempFolder + L"enable_rpr.py";
	std::fstream scriptFile(scriptPath, std::ios::out);
	scriptFile <<
		R""""(
import bpy
from pathlib import Path
bpy.ops.preferences.addon_install(overwrite=True, filepath=r')"""" << WstringToString(addonZipPath) << R""""(')
bpy.ops.preferences.addon_enable(module='rprblender')
bpy.ops.wm.save_userpref()
)"""";
	scriptFile.close();

	LogSystem("createActivationScript finished.");
	return scriptPath;
}


std::wstring createDisableAddonScript(const std::wstring& tempFolder)
{
	LogSystem("createDisableAddonScript...");

	const std::wstring pyScriptDisable{ tempFolder + L"disable_rpr.py" };

	std::fstream oFile(pyScriptDisable, std::ios::out);
	oFile <<
		R""""(
import bpy
bpy.ops.preferences.addon_disable(module='rprblender')
bpy.ops.wm.save_userpref()
)"""";
	oFile.close();

	LogSystem("createDisableAddonScript finished");
	return pyScriptDisable;
}


std::wstring createRemoveAddonScript(const std::wstring& tempFolder)
{
	LogSystem("createDicreateRemoveAddonScriptsableAddonScript...");

	const std::wstring pyScriptRemove{ tempFolder + L"remove_rpr.py" };

	std::fstream oFile(pyScriptRemove, std::ios::out);
	oFile <<
		R""""(
import bpy
bpy.ops.preferences.addon_remove(module='rprblender')
bpy.ops.wm.save_userpref()
)"""";
	oFile.close();

	LogSystem("createRemoveAddonScript finished");
	return pyScriptRemove;
}


void disableBlenderAddOn(const std::wstring& tempFolder, const std::wstring& blenderPath, const std::wstring& versionFolderName)
{
	const auto pyScriptDisable = createDisableAddonScript(tempFolder);
	const auto pyScriptRemove = createRemoveAddonScript(tempFolder);

	executeBlenderScript(blenderPath, versionFolderName, pyScriptDisable);
	Sleep(30000);
	executeBlenderScript(blenderPath, versionFolderName, pyScriptRemove);

	LogSystem("disableBlenderAddOn finished.");
}
