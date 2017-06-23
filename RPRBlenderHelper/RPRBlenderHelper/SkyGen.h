#pragma once

#if defined(MAX_PLUGIN)
	#include <max.h>
#elif defined(MAYA_PLUGIN)
	#include <maya/MFloatVector.h>
	#include <maya/MColor.h>
#endif


#include <vector>
#include <ctime>
#include <cstdlib>

#define Scalar double
#define GLOBAL_SCALE 0.3f // do not allow too bright skies

#ifndef PI
#define PI 3.14159265358979323846
#endif

struct SkyRgbFloat32
{
	float r, g, b;
	SkyRgbFloat32() : r(0), g(0), b(0) {};
};

struct SkyColor
{
	Scalar r, g, b;
	SkyColor() : r(0), g(0), b(0) {}
	SkyColor(Scalar r, Scalar g, Scalar b) : r(r), g(g), b(b) {}

	void sanitize()
	{
		if (isnan(r))
			r = 0;
		if (isnan(g))
			g = 0;
		if (isnan(b))
			b = 0;

		r = fmin(10000, fmax(0, r));
		g = fmin(10000, fmax(0, g));
		b = fmin(10000, fmax(0, b));
	}

#if defined(MAX_PLUGIN)
	Color asColor() { return Color(static_cast<float>(r), static_cast<float>(g), static_cast<float>(b)); }
	SkyColor& operator = (const Color& v) { r = v.r; g = v.g; b = v.b; return *this; }
#elif defined(MAYA_PLUGIN)
	MColor asColor() { return MColor(static_cast<float>(r), static_cast<float>(g), static_cast<float>(b)); }
	SkyColor& operator = (const MColor& v) { r = v.r; g = v.g; b = v.b; return *this; }
#elif defined(BLENDER_PLUGIN)
	MColor asColor() { return MColor(static_cast<float>(r), static_cast<float>(g), static_cast<float>(b)); }
	SkyColor& operator = (const MColor& v) { r = v.r; g = v.g; b = v.b; return *this; }
#endif

	SkyColor operator * (Scalar v) const { return SkyColor(r * v, g * v, b * v); }
	SkyColor operator / (Scalar v) const { return SkyColor(r / v, g / v, b / v); }
	SkyColor operator * (const SkyColor& v) const { return SkyColor(r * v.r, g * v.g, b * v.b); }
	SkyColor operator / (const SkyColor& v) const { return SkyColor(r / v.r, g / v.g, b / v.b); }
	SkyColor operator + (Scalar v) const { return SkyColor(r + v, g + v, b + v); }
	SkyColor operator - (Scalar v) const { return SkyColor(r - v, g - v, b - v); }
	SkyColor operator + (const SkyColor& v) const { return SkyColor(r + v.r, g + v.g, b + v.b); }
	SkyColor operator - (const SkyColor& v) const { return SkyColor(r - v.r, g - v.g, b - v.b); }
	SkyColor& operator *= (Scalar v) { r *= v; g *= v; b *= v; return *this; }
	SkyColor& operator /= (Scalar v) { r /= v; g /= v; b /= v; return *this; }
	SkyColor& operator *= (const SkyColor& v) { r *= v.r; g *= v.g; b *= v.b; return *this; }
	SkyColor& operator /= (const SkyColor& v) { r /= v.r; g /= v.g; b /= v.b; return *this; }
	SkyColor& operator += (Scalar v) { r += v; g += v; b += v; return *this; }
	SkyColor& operator -= (Scalar v) { r -= v; g -= v; b -= v; return *this; }
	SkyColor& operator += (const SkyColor& v) { r += v.r; g += v.g; b += v.b; return *this; }
	SkyColor& operator -= (const SkyColor& v) { r -= v.r; g -= v.g; b -= v.b; return *this; }
};


#ifdef MAYA_PLUGIN

// Define wrapper from MFloatVector to Max's Point3 class.
class Point3 : public MFloatVector
{
public:
	Point3()
	{}
	Point3(float x, float y, float z)
	: MFloatVector(x, y, z)
	{}
	Point3& operator=(const MFloatVector& other)
	{
		MFloatVector::operator=(other);
		return *this;
	}
	float Length()
	{
		return length();
	}
	Point3 Normalize() const
	{
		Point3 result = *this;
		result.normalize();
		return result;
	}
	friend inline float DotProd(const Point3& A, const Point3& B)
	{
		return A * B;
	}
};

