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

struct AzimuthZenithAngle
{
	double Azimuth;
	double Zenith;

	AzimuthZenithAngle(double A, double Z)
	{
		Azimuth = A;
		Zenith = Z;
	}
};

typedef double JulianDate;

/**
* Calculate topocentric solar position, i.e. the location of the sun on the sky for a certain point in time on a
* certain point of the Earth's surface.
*
* This follows the SPA algorithm described in Reda, I.; Andreas, A. (2003): Solar Position Algorithm for Solar
* Radiation Applications. NREL Report No. TP-560-34302, Revised January 2008. The algorithm is supposed to work for
* the years -2000 to 6000, with uncertainties of +/-0.0003 degrees.
*
* @param date        Observer's local date and time.
* @param latitude    Observer's latitude, in degrees (negative south of equator).
* @param longitude   Observer's longitude, in degrees (negative west of Greenwich).
* @param elevation   Observer's elevation, in meters.
* @param deltaT      Difference between earth rotation time and terrestrial time (or Universal Time and Terrestrial Time),
*                    in seconds. See
*                    <a href ="http://asa.usno.navy.mil/SecK/DeltaT.html">http://asa.usno.navy.mil/SecK/DeltaT.html</a>.
*                    For the year 2015, a reasonably accurate default would be 68.
* @param pressure    Annual average local pressure, in millibars (or hectopascals). Used for refraction
*                    correction of zenith angle. If unsure, 1000 is a reasonable default.
* @param temperature Annual average local temperature, in degrees Celsius. Used for refraction correction of zenith angle.
* @return Topocentric solar position (azimuth measured eastward from north)
* @see AzimuthZenithAngle
*/
AzimuthZenithAngle calculateSolarPosition(JulianDate jd, double latitude,
	double longitude, double elevation, double deltaT, double pressure,
	double temperature);

JulianDate julian_day(int y, int m, int day, int hour, int minute, int second, double tz);
