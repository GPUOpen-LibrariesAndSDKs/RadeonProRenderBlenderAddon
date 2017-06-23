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
