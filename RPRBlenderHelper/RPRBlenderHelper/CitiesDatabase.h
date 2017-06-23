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