class Point2
{
public:
	Point2()
	{}
	Point2(float inX, float inY)
	: x(inX)
	, y(inY)
	{}

	float	x;
	float	y;
};

#endif // MAYA_PLUGIN

class SkyGen
{
public:
	bool on = true;
	Scalar multiplier = 0.23;
	SkyColor rgb_unit_conversion = SkyColor(0.0001, 0.0001, 0.0001);
	Scalar haze = 0.2;
	SkyColor filter_color = SkyColor(0.0, 0.0, 0.0);
	Scalar saturation = 1.0;
	Scalar horizon_height = 0.001;
	Scalar horizon_blur = 0.1;
	SkyColor ground_color = SkyColor(0.4, 0.4, 0.4);
	SkyColor night_color = SkyColor(0.0, 0.0, 0.0);
	Point3 sun_direction = Point3(0.0f, 0.3f, 0.4f);
	Scalar sun_disk_intensity = 0.01;
	Scalar sun_disk_scale = 0.5;
	Scalar sun_glow_intensity = 1.0;
	bool y_is_up = false;

private:

	Scalar sun_glow_intensity_adjusted;

	Scalar smoothstep(const Scalar& a, const Scalar& b, const Scalar& x)
	{
		if (x <= a)
			return 0.0;
		if (x >= b)
			return 1.0;
		Scalar xx = (x - a) / (b - a);
		if (xx < 0.0)
			xx = 0.0;
		else if (xx > 1.0)
			xx = 1.0;
		return xx * xx * (3.0 - 2.0 * xx);
	}

	void square_to_disk(Scalar& inout_r, Scalar& inout_phi, const Scalar& in_x, const Scalar& in_y)
	{
		Scalar local_x = 2 * in_x - 1;
		Scalar local_y = 2 * in_y - 1;
		if (local_x == 0.0 && local_y == 0.0)
		{
			inout_phi = 0.0;
			inout_r = 0.0;
		}
		else
		{
			if (local_x > -local_y)
			{
				if (local_x > local_y)
				{
					inout_r = local_x;
					inout_phi = (PI / 4.0) * (1.0 + local_y / local_x);
				}
				else
				{
					inout_r = local_y;
					inout_phi = (PI / 4.0) * (3.0 - local_x / local_y);
				}
			}
			else
			{
				if (local_x < local_y)
				{
					inout_r = -local_x;
					inout_phi = (PI / 4.0) * (5.0 + local_y / local_x);
				}
				else
				{
					inout_r = -local_y;
					inout_phi = (PI / 4.0) * (7.0 - local_x / local_y);
				}
			}
		}
	}

	void xyz2dir(Point3& inout_dir, const Point3& in_main, const Scalar& x, const Scalar& y, const Scalar& z)
	{
		Point3 u;
		Point3 v;
		Point3 omain = in_main;
		if (abs(omain.x) < abs(omain.y))
		{
			u.x = 0.0;
			u.y = -omain.z;
			u.z = omain.y;
		}
		else
		{
			u.x = omain.z;
			u.y = 0.0;
			u.z = -omain.x;
		}
		if (u.Length() == 0.0)
		{
			if (abs(in_main.x) < abs(in_main.y))
			{
				u.x = 0.0;
				u.y = -in_main.z;
				u.z = in_main.y;
			}
			else
			{
				u.x = in_main.z;
				u.y = 0.0;
				u.z = -in_main.x;
			}
		}
		u = u.Normalize();
		v.Cross(in_main, u);
		inout_dir = float(x) * u + float(y) * v + float(z) * in_main;
	}

	void reflection_dir_diffuse_x(Point3& inout_refl_dir, const Point3& in_normal, const Point2& in_sample)
	{
		Scalar r = 0.0;
		Scalar phi = 0.0;

		square_to_disk(r, phi, in_sample.x, in_sample.y);
		Scalar x = r * cos(phi);
		Scalar y = r * sin(phi);

		Scalar z2 = 1.0 - x * x - y * y;
		Scalar z;
		if (z2 > 0.0)
		{
			z = sqrt(z2);
		}
		else
		{
			z = 0.0;
		}
		xyz2dir(inout_refl_dir, in_normal, x, y, z);
	}

