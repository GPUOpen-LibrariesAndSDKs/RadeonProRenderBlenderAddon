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

#include <iostream>
#include <stdio.h>
#include <string>
#include <vector>
#include <sstream>
#include <algorithm>
#include <iomanip>
#include <iterator>
#include <stdexcept>
#include <dlfcn.h>
#include <sys/utsname.h>
#include <sys/sysctl.h>

#if not defined(__APPLE__)
extern "C"{
#include <pci/pci.h>
}
#include <libdrm/drm.h>
#endif

#include <unistd.h> /* For open() */
#include <fcntl.h>  /* For O_RDONLY */
#include <sys/ioctl.h> /* For ioctl() */
#include <sys/types.h>
#include <sys/stat.h>

#if not defined(__APPLE__)
#include <CL/cl.h>
#else
#include <OpenCL/cl.h>
#include <IOKit/IOKitLib.h>
#include <CoreFoundation/CoreFoundation.h>
#endif

#include "formSelect.h"

#define RADEONPRORENDERTOOLS_DONTUSERPR

#define VERSION_MAJOR(ver) ((ver) >> 28)
#define VERSION_MINOR(ver) ((ver) & 0xfffffff)

#define USE_APPLESCRIPT

#ifndef USE_APPLESCRIPT
#define KGRN "\033[0;32;32m"
#define KRED "\033[0;32;31m"
#define KBLU "\033[0;32;34m"
#define RESET "\033[0m"
#endif

#include <RadeonProRender.h> // for get FR_API_VERSION
#include "RprTools.h"
#include "RprTools.cpp"


std::wstring g_registrationLink = L"";
const char g_activationPassword[] = "TagYourRenders#ProRender";
typedef cl_int(*PclGetPlatformIDs)(cl_uint	    /* num_entries */,
				   cl_platform_id * /* platforms */,
				   cl_uint *	    /* num_platforms */);

typedef cl_int(*PclGetPlatformInfo)(cl_platform_id   /* platform */,
				    cl_platform_info /* param_name */,
				    size_t	     /* param_value_size */,
				    void *	     /* param_value */,
				    size_t *	     /* param_value_size_ret */);

typedef cl_int(*PclGetDeviceIDs)(cl_platform_id   /* platform */,
				 cl_device_type   /* device_type */,
				 cl_uint	  /* num_entries */,
				 cl_device_id *   /* devices */,
				 cl_uint *	  /* num_devices */);

typedef cl_int(*PclGetDeviceInfo)(cl_device_id	  /* device */,
				  cl_device_info  /* param_name */,
				  size_t	  /* param_value_size */,
				  void *	  /* param_value */,
				  size_t *	  /* param_value_size_ret */);

struct INSTALLER_SYSTEM_INFO
{
	INSTALLER_SYSTEM_INFO()
	{
		getInfoSuccess = false;
		openclVersion = 0.0;
		gpuAvailableForOpenCL = false;
	}

	bool getInfoSuccess;
	std::vector<std::wstring> gpuName;
	std::vector<std::wstring> gpuDriver;
	std::wstring osversion;
	bool gpuAvailableForOpenCL;
	float openclVersion;
};
INSTALLER_SYSTEM_INFO g_systemInfo; // filled by GetSystemInfo_()

bool yesno_applescript(char const* prompt, const char* warning, bool default_yes=true)
{
    const char* cmd=
    "osascript<<EOT\n"
    "tell me to activate\n"
    "set question to display dialog \"%s\" buttons {\"Yes\",\"No\"} default button 2\n"
    "set answer to button returned of question\n"
    "if answer is equal to \"Yes\" then\n"
    "return 0\n"
    "end if\n"
    "error number -1\n"
    "EOT\n"
    ;
    //
    char cmdbuf[2048];
    sprintf(cmdbuf,cmd,warning);
    int result = system(cmdbuf);
    return (result==0) ? true : false;
}

bool ok_applescript(char const* prompt, const char* warning, bool default_yes=true)
{
    const char* cmd=
    "osascript<<EOT\n"
    "tell me to activate\n"
    "set question to display dialog \"%s\" buttons {\"OK\"} default button 1\n"
    "set answer to button returned of question\n"
    "if answer is equal to \"OK\" then\n"
    "return 0\n"
    "end if\n"
    "error number -1\n"
    "EOT\n"
    ;
    //
    char cmdbuf[2048];
    sprintf(cmdbuf,cmd,warning);
    int result = system(cmdbuf);
    return (result==0) ? true : false;
}


bool yesno(char const* prompt, bool default_yes=true)
{
    using namespace std;
    if (prompt && cin.tie())
    {
        *cin.tie() << prompt << (default_yes ? " [Yn] " : " [yN] ");
    }
    string line;
    if (!getline(cin, line))
    {
        throw std::runtime_error("yesno: unexpected input error");
    }
    else if (line.size() == 0)
    {
        return default_yes;
    }
    else
    {
        return line[0] == 'Y' || line[0] == 'y';
    }

}

