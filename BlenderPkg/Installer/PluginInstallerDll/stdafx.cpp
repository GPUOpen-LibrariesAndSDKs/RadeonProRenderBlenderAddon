#include "stdafx.h"


std::vector<std::wstring> split(const std::wstring &s, wchar_t delim)
{
	std::vector<std::wstring> elems;
	for (size_t p = 0, q = 0; p != s.npos; p = q)
		elems.push_back(s.substr(p + (p != 0), (q = s.find(delim, p + 1)) - p - (p != 0)));

	return elems;
}


void copyStringToClipboard(const std::wstring &str)
{
	size_t len = (str.length() + 1) * sizeof(wchar_t);
	HGLOBAL hMem = GlobalAlloc(GMEM_MOVEABLE, len);
	memcpy(GlobalLock(hMem), str.c_str(), len);
	GlobalUnlock(hMem);
	OpenClipboard(0);
	EmptyClipboard();
	SetClipboardData(CF_UNICODETEXT, hMem);
	CloseClipboard();
}

std::string WstringToString(const std::wstring& wstr)
{
	std::string res;
	for (size_t i = 0; i<wstr.length(); i++)
	{
		res.push_back((char)wstr[i]);
	}

	return res;
}


std::wstring GetSystemFolderPaths(int csidl)
{
	std::wstring res = L"";
	wchar_t folder[1024] = L"";
	HRESULT hr = SHGetFolderPathW(0, csidl, 0, 0, folder);
	if (SUCCEEDED(hr))
		res = (folder);

	return res;
}

//for a better address link firendly, I change some characters to underscore
std::wstring& URLfirendly(std::wstring & str)
{
	for (int i = 0; i<str.length(); i++)
	{
		if (str[i] == ' '
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

