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