bool PathFileExists(string path)
{
	ifstream my_file(path);
	return my_file.good();
}


int GetMinorVersion(string& s)
{
	int X, Y;
	std::sscanf(s.c_str(), "%d.%d", &X, &Y);
	return Y;
}

int GetMajorVersion(string& s)
{
	int X, Y;
	std::sscanf(s.c_str(), "%d.%d", &X, &Y);
	return X;
}

bool ParseNVIDIADriver(string& rawDriver, ofstream& logfile , int& publicVersionOut)
{
	//"10.18.13.5456"  --> for NVIDIA ( the 5 last figures correspond to the public version name, here it's 354.56 )
	//"9.18.13.697"    --> for NVIDIA ( public version will be 306.97 )
	publicVersionOut = 0;
	std::stringstream buffer;
	int A, B, X, Y, out = -1;
	size_t n = std::count(rawDriver.begin(), rawDriver.end(), '.');
	try
	{
		switch ( n )  
		{
			case 3 :
				std::sscanf(rawDriver.c_str(), "%d.%d.%d.%d", &A, &B, &X, &Y);
				buffer << setw(1) << (X%10) << setw(4) << setfill('0') << Y;
				break;
			case 1 :
				std::sscanf(rawDriver.c_str(), "%d.%d", &X, &Y);
				buffer << X << Y;
				break;
			default :
				X = Y = 0;
		}
		std::sscanf(buffer.str().c_str(), "%d", &out);
		publicVersionOut = out;
	}
	catch (runtime_error e)
	{
		logfile << "ParseNVIDIADriver : ERROR Exception" << std::endl;
		return false;
	}

	return (publicVersionOut > 0);
}

std::string ssystem(const char* cmd)
{
	char buffer[128];
	std::string result = "";
	FILE* pipe = popen(cmd, "r");
	if (!pipe) throw std::runtime_error("popen() failed!");
	try {
		while (!feof(pipe)) {
			if (fgets(buffer, 128, pipe) != NULL)
				result += buffer;
		}
	} catch (...) {
		pclose(pipe);
		throw;
	}
	pclose(pipe);
	return result;
}

std::wstring& URLfriendly(std::wstring& str)
{
	 for(int i=0; i<str.length(); i++)
	 {
		  if (	 str[i] == ' '
			   || str[i] == '&'
			   || str[i] == '?'
			   || str[i] == '('
			   || str[i] == ')'
			   || str[i] == '|'
			   || str[i] == '"'
			   )
		  {
			   str[i] = '_';
		  }
	 }

	 return str;
}


void formSelect::WstringToString(const std::wstring& wstr, std::string& astr)
{
	for(size_t i=0; i<wstr.length(); i++)
	{
		astr.push_back( (char)wstr[i] );
	}
	return;
}

void formSelect::StringToWstring(std::wstring &wstr, const std::string &astr)
{
	std::wstring wsTmp(astr.begin(), astr.end());

	wstr = wsTmp;

	return;
}

void formSelect::BuildRegistrationLink()
{
	*outmsg << "BuildRegistrationLink begin..." << endl;
	logfile << "Building registration link...\r\n" << endl;

    std::wstring blender_version = L"unknown";
    const char* blv = getenv("BLENDER_VERSION");
    if (blv)
        StringToWstring(blender_version, blv);

	/* Get RadeonProRender version */
	std::wstring rprVersion = L"unknown";
	uint32_t majorVersion = VERSION_MAJOR(RPR_API_VERSION);
	uint32_t minorVersion = VERSION_MINOR(RPR_API_VERSION);
	std::stringstream buffer;
	buffer << majorVersion << "." << minorVersion;
	StringToWstring(rprVersion,buffer.str().c_str());

	std::wstring osVersion = g_systemInfo.osversion;
	std::wstring registrationid = L"5A1E27D259A3291C";
	std::wstring appname = L"blender";
	std::wstring driverVersion = g_systemInfo.gpuDriver.size() > 0 ? g_systemInfo.gpuDriver[0] : std::wstring(L"");
	std::wstring gfxcard	= g_systemInfo.gpuName.size()	> 0 ? g_systemInfo.gpuName[0]	: std::wstring(L"");

	/* Link must look like : */
	//"https://feedback.amd.com/se/5A1E27D23E8EC664?registrationid=5A1E27D27D97ECF5&appname=blender&appversion=2016&frversion=1.6.30&os=win6.1.7601&gfxcard=AMD_FirePro_W8000__FireGL_V_&driverversion=15.201.2401.0"

	g_registrationLink = L"";
	g_registrationLink += L"https://feedback.amd.com/se/5A1E27D23E8EC664";
	g_registrationLink += L"?registrationid=";
	g_registrationLink += URLfriendly(registrationid);
	g_registrationLink += L"&appname=";
	g_registrationLink += URLfriendly(appname);
	g_registrationLink += L"&appversion=";
	g_registrationLink += URLfriendly(blender_version);
	g_registrationLink += L"&frversion=";
	g_registrationLink += URLfriendly(rprVersion);
	g_registrationLink += L"&os=";
	g_registrationLink += URLfriendly(osVersion);
	g_registrationLink += L"&gfxcard=";
	g_registrationLink += URLfriendly(gfxcard);
	g_registrationLink += L"&driverversion=";
	g_registrationLink += URLfriendly(driverVersion);

	string tmp;
	WstringToString(g_registrationLink.c_str(), tmp);
	logfile << "Register link = " + tmp + "\r\n" << endl;
    
    *outmsg << endl;
    *outmsg << endl;
    *outmsg << endl;
	*outmsg << "Register link = " + tmp << endl;
    *outmsg << endl;
    *outmsg << endl;
    *outmsg << endl;
    
	logfile << "Done.\r\n" << endl;
	*outmsg << "BuildRegistrationLink end..." << endl;
    
    
    std::string tmp2;
    tmp2 = "Please visit \n\n";
    tmp2 += tmp;
    tmp2 += "\n\n for the registration key.";
    ok_applescript("",tmp2.c_str());
}