	Scalar sky_luminance(const Point3& in_dir, const Point3& in_sun_pos, const Scalar& in_turbidity)
	{
		Scalar cos_gamma = DotProd(in_sun_pos, in_dir);
		if (cos_gamma < 0.0)
		{
			cos_gamma = 0.0;
		}
		if (cos_gamma > 1.0)
		{
			cos_gamma = 2.0 - cos_gamma;
		}
		Scalar gamma = acos(cos_gamma);
		Scalar cos_theta = in_dir.z;
		Scalar cos_theta_sun = in_sun_pos.z;
		Scalar theta_sun = acos(cos_theta_sun);

		Scalar A = 0.178721 * in_turbidity - 1.463037;
		Scalar B = -0.355402 * in_turbidity + 0.427494;
		Scalar C = -0.022669 * in_turbidity + 5.325056;
		Scalar D = 0.120647 * in_turbidity - 2.577052;
		Scalar E = -0.066967 * in_turbidity + 0.370275;

		Scalar Y = (((1 + A * exp(B / cos_theta)) * (1 + C * exp(D * gamma) +
			E * cos_gamma * cos_gamma)) /
			((1 + A * exp(B / 1.0)) * (1 + C * exp(D * theta_sun) +
				E * cos_theta_sun * cos_theta_sun)));
		return Y;
	}

	SkyColor calc_sun_color(const Point3& sun_dir, const Scalar& turbidity)
	{
		// Note: this function depends on sun_dir.z and turbidity, which are constants during image generation
		// Simple optimization: cache value.
		static Point3 cached_sun_dir(0, 0, 0);
		static Scalar cached_turbidity = -1;
		static SkyColor cached_result(0, 0, 0);
		if (sun_dir == cached_sun_dir && turbidity == cached_turbidity)
		{
			return cached_result;
		}

		SkyColor sun_color = SkyColor(0.0, 0.0, 0.0);
		SkyColor ko = SkyColor(12.0, 8.5, 0.9);
		SkyColor wavelength = SkyColor(0.610, 0.550, 0.470);
		SkyColor solRad = SkyColor(1.0 * 127500 / 0.9878,
			0.992 * 127500 / 0.9878,
			0.911 * 127500 / 0.9878);
		if (sun_dir.z > 0.0)
		{
			// constant: M_M_PI
			Scalar m = (1.0 / (sun_dir.z + 0.15 * pow(93.885f - acos(sun_dir.z) * 180 / PI, -1.253)));
			Scalar beta = 0.04608 * turbidity - 0.04586;
			Scalar alpha = 1.3;
			SkyColor ta, to, tr;
			// aerosol (water + dust) attenuation
			ta.r = exp(-m * beta * pow(wavelength.r, -alpha));
			ta.g = exp(-m * beta * pow(wavelength.g, -alpha));
			ta.b = exp(-m * beta * pow(wavelength.b, -alpha));
			// ozone absorption
			Scalar l = 0.0035;
			to.r = exp(-m * ko.r * l);
			to.g = exp(-m * ko.g * l);
			to.b = exp(-m * ko.b * l);
			// Rayleigh scattering
			tr.r = exp(-m * 0.008735 * pow(wavelength.r, -4.08));
			tr.g = exp(-m * 0.008735 * pow(wavelength.g, -4.08));
			tr.b = exp(-m * 0.008735 * pow(wavelength.b, -4.08));
			// result
			sun_color.r = tr.r * ta.r * to.r * solRad.r;
			sun_color.g = tr.g * ta.g * to.g * solRad.g;
			sun_color.b = tr.b * ta.b * to.b * solRad.b;
		}

		// cache result
		cached_sun_dir = sun_dir;
		cached_turbidity = turbidity;
		cached_result = sun_color;

		return sun_color;
	}

	void vectortweak(Point3& dir, bool y_is_up, const Scalar& horiz_height)
	{
		if (y_is_up)
		{
			float w = dir.z;
			dir.z = dir.y;
			dir.y = w;
		}
		if (horiz_height != 0)
		{
			dir.z -= static_cast<float>(horiz_height);
			dir = dir.Normalize();
		}
	}

