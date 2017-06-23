#include "stdafx.h"
#include "SkyBuilder.h"
#include "SkyGen.h"
#include "SunPositionCalculator.h"
#include <vector>
#include <assert.h>

// -----------------------------------------------------------------------------
SkyBuilder::SkyBuilder() 
	: m_imageBuffer(NULL)
	, m_imageWidth(0)
	, m_imageHeight(0)
{
}

// -----------------------------------------------------------------------------
SkyBuilder::~SkyBuilder()
{
}

// -----------------------------------------------------------------------------
void SkyBuilder::calculateSunPosition()
{
	// Determine whether the sun position should be
	// calculated directly from azimuth and altitude,
	// or if date, time and location should be used.
	if (m_attributes.sunPositionType == SkyAttributes::kAltitudeAzimuth)
	{
		m_sunAzimuth = m_attributes.azimuth;
		m_sunAltitude = m_attributes.altitude;
	}
	else
		calculateSunPositionGeographic();

	// Rotate so North matches Maya's default North.
	m_sunAzimuth -= 180;

	// Before this point, m_sunAltitude and m_sunAzimuth are in degrees

	// Convert to radians.
	m_sunAzimuth = toRadians(m_sunAzimuth);
	m_sunAltitude = toRadians(fmaxf(m_sunAltitude, -88));

	// Calculate the sun's direction vector.
	float phi = (PI_F * 0.5f) + m_sunAltitude;
	float theta = 0; // -m_sunAzimuth;
	float sinphi = sin(phi);

	m_sunDirection = Point3(
		cos(theta) * sinphi,
		sin(theta) * sinphi,
		-cos(phi)
	);
}

// -----------------------------------------------------------------------------
void SkyBuilder::calculateSunPositionGeographic()
{
	// Adjust time for daylight saving if required.
	bool daylightSaving = m_attributes.daylightSaving;
	int hours = m_attributes.hours;
	int day = m_attributes.day;
	int month = m_attributes.month;
	int year = m_attributes.year;

	if (daylightSaving)
		adjustDaylightSavingTime(hours, day, month, year);

	// Initialize the sun position calculator.
	SunPositionCalculator pc;
	pc.year = year;
	pc.month = month;
	pc.day = day;
	pc.hour = hours;
	pc.minute = m_attributes.minutes;
	pc.second = m_attributes.seconds;
	pc.timezone = m_attributes.timeZone;
	pc.delta_ut1 = 0;
	pc.delta_t = 67;
	pc.longitude = m_attributes.longitude;
	pc.latitude = m_attributes.latitude;
	pc.elevation = 0.0;
	pc.pressure = 820;
	pc.temperature = 11;
	pc.slope = 0;
	pc.azm_rotation = 0;
	pc.atmos_refract = 0.5667;
	pc.function = SunPositionCalculator::SPA_ALL;

	// Calculate the sun azimuth and altitude angles.
	pc.calculate();
	m_sunAzimuth = static_cast<float>(pc.azimuth);
	m_sunAltitude = static_cast<float>(pc.e);
}

// -----------------------------------------------------------------------------
void SkyBuilder::adjustDaylightSavingTime(int& hours, int& day, int& month, int& year) const
{
	static const int monthDays[] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };

	hours--;
	if (hours == -1)
	{
		hours = 23;
		day--;
		if (day == 0)
		{
			month--;
			if (month == 0)
			{
				month = 12;
				day = 31;
				year--;
			}
			else
			{
				if (month == 2)
				{
					bool leapdays = (year % 4 == 0) && (year % 400 == 0 || year % 100 != 0);
					if (leapdays)
						day = 29;
					else
						day = 28;
				}
				else
					day = monthDays[month - 1];
			}
		}
	}
}