void formSelect::formSelect_Shown(void)
{
	checkCompatibility_hardware();
	if (m_totalSuccess)
		checkCompatibility_driver();
//      Remove this one, Tahoe is not yet installed
//	if (m_totalSuccess)
//		checkCompatibility_Tahoe();
	if (m_totalSuccess)
		BuildRegistrationLink();
}

bool formSelect::checkCompatibility_hardware()
{

	*outmsg << "checkCompatibility_hardware begin..." << endl;
	logfile << "Checking hardware compatibility...\r\n" << endl;

	GetSystemInfo_();

    string osmessageWarning = "";
	bool displaWarningMessage_cantGetInfo = false;
    bool displaWarningMessage_incompatibleOS = false;
	bool displaWarningMessage_incompatibleOpenCL = false;
    bool displaWarningMessage_missingDylib = false;
	std::vector<std::wstring> displaWarningMessage_blacklistedDevice_names;

#define CHECK_DONE_BY_APP_INSTALLER 1
#ifndef CHECK_DONE_BY_APP_INSTALLER
    std::string osstring;
    osstring.resize(1024);
    size_t l = osstring.size();
    if (sysctlbyname("kern.osrelease",&osstring[0],&l,NULL,0)==0)
    {
        cout << "os.release" << osstring << endl;
        int minor=0, major=0;
        minor=GetMinorVersion(osstring);
        major=GetMajorVersion(osstring);
        cout << "\t" << major << " " << minor << endl;
        
        const int kRequiredMajor = 17;
        const int kRequiredMinor = 3;
        if (major < kRequiredMajor ||
            (major == kRequiredMajor && minor < kRequiredMinor))
        {
            osmessageWarning = "Mac Operating System High Sierra 10.13.3 or later is required. Continue installation?";
            displaWarningMessage_incompatibleOS = true;
        }
    }
    else
    {
        osmessageWarning = "Unable to determine OS version. Continue installation?";
        displaWarningMessage_cantGetInfo = true;
    }
#endif
    
    std::string ffidll = "/usr/lib/libffi.dylib";
    if (0 != access(ffidll.c_str(),F_OK))
    {
        osmessageWarning = "The required dynamic library '" + ffidll + "' is missing. Continue installation?";
        displaWarningMessage_missingDylib = true;
    }
    
    if (displaWarningMessage_incompatibleOS || displaWarningMessage_cantGetInfo || displaWarningMessage_missingDylib)
    {
#ifdef USE_APPLESCRIPT
        bool result = yesno_applescript("",osmessageWarning.c_str());
#else
        bool result = yesno("", false);
#endif
        if (!result)
        {
            m_totalSuccess = false;
            exit(-1);
            return false;
        }
    }
    
	if ( !g_systemInfo.getInfoSuccess)
	{
		displaWarningMessage_cantGetInfo = true;
		*outmsg << "displaWarningMessage_cantGetInfo = true" << endl;
	}


	if ( g_systemInfo.getInfoSuccess && (!g_systemInfo.gpuAvailableForOpenCL || g_systemInfo.openclVersion < 1.2f))
	{
		displaWarningMessage_incompatibleOpenCL = true;
		*outmsg << "displaWarningMessage_incompatibleOpenCL = true" << endl;
	}

	unsigned numWhitelisted = 0;
	for(int iGpu=0; iGpu<g_systemInfo.gpuName.size(); iGpu++)
	{
		std::string gpuNameA;
		WstringToString(g_systemInfo.gpuName[iGpu], gpuNameA);

#if defined(__APPLE__)
		if (g_systemInfo.getInfoSuccess && !IsDeviceNameWhitelisted(gpuNameA.c_str(), RPRTOS_MACOS))
#else
		if ( g_systemInfo.getInfoSuccess && !IsDeviceNameWhitelisted(gpuNameA.c_str(),RPRTOS_LINUX))
#endif
		{
			displaWarningMessage_blacklistedDevice_names.push_back(g_systemInfo.gpuName[iGpu]);
			*outmsg << "incompatible device " + gpuNameA << endl;
		}
		else
		{
			numWhitelisted++;
		}
	}

    // Only warn about blacklisted devices if we have no whitelisted GPUs
    bool badGpuBlackList = (numWhitelisted == 0) && (displaWarningMessage_blacklistedDevice_names.size() >= 1);
	if ( displaWarningMessage_cantGetInfo || displaWarningMessage_incompatibleOpenCL || badGpuBlackList )
	{
		string messageWarning = "";

		if ( displaWarningMessage_cantGetInfo )
		{
			messageWarning = "Installer is not able to check the system compatibility. ";
			logfile << messageWarning + "\r\n" << endl;
			messageWarning += "Continue install anyway ?";
			*outmsg << "WARNING MESSAGE : "+messageWarning;
		}

		if ( displaWarningMessage_incompatibleOpenCL )
		{
			messageWarning = "Your system seems incompatible with Radeon ProRender for OpenCL. Only the CPU rendering mode may run correctly. ";
			logfile << messageWarning + "\r\n" << endl;
			messageWarning += "Continue install anyway ?";
			*outmsg << "WARNING MESSAGE : "+messageWarning;
		}

		if (badGpuBlackList)
		{
			string BckDevName;
			WstringToString(displaWarningMessage_blacklistedDevice_names[0].c_str(), BckDevName);
			messageWarning = "Some of your devices (" + BckDevName + ") are known as incompatible or have not been certified by the Radeon ProRender Team. ";
			logfile << messageWarning + "\r\n" << endl;
			messageWarning += "Continue install anyway ?";
			*outmsg << "WARNING MESSAGE : "+messageWarning;
		}

#ifdef USE_APPLESCRIPT
        bool result = yesno_applescript("",messageWarning.c_str());
#else
		bool result = yesno("", false);
#endif
		if (!result)
		{
			m_totalSuccess = false;
            exit(-1);
			return false;
		}
	}


	logfile << "Done.\r\n" << endl;
	*outmsg << "checkCompatibility_hardware end..." << endl;

	return true;
}