	Point3 sky_color_xyz(const Point3& in_dir, const Point3& in_sun_pos, const Scalar& in_turbidity, const Scalar& in_luminance)
	{
		Point3 xyz;
		Scalar A, B, C, D, E;
		Scalar cos_gamma = DotProd(in_sun_pos, in_dir);
		if (cos_gamma > 1.0)
		{
			cos_gamma = 2.0 - cos_gamma;
		}
		Scalar gamma = acos(cos_gamma);
		Scalar cos_theta = in_dir.z;
		Scalar cos_theta_sun = in_sun_pos.z;
		Scalar theta_sun = acos(cos_theta_sun);
		Scalar t2 = in_turbidity * in_turbidity;
		Scalar ts2 = theta_sun * theta_sun;
		Scalar ts3 = ts2 * theta_sun;
		// determine x and y at zenith
		Scalar zenith_x = ((+0.001650*ts3 - 0.003742*ts2 +
			0.002088*theta_sun + 0) * t2 +
			(-0.029028*ts3 + 0.063773*ts2 -
				0.032020*theta_sun + 0.003948) * in_turbidity +
				(+0.116936*ts3 - 0.211960*ts2 +
					0.060523*theta_sun + 0.258852));
		Scalar zenith_y = ((+0.002759*ts3 - 0.006105*ts2 +
			0.003162*theta_sun + 0) * t2 +
			(-0.042149*ts3 + 0.089701*ts2 -
				0.041536*theta_sun + 0.005158) * in_turbidity +
				(+0.153467*ts3 - 0.267568*ts2 +
					0.066698*theta_sun + 0.266881));
		xyz.y = static_cast<float>(in_luminance);
		A = -0.019257 * in_turbidity - (0.29 - pow(cos_theta_sun, 0.5) * 0.09);

		B = -0.066513 * in_turbidity + 0.000818;
		C = -0.000417 * in_turbidity + 0.212479;
		D = -0.064097 * in_turbidity - 0.898875;
		E = -0.003251 * in_turbidity + 0.045178;
		Scalar x = (((1 + A * exp(B / cos_theta)) * (1 + C * exp(D * gamma) +
			E * cos_gamma * cos_gamma)) /
			((1 + A * exp(B / 1.0)) * (1 + C * exp(D * theta_sun) +
				E * cos_theta_sun * cos_theta_sun)));
		A = -0.016698 * in_turbidity - 0.260787;
		B = -0.094958 * in_turbidity + 0.009213;
		C = -0.007928 * in_turbidity + 0.210230;
		D = -0.044050 * in_turbidity - 1.653694;
		E = -0.010922 * in_turbidity + 0.052919;
		Scalar y = (((1 + A * exp(B / cos_theta)) * (1 + C * exp(D * gamma) +
			E * cos_gamma * cos_gamma)) /
			((1 + A * exp(B / 1.0)) * (1 + C * exp(D * theta_sun) +
				E * cos_theta_sun * cos_theta_sun)));
		Scalar local_saturation = 1.0;
		x = zenith_x * ((x * local_saturation) + (1.0 - local_saturation));
		y = zenith_y * ((y * local_saturation) + (1.0 - local_saturation));
		// convert chromaticities x and y to CIE
		xyz.x = static_cast<float>((x / y) * xyz.y);
		xyz.z = static_cast<float>(((1.0 - x - y) / y) * xyz.y);
		return xyz;
	}

	SkyColor calc_env_color(const Point3& in_sun_dir, const Point3& in_dir, const Scalar& in_turbidity)
	{
		SkyColor env_color = SkyColor(0.0, 0.0, 0.0);
		// start with absolute value of zenith luminace in K cd/m2
		Scalar theta_sun = acos(in_sun_dir.z);
		Scalar chi = (4.0 / 9.0 - in_turbidity / 120.0) * (PI - 2 * theta_sun);
		Scalar luminance = (1000.0 * (4.0453 * in_turbidity - 4.9710) * tan(chi) -
			0.2155 * in_turbidity + 2.4192);
		luminance *= sky_luminance(in_dir, in_sun_dir, in_turbidity);
		// calculate the sky colour - this uses 2 matrices (for 'x' and for 'y')
		Point3 XYZ = sky_color_xyz(in_dir, in_sun_dir, in_turbidity, luminance);
		// use result
		env_color.r = 3.241 * XYZ.x - 1.537 * XYZ.y - 0.499 * XYZ.z;
		env_color.g = -0.969 * XYZ.x + 1.876 * XYZ.y + 0.042 * XYZ.z;
		env_color.b = 0.056 * XYZ.x - 0.204 * XYZ.y + 1.057 * XYZ.z;
		env_color *= PI;
		return env_color;
	}

	class Sample_iterator
	{
	public:
		Sample_iterator(int size)
		{
			mGen.resize(size);
			std::srand(static_cast<unsigned int>(std::time(0)));
			for (int i = 0; i < size; i++)
			{
				mGen[i].x = 0.5f;
				mGen[i].y = 0.5f;
			}
			const float rho = 0.8f;
			const float orho = sqrt(1.0f - rho);
			for (int i = 0; i < size; i++)
				mGen[i].y = rho * mGen[i].x + orho * mGen[i].y;
		}
		std::vector<Point2> mGen;
	};

