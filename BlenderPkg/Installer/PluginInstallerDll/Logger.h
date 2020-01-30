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