bool formSelect::checkCompatibility_driver()
{
	logfile << "Checking driver compatibility...\r\n" << endl;
	*outmsg << "checkCompatibility_driver begin..." << endl;
    
#if defined(__APPLE__)
    
    return true;
    
#else

	const int Supported_AMD_driverMajor = 15;
	const int Supported_AMD_driverMinor = 301;

	string Supported_NVIDIA_driver_string = "368.39";
	const int Supported_NVIDIA_driver     =  36839;

	string VideoController_DriverVersion, VideoController_Name;
	bool hardwareIsAMD = false, hardwareIsNV = false;
	int driverCompatible = 0;
	string answer;
	if (PathFileExists("/proc/driver/nvidia/version"))
	{
		/* NVidia case */
		/* NVRM version: NVIDIA UNIX x86_64 Kernel Module  304.54  Sat Sep 29 00:05:49 PDT 2012 */
		/* Or */
		/* NVRM version: NVIDIA UNIX x86_64 Kernel Module  367.57  Mon Oct  3 20:37:01 PDT 2016 */
		/* GCC version: gcc version 4.4.7 20120313 (RedHat 4.4.7-17) (GCC) */
		answer = ssystem("grep NVRM /proc/driver/nvidia/version | awk '{print $8}'");
		hardwareIsNV = true;
		VideoController_DriverVersion = answer;
	}
	else
	{
		/* AMD case */
		/* ReleaseVersion=16.40 */
		string QuerryPath = "/var/opt/amdgpu-pro-local";
		string DriverFileName = "/dev/ati/card0";
		if (PathFileExists(QuerryPath.c_str()))
		{
//			string cmd = "grep Filename: " + QuerryPath + "/* | grep \"/amdgpu-pro\" | grep amd64 | grep -v lib32 | awk -F\"_\" '{print $2}' | awk -F\"-\" '{print $1}'";
			string cmd = "grep Filename: " + QuerryPath + "/* | awk '{ print $2}'| awk -F\"/\" '{print $2}'| grep \"^amdgpu-pro_\" | grep amd64 | awk -F\"_\" '{print $2}' | awk -F\"-\" '{print $1}'";
			answer = ssystem(cmd.c_str());
			hardwareIsAMD = true;
			VideoController_DriverVersion = answer;
		}
		/* ReleaseVersion=S15.302.2301-160625a-304717C-Retail_End_User */
		else if (PathFileExists(DriverFileName.c_str()))
		{
			struct drm_version d_ver = {.version_major=0, .version_minor=0, .version_patchlevel=0};
			try
			{
				int fd = open(DriverFileName.c_str(), O_RDONLY | O_NONBLOCK);
				ioctl(fd, DRM_IOCTL_VERSION, &d_ver);
			}
			catch (...)
			{
				logfile << "checkCompatibility_driver: ERROR Exception" << std::endl;
				return false;
			}

			std::stringstream buffer;
//			buffer << "Major version: " <<	d_ver.version_major << " Minor version: " << d_ver.version_minor << " Patch level: " << d_ver.version_patchlevel << endl;
//			*outmsg << buffer.str().c_str() << endl;
			buffer << d_ver.version_major << "." << d_ver.version_minor << d_ver.version_patchlevel;
			hardwareIsAMD = true;
			VideoController_DriverVersion = buffer.str().c_str();
		}
		else if (PathFileExists("/etc/ati/amdpcsdb"))
		{
			answer = ssystem("grep ReleaseVersion /etc/ati/amdpcsdb | awk -F\"S\" '{ print $2 }' | awk -F\"-\" '{print $1}'");
			if (answer == "")
			{
				answer = ssystem("rpm -q -a | grep fglrx | grep core | awk -F\"-\" '{print $2}'");
				if (answer != "")
				{
					hardwareIsAMD = true;
					VideoController_DriverVersion = answer;
				}
			}
			else
			{
				hardwareIsAMD = true;
				VideoController_DriverVersion = answer;
			}
		}
	}

	//example of VideoController_DriverVersion:
	//"15.301.2601.0"  --> for AMD
	//"10.18.13.5456"  --> for NVIDIA ( the 5 last figures correspond to the public version name, here it's 354.56 )
	//"9.18.13.697"    --> for NVIDIA ( public version will be 306.97 )

	//examples of VideoController_Name :
	//"AMD FirePro W8000"
	//"NVIDIA Quadro 4000"
	//"NVIDIA GeForce GT 540M"

	if (hardwareIsAMD || hardwareIsNV)
	{
		VideoController_DriverVersion.resize( VideoController_DriverVersion.find_last_not_of("\n")+1 );
		string HardwareName = hardwareIsAMD ? "(AMD) " : "(NVIDIA) ";
		*outmsg << "VideoController_DriverVersion = " + HardwareName + VideoController_DriverVersion << endl;
		for(int iGpu=0; iGpu<g_systemInfo.gpuName.size(); iGpu++)
		{
			std::string gpuNameA;
			WstringToString(g_systemInfo.gpuName[iGpu], gpuNameA);
			*outmsg << "VideoController_Name = " + gpuNameA << endl;
		}
	}

	std::ostringstream oss;
	std::wstring wstrname;
	if (hardwareIsAMD)
	{
		int VersionMajorInt = GetMajorVersion(VideoController_DriverVersion);
		int VersionMinorInt = GetMinorVersion(VideoController_DriverVersion);

		if ( VersionMajorInt < Supported_AMD_driverMajor )
		{
			driverCompatible = 1;
			*outmsg << "checkCompatibility_driver : WARNING: driver not compatible because major." << endl;
		}
		else if ( VersionMajorInt == Supported_AMD_driverMajor && VersionMinorInt < Supported_AMD_driverMinor )
		{
			driverCompatible = 1;
			*outmsg << "checkCompatibility_driver : WARNING: driver not compatible because minor." << endl;
		}
		else
		{
			driverCompatible = 2;
			*outmsg << "checkCompatibility_driver : AMD driver compatible" << endl;
		}
		oss << VersionMajorInt << "." << VersionMinorInt;
	}
	else if (hardwareIsNV)
	{

		int nvidiaPublicDriver = 0;
		bool successParseNVdriver = ParseNVIDIADriver(VideoController_DriverVersion, logfile, nvidiaPublicDriver);

		if ( successParseNVdriver )
		{
			*outmsg << "checkCompatibility_driver : nvidiaPublicDriver = " + to_string(nvidiaPublicDriver) << endl;

			if ( nvidiaPublicDriver < Supported_NVIDIA_driver )
			{
				driverCompatible = 1;
				*outmsg << "checkCompatibility_driver : WARNING: NV driver too old." << endl;
			}
			else
			{
				driverCompatible = 2;
				*outmsg << "checkCompatibility_driver : NVIDIA driver compatible" << endl;
			}
		}
		else
		{
			*outmsg << "checkCompatibility_driver : WARNING: bad NVIDIA driver format" << endl;
		}
		oss << nvidiaPublicDriver;
	}
	else
	{
		logfile << "checkCompatibility_driver : WARNING: No AMD or NV Found." << endl;
	}
	StringToWstring(wstrname, oss.str());
	g_systemInfo.gpuDriver.push_back(wstrname);


	if ( driverCompatible == 1 )
	{
		ostringstream messageWarning;
		messageWarning << "Your graphics driver may be incompatible with Radeon ProRender. ";

		if ( hardwareIsAMD )
		{
			messageWarning << "For AMD, you need " << Supported_AMD_driverMajor << "." << Supported_AMD_driverMinor << " or higher.";
		}
		else if ( hardwareIsNV )
		{
			messageWarning << "For NVIDIA, you need " << Supported_NVIDIA_driver_string << " or higher.";
		}

		logfile << messageWarning.str() + "\r\n" << endl;
		messageWarning << "Continue install anyway ?";
		*outmsg << "WARNING MESSAGE : " + messageWarning.str() << RESET;
#ifdef USE_APPLESCRIPT
        bool result = yesno_applescript("",messageWarning.c_str());
#else
        bool result = yesno("", false);
#endif
		if (!result)
		{
			m_totalSuccess = false;
			return false;
		}
	}
	logfile << "Done.\r\n" << endl;
	*outmsg << "checkCompatibility_driver end..." << endl;

	return true;
#endif
}

