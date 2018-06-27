#include "PluginContext.h"

#include <intrin.h>

PluginContext& PluginContext::instance()
{
	static PluginContext pluginContext;

	return pluginContext;
}

PluginContext::PluginContext()
{
	mHasSSE41 = CheckSSE41();
}

bool PluginContext::HasSSE41() const
{
	return mHasSSE41;
}

bool PluginContext::CheckSSE41()
{
	bool hasSSE41 = true;

	int cpuInfo[4];

	__cpuid(cpuInfo, 0);

	size_t elementsNumber = cpuInfo[0];

	if (elementsNumber > 0)
	{
		__cpuidex(cpuInfo, 1, 0);

		int f_1_ECX = cpuInfo[2];
		int f_1_EDX = cpuInfo[3];

		bool hasSSE = f_1_EDX & (1 << 25);
		bool hasSSE2 = f_1_EDX & (1 << 26);
		bool hasSSE3 = f_1_ECX & (1 << 0);
		hasSSE41 = f_1_ECX & (1 << 19);
		bool hasSSE42 = f_1_ECX & (1 << 20);
	}

	// another way to check
	try
	{
		__m128i data = _mm_set1_epi32(0xaa55);
		__m128i y = _mm_packus_epi32(data, data);
	}
	catch (...)
	{
		hasSSE41 = false;
	}

	return hasSSE41;
}
