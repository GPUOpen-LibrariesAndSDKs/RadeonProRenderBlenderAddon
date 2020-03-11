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
#include <cstdio>

class Logger
{
	typedef void(*Callback)(const char * sz);

	Callback callback;

	// single instance
	static Logger& Instance()
	{
		static Logger instance;
		return instance;
	}

	// private
	Logger()
	{
		callback = nullptr;
	}

public:
	static void SetCallback(Callback cb = nullptr)
	{
		Instance().callback = cb;
	}

	template <typename... Args>
	static void Printf(const char *format, const Args&... args)
	{
		if (auto cb = Instance().callback)
		{
			char buf[0x10000];
			sprintf_s(buf, format, args...);
			cb(buf);
		}
	}

	static void Printf(const char *sz)
	{
		if (auto cb = Instance().callback)
			cb(sz);
	}

};

template <typename... Args>
inline void DebugPrint(const char *format, const Args&... args)
{
#ifdef _DEBUG
	Logger::Printf(format, args...);
#endif
}


