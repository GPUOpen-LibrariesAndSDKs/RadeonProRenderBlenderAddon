#pragma once

#if defined(WIN32)
	#define NOMINMAX
	#define WIN32_LEAN_AND_MEAN             // Exclude rarely-used stuff from Windows headers
	#include <windows.h>
	#define EXPORT __declspec(dllexport)
#else
	#define EXPORT
#endif


#include "math_wrap.h"
