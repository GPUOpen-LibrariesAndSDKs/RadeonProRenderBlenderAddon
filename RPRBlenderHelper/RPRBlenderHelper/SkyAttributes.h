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
