#pragma once

class PluginContext
{
private:
	PluginContext();

public:
	PluginContext(const PluginContext&) = delete;
	PluginContext& operator=(const PluginContext&) = delete;

	static PluginContext& instance();

	bool HasSSE41() const;

private:
	bool CheckSSE41();

private:
	bool mHasSSE41 = false;
};