	SkyColor calc_irrad(const Point3& in_data_sun_dir, const Scalar& in_data_sun_dir_haze)
	{
		// result of this function depends on sun direction and constant - cache this value.
		static Point3 cached_sun_dir(0, 0, 0);
		static Scalar cached_sun_dir_haze = -1;
		static SkyColor cached_result(0, 0, 0);
		if (in_data_sun_dir == cached_sun_dir && in_data_sun_dir_haze == cached_sun_dir_haze)
		{
			return cached_result;
		}

		SkyColor colaccu = SkyColor(0.0, 0.0, 0.0);
		Point3 nuState_normal = Point3(0.0f, 0.0f, 1.0f);
		Point3 nuState_normal_geom = nuState_normal;
		Point3 sun_dir = in_data_sun_dir;
		if (sun_dir.z < 0.001)
		{
			sun_dir.z = 0.001f;
			sun_dir = sun_dir.Normalize();
		}

		Sample_iterator si(2);
		Point2 sample = Point2(0.0f, 0.0f);
		Point3 diff = Point3(0.0f, 0.0f, 0.0f);
		SkyColor work = SkyColor(0.0, 0.0, 0.0);
		for (auto sample : si.mGen)
		{
			reflection_dir_diffuse_x(diff, nuState_normal, sample);
			work = calc_env_color(sun_dir, diff, in_data_sun_dir_haze);
			colaccu += work;
		}
		colaccu /= Scalar(si.mGen.size());

		cached_sun_dir = in_data_sun_dir;
		cached_sun_dir_haze = in_data_sun_dir_haze;
		cached_result = colaccu;

		return colaccu;
	}

	void tweak_saturation(Scalar& inout_saturation, const Scalar& in_haze)
	{
		Scalar lowsat = pow(inout_saturation, 3.0);
		if (inout_saturation <= 1.0)
		{
			Scalar local_haze = in_haze;
			local_haze -= 2.0;
			local_haze /= 15.0;
			if (local_haze < 0.0) local_haze = 0.0;
			if (local_haze > 1.0) local_haze = 1.0;
			local_haze = pow(local_haze, 3.0);
			inout_saturation = ((inout_saturation * (1.0 - local_haze)) +
				lowsat * local_haze);
		}
	}

