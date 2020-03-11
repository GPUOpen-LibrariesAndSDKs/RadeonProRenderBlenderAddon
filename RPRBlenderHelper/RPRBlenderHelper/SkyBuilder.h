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


#include "SkyAttributes.h"

// The following define will activate code which uses directional light as primary light
// source for sky. It is obsolete code and should be considered for removal later.
//#define USE_DIRECTIONAL_SKY_LIGHT 1



struct SkyRgbFloat32;

/**
 * The sky builder uses the sky dependency node as input
 * and reads the attributes to calculate the position of
 * the sun and update the sphere environment map.
 */
class SkyBuilder
{
public:
	SkyBuilder();
	virtual ~SkyBuilder();

	// in radians
	float getSunAzimuth	() const { return m_sunAzimuth; }
	float getSunAltitude() const { return m_sunAltitude; }
	
	/** Create the sky sphere map. */
	bool createSkyImage();

	/** Calculate the sun position. */
	void calculateSunPosition();

	void setImageData(int width, int height, SkyRgbFloat32 * rgb_buffer);
	
	SkyAttributes & getAttributes() { return m_attributes; }

private:

	/** Sky attributes. */
	SkyAttributes m_attributes;

	/** Sky image width. */
	unsigned int m_imageWidth;

	/** Sky image height. */
	unsigned int m_imageHeight;

	/** Storage space for the sky image. */
	SkyRgbFloat32* m_imageBuffer;

	/** Sun azimuth in radians. */
	float m_sunAzimuth;

	/** Sun altitude in radians. */
	float m_sunAltitude;

	/** Sun direction vector. */
	Point3 m_sunDirection;

	/** The colour of the directional sun light. */
	MColor m_sunLightColor;

	/** Calculate the sun position from location, date and time. */
	void calculateSunPositionGeographic();

	/** Adjust the given time values for daylight saving. */
	void adjustDaylightSavingTime(int& hours, int& day, int& month, int& year) const;
};