bool formSelect::checkCompatibility_Tahoe()
{
	//check that libTahoe64.so can be loaded.
	//for example,	in AMDMAX-815 , libTahoe64.so was not loaded because its dependancy libOpenCL.so was outdated.

	*outmsg << "checkCompatibility_Tahoe begin..." << endl;
	logfile << "Checking Radeon ProRender compatibility...\r\n" << endl;

	std::string fullpath = "libTahoe64.so";
	void *tahoe_handle = dlopen(fullpath.c_str(), RTLD_NOW);
	char *error;

	dlerror();
	if (tahoe_handle)
	{
		*outmsg << "checkCompatibility_Tahoe : libTahoe64.so can be loaded" << endl;
		dlclose(tahoe_handle);
	}
	else
	{
		*outmsg << "checkCompatibility_Tahoe - ERROR : Tahoe64.so can NOT be loaded" << endl;

		//try to understand why
		if ( !PathFileExists(fullpath.c_str())	)
		{
			*outmsg << "the libTahoe64.so file does NOT exist." << endl;
		}
		else
		{
			*outmsg << "the libTahoe64.so file exists." << endl;
		}

		string messageWarning = "ERROR : Your system is not compatible with Radeon ProRender.\nThis could be because OpenCL is not installed, please install it from your hardware vendor website.\nSee previous Warning message(s), and log.txt in install folder for more information.\n";
		messageWarning += "Continue install anyway ?";
		*outmsg << messageWarning;

		//cancel installation
#ifdef USE_APPLESCRIPT
        bool result = yesno_applescript("",messageWarning.c_str());
#else
        bool result = yesno("", false);
#endif
		if (!result)
		{
			m_totalSuccess = false;
			return false;
		}

	}

	*outmsg << "checkCompatibility_Tahoe end..." << endl;
	logfile << "Done.\r\n" << endl;

	return true;
}

