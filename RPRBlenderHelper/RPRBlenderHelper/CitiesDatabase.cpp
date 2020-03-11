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
#include "stdafx.h"
#include "CitiesDatabase.h"

#include <algorithm>
#include <assert.h>

extern std::string g_addon_path;

#if defined(WIN32)

#include <io.h>

bool IsFileExist(const std::string &s)
{
	return _access(s.c_str(), 0) == 0;
}

#else

#include <unistd.h>

bool IsFileExist(const std::string &s)
{
	return access(s.c_str(), F_OK) != -1;
}

#endif




int CitiesDatabase::SearchWorldCity(const std::string &searchTerm)
{
	std::string search = searchTerm;
	std::transform(search.begin(), search.end(), search.begin(), ::tolower);

	int numCities = (int)mCitiesData.size();

//#pragma omp parallel for
	for (int ii = 0; ii < numCities; ii++)
	{
		const CWorldCity &city = mCitiesData[ii];
		std::string name = city.name;
		if (name.compare(search) == 0)
			return ii;
	}
	return -1;
}


int CitiesDatabase::LookUpWorldCity(const std::string &searchTerm, int startIndex)
{
	if (startIndex < 0)
	{
		startIndex = 0;
	}
	else
	{
		startIndex++;
	}

	std::string search = searchTerm;
	std::transform(search.begin(), search.end(), search.begin(), ::tolower);

	int numCities = (int)mCitiesData.size();

//#pragma omp parallel for
	for (int ii = startIndex; ii < numCities; ii++)
	{
		const CWorldCity &city = mCitiesData[ii];
		std::string name = city.name;
		std::string::size_type pos = name.find(search);
		if (pos != std::string::npos)
			return ii;
	}
	return -1;
}



bool CitiesDatabase::GetCityData(const std::string &city, float * lat, float * longi, float * utcoffset)
{
	int index = SearchWorldCity(city);
	if (index == -1)
		return false;

	assert(index < mCitiesData.size());
	*lat = mCitiesData[index].latitude;
	*longi = mCitiesData[index].longitude;
	*utcoffset = mCitiesData[index].UTCOffset;
	return true;
}


const char * CitiesDatabase::GetCityNameByIndex(int index)
{
	if (index < 0 || index >= mCitiesData.size())
		return nullptr;

	return mCitiesData[index].name.c_str();
}


void CitiesDatabase::BuildWorldCitiesDatabase()
{
	if (database_inited)
		return;

	auto coname = g_addon_path + "/RadeonProRender_co.dat";
	auto ciname = g_addon_path + "/RadeonProRender_ci.dat";
	auto csname = g_addon_path + "/RadeonProRender_cs.dat";
	bool coExists = IsFileExist(coname);
	bool ciExists = IsFileExist(ciname);
	bool csExists = IsFileExist(csname);

	if (coExists && ciExists)
	{
		char buffer[2048];
		FILE * countries_in = fopen(coname.c_str(), "rb");
		assert(countries_in);
		int num_countries = 0;
		fread(&num_countries, sizeof(int), 1, countries_in);
		for (int i = 0; i < num_countries; i++)
		{
			int len = 0;
			fread(&len, sizeof(int), 1, countries_in);
			fread(&buffer, sizeof(char), len, countries_in);
			buffer[len] = '\0';
			mCountriesData.push_back(buffer);
		}
		fclose(countries_in);
		
		FILE * cities_in = fopen(ciname.c_str(), "rb");
		assert(cities_in);
		int num_cities = 0;
		fread(&num_cities, sizeof(int), 1, cities_in);
		mCitiesData.resize(num_cities);
		for (int i = 0; i < num_cities; i++)
		{
			int len = 0;
			fread(&len, sizeof(int), 1, cities_in);
			fread(&buffer, sizeof(char), len, cities_in);
			buffer[len] = '\0';
			mCitiesData[i].name = buffer;
			fread(&mCitiesData[i].latitude, sizeof(float), 1, cities_in);
			fread(&mCitiesData[i].longitude, sizeof(float), 1, cities_in);
			fread(&mCitiesData[i].UTCOffset, sizeof(float), 1, cities_in);
			fread(&mCitiesData[i].countryIdx, sizeof(int), 1, cities_in);
		}
		fclose(cities_in);
	}

	if (csExists)
	{
		FILE * shapes_in = fopen(csname.c_str(), "rb");
		assert(shapes_in);
		int numRecords = 0;
		fread(&numRecords, sizeof(int), 1, shapes_in);

		for (int i = 0; i < numRecords; i++)
		{
			int curRecord = (int)mTzDb.size();
			mTzDb.resize(curRecord + 1);

			int len;
			fread(&len, sizeof(int), 1, shapes_in);
			char buf[1024];
			fread(buf, sizeof(char), len, shapes_in);
			buf[len] = '\0';
			mTzDb[curRecord].name = buf;

			fread(&mTzDb[curRecord].type, sizeof(int), 1, shapes_in);
			fread(&mTzDb[curRecord].UTCoffset, sizeof(float), 1, shapes_in);
			int numVerts = 0;
			fread(&numVerts, sizeof(int), 1, shapes_in);
			for (int j = 0; j < numVerts; j++)
			{
				float lati, longi;
				fread(&longi, sizeof(float), 1, shapes_in);
				fread(&lati, sizeof(float), 1, shapes_in);
				mTzDb[curRecord].verts.push_back(Point2(longi, lati));
			}
		}
		fclose(shapes_in);
	}

	database_inited = true;
}