// -----------------------------------------------------------------------------
bool SkyBuilder::createSkyImage()
{
	// Create the image buffer if necessary.
	if (!m_imageBuffer)
		return false;

	// Initialize the sky generator.
	SkyGen sg;
	sg.saturation = m_attributes.saturation;
	sg.night_color = MColor(0, 0, 0);
	sg.rgb_unit_conversion = MColor(0.0001f, 0.0001f, 0.0001f);
#ifdef USE_DIRECTIONAL_SKY_LIGHT
	sg.sun_disk_intensity = 0.01f;
#else
	sg.sun_disk_intensity = 100.0f;
#endif
	sg.haze = m_attributes.turbidity;
	sg.horizon_height = m_attributes.horizonHeight;
	sg.horizon_blur = m_attributes.horizonBlur;
	sg.ground_color = m_attributes.groundColor;
	sg.sun_disk_scale = m_attributes.sunDiskSize;
	sg.sun_glow_intensity = m_attributes.sunGlow;
	sg.multiplier = 1.0; // controlled outside, as RPR light's parameter
	sg.filter_color = m_attributes.filterColor;
	
	sg.sun_direction = m_sunDirection;

	// Generate the image.
	sg.generate(m_imageWidth, m_imageHeight, m_imageBuffer);

	// Calculate the directional sun light colour.
	SkyColor c = sg.computeColor(sg.sun_direction);
	m_sunLightColor = c.asColor();
	return true;
}

void SkyBuilder::setImageData(int width, int height, SkyRgbFloat32 * rgb_buffer)
{
	m_imageWidth = width;
	m_imageHeight = height;
	m_imageBuffer = rgb_buffer;
}


////////////////////////////////////////////////////////////////////////////////////
// > Exports
////////////////////////////////////////////////////////////////////////////////////

SkyBuilder builder;


extern "C"  EXPORT void set_sun_horizontal_coordinate(float azimuth, float altitude)
{
	SkyAttributes &attr = builder.getAttributes();
	attr.azimuth = azimuth;
	attr.altitude = altitude;
	attr.sunPositionType = SkyAttributes::kAltitudeAzimuth;

	builder.calculateSunPosition();	
}


extern "C"  EXPORT void set_sun_time_location(float latitude, float longitude, 
											int year, int month, int day, 
											int hours, int minutes, int seconds, 
											float timeZone, bool daylightSaving)
{
	SkyAttributes &attr = builder.getAttributes();
	attr.latitude = latitude;
	attr.longitude = longitude;
	attr.year = year;
	attr.month = month;
	attr.day = day;
	attr.hours = hours;
	attr.minutes = minutes;
	attr.seconds = seconds;
	attr.timeZone = timeZone;
	attr.daylightSaving = daylightSaving;
	attr.sunPositionType = SkyAttributes::kTimeLocation;

	builder.calculateSunPosition();
}


extern "C"  EXPORT void set_sky_params( float turbidity, float sun_glow_intensity, float sun_disc_size,
										float horizon_height, float horizon_blur, float saturation, 
										void * filter_color, void * ground_color)
{
	SkyAttributes &attr = builder.getAttributes();

	attr.turbidity = turbidity;
	attr.sunGlow = sun_glow_intensity;
	attr.sunDiskSize = sun_disc_size;
	attr.horizonHeight = horizon_height;
	attr.horizonBlur = horizon_blur;
	attr.saturation = saturation;

	attr.filterColor = MColor(static_cast<float*>(filter_color));
	attr.groundColor = MColor(static_cast<float*>(ground_color));
}


extern "C"  EXPORT bool generate_sky_image(int width, int height, void * rgb_buffer)
{
	if (!rgb_buffer || width <= 0 || height <= 0)
		return false;

	builder.setImageData(width, height, (SkyRgbFloat32*)rgb_buffer);
	return builder.createSkyImage();
}


extern "C"  EXPORT float get_sun_azimuth()
{
	return builder.getSunAzimuth();
}

extern "C"  EXPORT float get_sun_altitude()
{
	return builder.getSunAltitude();
}