void formSelect::GetSystemInfo_()
{
#if defined(__APPLE__)
    *outmsg << "> GetSystemInfo_ begin..." << endl;
    
    struct utsname uts;
    uname(&uts);
    if (uname(&uts))
    {
        g_systemInfo.getInfoSuccess = false;
        *outmsg << "> GetSystemInfo_: FAILED - uname" << endl;
        return;
    }
   
    //try to load OpenCL lib and methods required for version check
    std::string OCL_name = "/System/Library/Frameworks/OpenCL.framework/OpenCL";
    void *openclLib = dlopen(OCL_name.c_str(), RTLD_NOW);
    if (!openclLib)
    {
        g_systemInfo.getInfoSuccess = false;
        *outmsg << "> GetSystemInfo_: FAILED - dlopen libOpenCL.so" << endl;
        return;
    }
    *outmsg << "> GetSystemInfo_ : " << OCL_name << " can be loaded" << endl;
    
    dlerror();
    //loading required methods
    PclGetPlatformIDs GetPlatformIDs = (PclGetPlatformIDs)dlsym(openclLib, "clGetPlatformIDs");
    PclGetPlatformInfo GetPlatformInfo = (PclGetPlatformInfo)dlsym(openclLib, "clGetPlatformInfo");
    PclGetDeviceIDs GetDeviceIDs = (PclGetDeviceIDs)dlsym(openclLib, "clGetDeviceIDs");
    PclGetDeviceInfo GetDeviceInfo = (PclGetDeviceInfo)dlsym(openclLib, "clGetDeviceInfo");
    
    if (!GetPlatformIDs || !GetPlatformInfo || !GetDeviceIDs || !GetDeviceInfo)
    {
        g_systemInfo.getInfoSuccess = false;
        *outmsg << "> GetSystemInfo_: FAILED - GetProcAddress opencl" << endl;
        return;
    }
    
    //look for device with newer OpenCL version
    cl_int error = CL_SUCCESS;
    // Query for platforms
    std::vector<cl_platform_id> platforms;
    cl_uint platf_count = 0;
    error = GetPlatformIDs(0, nullptr, &platf_count);
    if (error != CL_SUCCESS)
    {
        g_systemInfo.getInfoSuccess = false;
        *outmsg << "> GetSystemInfo_: FAILED - can't get OpenCL platforms" << endl;
        return;
    }
    if (platf_count == 0)
    {
        g_systemInfo.getInfoSuccess = false;
        *outmsg << "> GetSystemInfo_: FAILED - there are no available OpenCL platforms" << endl;
        return;
    }
    
    platforms.resize(platf_count);
    error |= GetPlatformIDs(platf_count, platforms.data(), nullptr);
    if (error != CL_SUCCESS)
    {
        g_systemInfo.getInfoSuccess = false;
        *outmsg << "> GetSystemInfo_: FAILED - can't get OpenCL platforms 2" << endl;
        return;
    }
    
    g_systemInfo.gpuAvailableForOpenCL = false;
    g_systemInfo.openclVersion = 0.0f;
    
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
            *outmsg << "> GetSystemInfo_: FAILED - can't get OpenCL devices" << endl;
            return;
        }
        
        for (auto& dev : devices)
        {
            // Get the device name
            char device_string[1024];
            GetDeviceInfo(dev, CL_DEVICE_NAME, sizeof(device_string), &device_string, NULL);
            std::wstring wstrname;
            std::string dstrname = device_string;
            StringToWstring(wstrname, dstrname);
            g_systemInfo.gpuName.push_back(wstrname);
            *outmsg << "Device name " << device_string << endl;
            
            size_t version_size = 0;
            error = GetDeviceInfo(dev, CL_DEVICE_VERSION, 0, nullptr, &version_size);
            std::vector<char> version(version_size);
            error |= GetDeviceInfo(dev, CL_DEVICE_VERSION, version_size, version.data(), nullptr);
            if (error != CL_SUCCESS)
            {
                g_systemInfo.getInfoSuccess = false;
                *outmsg << "GetSystemInfo_: FAILED - can't get devices OpenCL version" << endl;
                return;
            }
            
            std::string strVersion(version.begin(), version.end());
            std::istringstream buf(strVersion);
            std::istream_iterator<std::string> beg(buf), end;
            std::vector<std::string> tokens(beg, end);
            // expected version string in format OpenCL<space><major_version.minor_version><space><vendor-specific information>
            float devCLVersion = std::stof(tokens[1]);
            
            *outmsg << " + 1 GPU supports OpenCL " + to_string(devCLVersion) << endl;
            
            if (devCLVersion > g_systemInfo.openclVersion)
            g_systemInfo.openclVersion = devCLVersion;
            
            g_systemInfo.gpuAvailableForOpenCL = true;
        }
        
    }
    
    
    g_systemInfo.getInfoSuccess = true;
    *outmsg << "> GetSystemInfo_: SUCCESS." << endl;
    *outmsg << "> GetSystemInfo_ end..." << endl;
    return;
