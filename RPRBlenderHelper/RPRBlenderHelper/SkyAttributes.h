#pragma once

#include "math_wrap.h"


class SkyAttributes
{

public:

	SkyAttributes() {};
	virtual ~SkyAttributes() {};


	// Properties
	// -----------------------------------------------------------------------------
	float turbidity = 0;
	float intensity = 0;
	float albedo = 0;
	float sunGlow = 0;
	float sunDiskSize = 0;
	short sunPositionType = 0;
	float horizonHeight = 0;
	float horizonBlur = 0;
	float saturation = 1;

	MColor groundColor;
	MColor filterColor;

	float azimuth = 0;
	float altitude = 0;

	float latitude = 0;
	float longitude = 0;
	float timeZone = 0;

	bool daylightSaving = false;
	int hours = 0;
	int minutes = 0;
	int seconds = 0;
	int day = 0;
	int month = 0;
	int year = 0;


	/** The method used for positioning the sun. */
	enum SunPositionType
	{
		kAltitudeAzimuth = 0,
		kTimeLocation
	};
};
