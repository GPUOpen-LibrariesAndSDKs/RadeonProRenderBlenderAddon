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

#include <iostream>
#include <fstream>
#include <string>
#include <array>

using namespace std;

extern ofstream logfile;
extern ostream *outmsg;

class formSelect
{
private:

public:
	// Constructor
	formSelect() : m_totalSuccess (true) {};

	// Destructor
	~formSelect () {};

	void formSelect_Shown(void);
	bool checkCompatibility_hardware(void);
	bool checkCompatibility_driver(void);
	bool checkCompatibility_Tahoe(void);
	//this function will fill  g_systemInfo
	void GetSystemInfo_(void);
	void WstringToString(const std::wstring& wstr, std::string& astr);
	void StringToWstring(std::wstring &wstr, const std::string &astr);
	void BuildRegistrationLink(void);

//	std::array<bool, NB_MAYA_VERSION>& m_versionsSelectedByUser;

	bool m_totalSuccess;
}; // class formSelect