	void colortweak(SkyColor& color, const Scalar& saturation, const SkyColor& filter_color)
	{
		SkyColor luminance_weight = SkyColor(0.212671, 0.715160, 0.072169);
		Scalar intensity = (color.r * luminance_weight.r + color.g * luminance_weight.g + color.b * luminance_weight.b);
		if (color.r < 0.0) color.r = 0.0;
		if (color.g < 0.0) color.g = 0.0;
		if (color.b < 0.0) color.b = 0.0;
		if (saturation <= 0.0)
		{
			color.r = color.g = color.b = intensity;
		}
		else
		{
			color = color * saturation + intensity * (1.0 - saturation);
			// boosted saturation can cause negatives
			if (saturation > 1.0)
			{
				if (color.r < 0.0) color.r = 0.0;
				if (color.g < 0.0) color.g = 0.0;
				if (color.b < 0.0) color.b = 0.0;
			}
		}
		// redness
		//color.r *= 1.0 + redness;
		//color.b *= 1.0 - redness;

		color.r *= 1.0 + filter_color.r;
		color.g *= 1.0 + filter_color.g;
		color.b *= 1.0 + filter_color.b;
	}

public:
	SkyColor computeColor(const Point3 &direction)
	{
		SkyColor result = SkyColor(0.0, 0.0, 0.0);
		Scalar factor = 1.0;
		SkyColor out_color = SkyColor(0.0, 0.0, 0.0);
		SkyColor rgb_scale = rgb_unit_conversion;
		Point3 dir = direction;
		Scalar horiz_height = horizon_height / 10.0;
		vectortweak(dir, y_is_up, horiz_height);
		// haze
		Scalar local_haze = 2.0 + haze;
		if (local_haze < 2.0)
		{
			local_haze = 2.0;
		}
		Scalar local_saturation = saturation;
		tweak_saturation(local_saturation, local_haze);
		// rgb_scale
		if (rgb_scale.r < 0.0)
		{
			rgb_scale.r = rgb_scale.g = rgb_scale.b = 1.0 / 80000.0;
		}
		rgb_scale *= multiplier;
		if (multiplier <= 0.0 || !on)
		{
			result = SkyColor(0.0, 0.0, 0.0);
		}
		else
		{
			// downness
			Scalar downness = dir.z;
			// only calc for above-the-horizon
			if (dir.z < 0.001)
			{
				dir.z = 0.001f;
				dir = dir.Normalize();
			}
			// sun_dir
			Point3 sun_dir = sun_direction;
			sun_dir = sun_dir.Normalize();
			vectortweak(sun_dir, y_is_up, horiz_height);
			if (sun_dir.z < 0.001)
			{
				if (sun_dir.z < 0.0)
				{
					factor = 1.0 + sun_dir.z;
				}
			}

			SkyColor data_sun_color = calc_sun_color(sun_dir, local_haze);

			if (downness <= 0.0)
			{
				// Lower hemisphere
				SkyColor downcolor = ground_color;
				Scalar data_sun_dir_haze = 2.0 + haze;
				if (data_sun_dir_haze < 2.0)
				{
					data_sun_dir_haze = 2.0;
				}
				SkyColor irrad = calc_irrad(sun_dir, data_sun_dir_haze);
				downcolor *= (irrad + data_sun_color * sun_dir.z);
				Scalar hor_blur = horizon_blur / 10.0;
				Scalar night_factor = 1.0;
				if (hor_blur > 0.0)
				{
					Scalar dness = -downness / hor_blur;
					dness = smoothstep(0.0, 1.0, dness);
					if (dness < 1.0)
					{
						// Call calc_env_color only when needed
						SkyColor color = calc_env_color(sun_dir, dir, local_haze) * factor;
						out_color = color * (1.0 - dness) + downcolor * dness;
					}
					else
					{
						out_color = downcolor;
					}
					night_factor = 1.0 - dness;
				}
				else
				{
					out_color = downcolor;
					night_factor = 0.0;
				}
				out_color *= GLOBAL_SCALE;

				if (night_factor > 0.0)
				{
					SkyColor night = night_color;
					night *= night_factor;
					if (out_color.r < night.r) out_color.r = night.r;
					if (out_color.g < night.g) out_color.g = night.g;
					if (out_color.b < night.b) out_color.b = night.b;
				}
			}
			else
			{
				// Upper hemisphere

				// Sky color
				SkyColor color = calc_env_color(sun_dir, dir, local_haze) * GLOBAL_SCALE;
				// Sun color
				if (sun_disk_intensity > 0.0 && sun_disk_scale > 0.0)
				{
					Scalar dot = fminf(1, fmaxf(-1, DotProd(dir, sun_dir)));
					Scalar sun_angle = acos(dot);
					Scalar sun_radius = 0.00465 * sun_disk_scale * 10.0;
					if (sun_angle < sun_radius)
					{
						static double glow_scale = 1000.0;
						static double sun_shift = 6e-6; // offset for making sunAmount(0) == 0
						static double base_sun_disk_value = 80.0f;
						static double sun_mul_factor = 500.0;
						static double p = 2.0;
						double sun_area_scale = sun_disk_scale * sun_disk_scale;
						if (sun_area_scale < 0.001) // don't divide by zero
							sun_area_scale = 0.001;
						double sun_disk_value = base_sun_disk_value / sun_area_scale; // adjust sun brightness by sun area
						Scalar x = 1.0 - sun_angle / sun_radius; // sun factor: 1.0 = center, 0.0 = border
						Scalar sunAmount;
						if (x < 0.9)
						{
							// 0 .. 0.9 is glow
							x = x / 0.9;
							sunAmount = (pow(10, 1.0 - log((1.0 - x) * sun_mul_factor)) - sun_shift) * glow_scale * sun_glow_intensity_adjusted;
							// do not glow brighter than sun
							if (sunAmount > sun_disk_value) sunAmount = sun_disk_value;
						}
						else
						{
							// 0.9 .. 1.0 (1/10 of radius) is sun disk - filled with constant color
							sunAmount = sun_disk_value;
						}
						if (sunAmount < 0) sunAmount = 0; // just in case
						Scalar sun_factor = sunAmount * sun_disk_intensity;
						color += data_sun_color * sun_factor;
					}
				}
				out_color = color;
			}

			// set the output
			out_color *= rgb_scale;

			colortweak(out_color, local_saturation, filter_color);
			result = out_color;
		}

		result.sanitize();

		return result;
	}

public:
	void generate(int w, int h, SkyRgbFloat32 *buffer);
};