bool isPointInRect(const float rect[4], const float &x, const float &y)
{
	float orect[] = {
		std::min(rect[0], rect[2]),
		std::min(rect[1], rect[3]),
		std::max(rect[0], rect[2]),
		std::max(rect[1], rect[3])
	};
	return (x >= orect[0] && x <= orect[2] && y >= orect[1] && y <= orect[2]);
}

bool isPointInPoly(const std::vector<Point2> &poly, const float &x, const float &y)
{
	bool inside = false;
	int numVerts = (int)poly.size();
	for (int i = 0, j = numVerts - 1; i < numVerts; j = i++)
	{
		if (((poly[i].y > y) != (poly[j].y > y)) &&
			(x < (poly[j].x - poly[i].x) * (y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x))
			inside = !inside;
	}
	return inside;
}


float CitiesDatabase::GetWorldUTCOffset(float lati, float longi)
{
	float res = -1.f;

	for (auto cc : mTzDb)
	{
		if (cc.type == TZTYPE_MULTIPOLYGON && isPointInPoly(cc.verts, longi, lati))
			return cc.UTCoffset;
		else if (cc.type == TZTYPE_BOX)
		{
			float rect[4] = { cc.verts[0].x, cc.verts[0].y, cc.verts[1].x, cc.verts[1].y };
			if (isPointInRect(rect, longi, lati))
				return cc.UTCoffset;
		}
	}

	// compute marine UTC
	res = longi * 24.f / 360.f;

	return res;
}

CitiesDatabase db;

extern "C"  EXPORT bool get_city_data(const char * city, float * lati, float * longi, float * utcoffset)
{
	if (!city || !*city || !lati || !longi || !utcoffset)
		return false;

	db.BuildWorldCitiesDatabase();
	return db.GetCityData(city, lati, longi, utcoffset);
}

extern "C"  EXPORT int lookup_city(const char * city, int startIndex)
{
	if (!city || !*city)
		return -1;
	
	db.BuildWorldCitiesDatabase();
	return db.LookUpWorldCity(city, startIndex);
}

extern "C"  EXPORT const char * get_city_name_by_index(int index)
{
	db.BuildWorldCitiesDatabase();

	return db.GetCityNameByIndex(index);
}


extern "C"  EXPORT float get_world_utc_offset(float lati, float longi)
{
	db.BuildWorldCitiesDatabase();
	return db.GetWorldUTCOffset(lati, longi);
}