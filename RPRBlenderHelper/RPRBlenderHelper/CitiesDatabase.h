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

#include <vector>
#include <string>

class CitiesDatabase
{
	enum
	{
		TZTYPE_BOX,
		TZTYPE_MULTIPOLYGON
	};

	typedef struct tzrecord_t
	{
		std::string name;
		int type;
		std::vector<Point2> verts;
		float UTCoffset;
	} TZRecord;

	std::vector<TZRecord> mTzDb;

	struct CWorldCity
	{
		std::string name;
		float latitude;
		float longitude;
		float UTCOffset;
		int countryIdx;
	};

	std::vector<std::string> mCountriesData;
	std::vector<CWorldCity> mCitiesData;

	bool	database_inited;

public:

	const char * GetCityNameByIndex		(int index);
	int		LookUpWorldCity				(const std::string &searchTerm, int startIndex);
	
	int		SearchWorldCity				(const std::string &searchTerm);
	void	BuildWorldCitiesDatabase	();
	bool	GetCityData					(const std::string &city, float * lat, float * longi, float * utcoffset);
	float	GetWorldUTCOffset			(float lati, float longi);

	CitiesDatabase() : database_inited(false) {};
	virtual ~CitiesDatabase() {};

};