#else
	*outmsg << "> GetSystemInfo_ begin..." << endl;

	struct utsname uts;
	uname(&uts);
	if (uname(&uts))
	{
		g_systemInfo.getInfoSuccess = false;
		*outmsg << "> GetSystemInfo_: FAILED - uname" << endl;
		return;
	}
	std::wstring wstr;
#if 1
	StringToWstring(wstr, string(uts.sysname) + string(uts.release));
#else
	string answer = ssystem("uname -m");
	if (answer.find("64", 0) != answer.npos)
		StringToWstring(wstr, string(uts.sysname) + "64");
	else
		StringToWstring(wstr, string(uts.sysname) + "32");
#endif
	g_systemInfo.osversion = wstr;
	struct pci_access *pacc;
	struct pci_dev *dev;
	unsigned int c;
	char namebuf[1024], *name;
	pacc = pci_alloc(); /* Get the pci_access structure */
	pci_init(pacc);     /* Initialize the PCI library */
	pci_scan_bus(pacc); /* We want to get the list of devices */
	for(dev=pacc->devices; dev;dev=dev->next) /* Iterate over all devices */
	{
		pci_fill_info(dev, PCI_FILL_IDENT);	   /* Fill in header info we need */
		c = pci_read_byte(dev, PCI_INTERRUPT_PIN); /*Read config register directly */
		if (dev->vendor_id == 0x1002 /*AMD*/ || dev->vendor_id == 0x10DE /*NVIDIA*/)
		{
			name = pci_lookup_name(pacc, namebuf, sizeof(namebuf), PCI_LOOKUP_DEVICE, dev->vendor_id, dev->device_id);
			if (strstr(name, "Audio") == NULL && strstr(name, "audio") == NULL && strstr(name, "Device") == NULL && strstr(name, "device") == NULL )
			{
				std::stringstream buffer;
				buffer << " + 1 " << setw(4) << setfill('0') << std::hex << (int)dev->domain << ":" << setw(2) << (int)dev->bus << ":" << setw(2) << (int)dev->dev << "." << (int)dev->func << " vendor=" << setw(4) << (int)dev->vendor_id << " device=" << setw(4) << (int)dev->device_id << " (" << name << ")";
				*outmsg << buffer.str() << std::endl;
				std::string strname = string(name), strname2, strname3;
				size_t pos1 = strname.find("[", 0);
				size_t pos2 = strname.npos;
				if (pos1 != strname.npos)
					pos2 = strname.find("]", pos1);
				if (pos2 != strname.npos)
					strname2 = strname.substr(pos1 + 1, pos2 - pos1 -1);
				if (dev->vendor_id == 0x1002 /*AMD*/)
					strname3 = "AMD ";
				else
					strname3 = "NVIDIA";
				std::wstring wstrname;
				StringToWstring(wstrname, strname3 + strname2);
				g_systemInfo.gpuName.push_back(wstrname);
			}
		}
	}

	// Cleanup
	// ========
	pci_cleanup(pacc);


	/////////////////////////////

	//try to load OpenCL lib and methods required for version check
	std::string OCL_name = "libOpenCL.so";
	void *openclLib = dlopen(OCL_name.c_str(), RTLD_NOW);
	if (!openclLib)
	{
		OCL_name = "libOpenCL.so.1";
		openclLib = dlopen(OCL_name.c_str(), RTLD_NOW);
		if (!openclLib)
		{
			g_systemInfo.getInfoSuccess = false;
			*outmsg << "> GetSystemInfo_: FAILED - dlopen libOpenCL.so" << endl;
			return;
		}
	}
	*outmsg << "> GetSystemInfo_ : " << OCL_name << " can be loaded" << endl;

	dlerror();
	//loading required methods
	PclGetPlatformIDs GetPlatformIDs = (PclGetPlatformIDs)dlsym(openclLib, "clGetPlatformIDs");
	PclGetPlatformInfo GetPlatformInfo = (PclGetPlatformInfo)dlsym(openclLib, "clGetPlatformInfo");
	PclGetDeviceIDs GetDeviceIDs = (PclGetDeviceIDs)dlsym(openclLib, "clGetDeviceIDs");
	PclGetDeviceInfo GetDeviceInfo = (PclGetDeviceInfo)dlsym(openclLib, "clGetDeviceInfo");

	if (!GetPlatformIDs || !GetPlatformInfo || !GetDeviceIDs || !GetDeviceInfo)
	{
		g_systemInfo.getInfoSuccess = false;
		*outmsg << "> GetSystemInfo_: FAILED - GetProcAddress opencl" << endl;
		return;
	}

	//look for device with newer OpenCL version
	cl_int error = CL_SUCCESS;
	// Query for platforms
	std::vector<cl_platform_id> platforms;
	cl_uint platf_count = 0;
	error = GetPlatformIDs(0, nullptr, &platf_count);
	if (error != CL_SUCCESS)
	{
		g_systemInfo.getInfoSuccess = false;
		*outmsg << "> GetSystemInfo_: FAILED - can't get OpenCL platforms" << endl;
		return;
	}
	if (platf_count == 0)
	{
		g_systemInfo.getInfoSuccess = false;
		*outmsg << "> GetSystemInfo_: FAILED - there are no available OpenCL platforms" << endl;
		return;
	}

	platforms.resize(platf_count);
	error |= GetPlatformIDs(platf_count, platforms.data(), nullptr);
	if (error != CL_SUCCESS)
	{
		g_systemInfo.getInfoSuccess = false;
		*outmsg << "> GetSystemInfo_: FAILED - can't get OpenCL platforms 2" << endl;
	return;
	}

	g_systemInfo.gpuAvailableForOpenCL = false;
	g_systemInfo.openclVersion = 0.0f;

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
			*outmsg << "> GetSystemInfo_: FAILED - can't get OpenCL devices" << endl;
			return;
		}

		for (auto& dev : devices)
		{
			size_t version_size = 0;
			error = GetDeviceInfo(dev, CL_DEVICE_VERSION, 0, nullptr, &version_size);
			std::vector<char> version(version_size);
			error |= GetDeviceInfo(dev, CL_DEVICE_VERSION, version_size, version.data(), nullptr);
			if (error != CL_SUCCESS)
			{
				g_systemInfo.getInfoSuccess = false;
				*outmsg << "GetSystemInfo_: FAILED - can't get devices OpenCL version" << endl;
				return;
			}

			std::string strVersion(version.begin(), version.end());
			std::istringstream buf(strVersion);
			std::istream_iterator<std::string> beg(buf), end;
			std::vector<std::string> tokens(beg, end);
			// expected version string in format OpenCL<space><major_version.minor_version><space><vendor-specific information>
			float devCLVersion = std::stof(tokens[1]);

			*outmsg << " + 1 GPU supports OpenCL " + to_string(devCLVersion) << endl;

			if (devCLVersion > g_systemInfo.openclVersion)
				g_systemInfo.openclVersion = devCLVersion;

			g_systemInfo.gpuAvailableForOpenCL = true;
		}

	}


	g_systemInfo.getInfoSuccess = true;
	*outmsg << "> GetSystemInfo_: SUCCESS." << endl;
	*outmsg << "> GetSystemInfo_ end..." << endl;
	return;
#endif
}

