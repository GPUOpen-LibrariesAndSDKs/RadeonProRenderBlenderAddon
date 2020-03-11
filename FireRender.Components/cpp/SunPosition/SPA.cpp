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
#include <cmath>
#include <vector>

#include "SPA.h"

#define M_PI acos(-1.0)
#define toDegrees(a) (a * 180.0 / M_PI)
#define toRadians(a) (a * M_PI / 180.0)

int julian(int y, int m, int d) {
	return 367 * y -
		(7 * (y + (m + 9) / 12)) / 4 -
		(3 * ((y + (m - 9) / 7) / 100 + 1)) / 4 +
		275 * m / 9 + d + 1721029;
}

void gregorian(int j, int *year, int *month, int *day) {
	int a = j + 68569;
	int b = 4 * a / 146097;
	int c = a - (146097 * b + 3) / 4;
	int d = 4000 * (c + 1) / 1461001;
	int e = c - 1461 * d / 4 + 31;
	int f = 80 * e / 2447;
	int g = f / 11;
	int h = e - 2447 * f / 80;
	int m = f + 2 - 12 * g;
	int y = 100 * (b - 49) + d + g;

	*year = y; *month = m; *day = h;
}


double getJulianEphemerisDay(double jd, double delta_t)
{
	return jd + delta_t / 86400.0;
}

double getJulianEphemerisMillennium(double jce)
{
	return (jce / 10.0);
}

double getJulianEphemerisCentury(double jd)
{
	return (jd - 2451545.0) / 36525.0;
}

std::vector<std::vector<std::vector<double>>> TERMS_L = {
	{ { 175347046.0, 0, 0 },{ 3341656.0, 4.6692568, 6283.07585 },{ 34894.0, 4.6261, 12566.1517 },
	{ 3497.0, 2.7441, 5753.3849 },{ 3418.0, 2.8289, 3.5231 },{ 3136.0, 3.6277, 77713.7715 },
	{ 2676.0, 4.4181, 7860.4194 },{ 2343.0, 6.1352, 3930.2097 },{ 1324.0, 0.7425, 11506.7698 },
	{ 1273.0, 2.0371, 529.691 },{ 1199.0, 1.1096, 1577.3435 },{ 990, 5.233, 5884.927 },
	{ 902, 2.045, 26.298 },{ 857, 3.508, 398.149 },{ 780, 1.179, 5223.694 },
	{ 753, 2.533, 5507.553 },{ 505, 4.583, 18849.228 },{ 492, 4.205, 775.523 },{ 357, 2.92, 0.067 },
	{ 317, 5.849, 11790.629 },{ 284, 1.899, 796.298 },{ 271, 0.315, 10977.079 },
	{ 243, 0.345, 5486.778 },{ 206, 4.806, 2544.314 },{ 205, 1.869, 5573.143 },
	{ 202, 2.458, 6069.777 },{ 156, 0.833, 213.299 },{ 132, 3.411, 2942.463 },
	{ 126, 1.083, 20.775 },{ 115, 0.645, 0.98 },{ 103, 0.636, 4694.003 },{ 102, 0.976, 15720.839 },
	{ 102, 4.267, 7.114 },{ 99, 6.21, 2146.17 },{ 98, 0.68, 155.42 },{ 86, 5.98, 161000.69 },
	{ 85, 1.3, 6275.96 },{ 85, 3.67, 71430.7 },{ 80, 1.81, 17260.15 },{ 79, 3.04, 12036.46 },
	{ 75, 1.76, 5088.63 },{ 74, 3.5, 3154.69 },{ 74, 4.68, 801.82 },{ 70, 0.83, 9437.76 },
	{ 62, 3.98, 8827.39 },{ 61, 1.82, 7084.9 },{ 57, 2.78, 6286.6 },{ 56, 4.39, 14143.5 },
	{ 56, 3.47, 6279.55 },{ 52, 0.19, 12139.55 },{ 52, 1.33, 1748.02 },{ 51, 0.28, 5856.48 },
	{ 49, 0.49, 1194.45 },{ 41, 5.37, 8429.24 },{ 41, 2.4, 19651.05 },{ 39, 6.17, 10447.39 },
	{ 37, 6.04, 10213.29 },{ 37, 2.57, 1059.38 },{ 36, 1.71, 2352.87 },{ 36, 1.78, 6812.77 },
	{ 33, 0.59, 17789.85 },{ 30, 0.44, 83996.85 },{ 30, 2.74, 1349.87 },{ 25, 3.16, 4690.48 } },
	
	{ { 628331966747.0, 0, 0 },{ 206059.0, 2.678235, 6283.07585 },{ 4303.0, 2.6351, 12566.1517 },
	{ 425.0, 1.59, 3.523 },{ 119.0, 5.796, 26.298 },{ 109.0, 2.966, 1577.344 },
	{ 93, 2.59, 18849.23 },{ 72, 1.14, 529.69 },{ 68, 1.87, 398.15 },{ 67, 4.41, 5507.55 },
	{ 59, 2.89, 5223.69 },{ 56, 2.17, 155.42 },{ 45, 0.4, 796.3 },{ 36, 0.47, 775.52 },
	{ 29, 2.65, 7.11 },{ 21, 5.34, 0.98 },{ 19, 1.85, 5486.78 },{ 19, 4.97, 213.3 },
	{ 17, 2.99, 6275.96 },{ 16, 0.03, 2544.31 },{ 16, 1.43, 2146.17 },{ 15, 1.21, 10977.08 },
	{ 12, 2.83, 1748.02 },{ 12, 3.26, 5088.63 },{ 12, 5.27, 1194.45 },{ 12, 2.08, 4694 },
	{ 11, 0.77, 553.57 },{ 10, 1.3, 6286.6 },{ 10, 4.24, 1349.87 },{ 9, 2.7, 242.73 },
	{ 9, 5.64, 951.72 },{ 8, 5.3, 2352.87 },{ 6, 2.65, 9437.76 },{ 6, 4.67, 4690.48 } },
	
	{ { 52919.0, 0, 0 },{ 8720.0, 1.0721, 6283.0758 },{ 309.0, 0.867, 12566.152 },{ 27, 0.05, 3.52 },
	{ 16, 5.19, 26.3 },{ 16, 3.68, 155.42 },{ 10, 0.76, 18849.23 },{ 9, 2.06, 77713.77 },
	{ 7, 0.83, 775.52 },{ 5, 4.66, 1577.34 },{ 4, 1.03, 7.11 },{ 4, 3.44, 5573.14 },
	{ 3, 5.14, 796.3 },{ 3, 6.05, 5507.55 },{ 3, 1.19, 242.73 },{ 3, 6.12, 529.69 },
	{ 3, 0.31, 398.15 },{ 3, 2.28, 553.57 },{ 2, 4.38, 5223.69 },{ 2, 3.75, 0.98 } },
	{ { 289.0, 5.844, 6283.076 },{ 35, 0, 0 },{ 17, 5.49, 12566.15 },{ 3, 5.2, 155.42 },{ 1, 4.72, 3.52 },
	{ 1, 5.3, 18849.23 },{ 1, 5.97, 242.73 } },
	{ { 114.0, 3.142, 0 },{ 8, 4.13, 6283.08 },{ 1, 3.84, 12566.15 } },
	{ { 1, 3.14, 0 } }};

std::vector<std::vector<std::vector<double>>> TERMS_B = {
	{ { 280.0, 3.199, 84334.662 },{ 102.0, 5.422, 5507.553 },{ 80, 3.88, 5223.69 },{ 44, 3.7, 2352.87 }, { 32, 4, 1577.34 } }, 
	{ { 9, 3.9, 5507.55 },{ 6, 1.73, 5223.69 } } };

std::vector<std::vector<std::vector<double>>> TERMS_R = {
	{ { 100013989.0, 0, 0 },{ 1670700.0, 3.0984635, 6283.07585 },{ 13956.0, 3.05525, 12566.1517 },
	{ 3084.0, 5.1985, 77713.7715 },{ 1628.0, 1.1739, 5753.3849 },{ 1576.0, 2.8469, 7860.4194 },
	{ 925.0, 5.453, 11506.77 },{ 542.0, 4.564, 3930.21 },{ 472.0, 3.661, 5884.927 },
	{ 346.0, 0.964, 5507.553 },{ 329.0, 5.9, 5223.694 },{ 307.0, 0.299, 5573.143 },
	{ 243.0, 4.273, 11790.629 },{ 212.0, 5.847, 1577.344 },{ 186.0, 5.022, 10977.079 },
	{ 175.0, 3.012, 18849.228 },{ 110.0, 5.055, 5486.778 },{ 98, 0.89, 6069.78 },
	{ 86, 5.69, 15720.84 },{ 86, 1.27, 161000.69 },{ 65, 0.27, 17260.15 },{ 63, 0.92, 529.69 },
	{ 57, 2.01, 83996.85 },{ 56, 5.24, 71430.7 },{ 49, 3.25, 2544.31 },{ 47, 2.58, 775.52 },
	{ 45, 5.54, 9437.76 },{ 43, 6.01, 6275.96 },{ 39, 5.36, 4694 },{ 38, 2.39, 8827.39 },
	{ 37, 0.83, 19651.05 },{ 37, 4.9, 12139.55 },{ 36, 1.67, 12036.46 },{ 35, 1.84, 2942.46 },
	{ 33, 0.24, 7084.9 },{ 32, 0.18, 5088.63 },{ 32, 1.78, 398.15 },{ 28, 1.21, 6286.6 },
	{ 28, 1.9, 6279.55 },{ 26, 4.59, 10447.39 } },
	
	{ { 103019.0, 1.10749, 6283.07585 },{ 1721.0, 1.0644, 12566.1517 },{ 702.0, 3.142, 0 },
	{ 32, 1.02, 18849.23 },{ 31, 2.84, 5507.55 },{ 25, 1.32, 5223.69 },{ 18, 1.42, 1577.34 },
	{ 10, 5.91, 10977.08 },{ 9, 1.42, 6275.96 },{ 9, 0.27, 5486.78 } },
	
	{ { 4359.0, 5.7846, 6283.0758 },{ 124.0, 5.579, 12566.152 },{ 12, 3.14, 0 },{ 9, 3.63, 77713.77 },
	{ 6, 1.87, 5573.14 },{ 3, 5.47, 18849.23 } },
	
	{ { 145.0, 4.273, 6283.076 },{ 7, 3.92, 12566.15 } },
	
	{ { 4, 2.56, 6283.08 } }

};

std::vector<std::vector<double>> NUTATION_COEFFS = {
	{ 297.85036, 445267.111480, -0.0019142, 1.0 / 189474 }, { 357.52772, 35999.050340, -0.0001603, -1.0 / 300000 }, { 134.96298, 477198.867398, 0.0086972, 1.0 / 56250 },
	{ 93.27191, 483202.017538, -0.0036825, 1.0 / 327270 },{ 125.04452, -1934.136261, 0.0020708, 1.0 / 450000 } 
};

std::vector<std::vector<double>> TERMS_Y = { { 0, 0, 0, 0, 1 },{ -2, 0, 0, 2, 2 },{ 0, 0, 0, 2, 2 },
{ 0, 0, 0, 0, 2 },{ 0, 1, 0, 0, 0 },{ 0, 0, 1, 0, 0 },{ -2, 1, 0, 2, 2 },{ 0, 0, 0, 2, 1 },
{ 0, 0, 1, 2, 2 },{ -2, -1, 0, 2, 2 },{ -2, 0, 1, 0, 0 },{ -2, 0, 0, 2, 1 },{ 0, 0, -1, 2, 2 },
{ 2, 0, 0, 0, 0 },{ 0, 0, 1, 0, 1 },{ 2, 0, -1, 2, 2 },{ 0, 0, -1, 0, 1 },{ 0, 0, 1, 2, 1 },
{ -2, 0, 2, 0, 0 },{ 0, 0, -2, 2, 1 },{ 2, 0, 0, 2, 2 },{ 0, 0, 2, 2, 2 },{ 0, 0, 2, 0, 0 },
{ -2, 0, 1, 2, 2 },{ 0, 0, 0, 2, 0 },{ -2, 0, 0, 2, 0 },{ 0, 0, -1, 2, 1 },{ 0, 2, 0, 0, 0 },
{ 2, 0, -1, 0, 1 },{ -2, 2, 0, 2, 2 },{ 0, 1, 0, 0, 1 },{ -2, 0, 1, 0, 1 },{ 0, -1, 0, 0, 1 },
{ 0, 0, 2, -2, 0 },{ 2, 0, -1, 2, 1 },{ 2, 0, 1, 2, 2 },{ 0, 1, 0, 2, 2 },{ -2, 1, 1, 0, 0 },
{ 0, -1, 0, 2, 2 },{ 2, 0, 0, 2, 1 },{ 2, 0, 1, 0, 0 },{ -2, 0, 2, 2, 2 },{ -2, 0, 1, 2, 1 },
{ 2, 0, -2, 0, 1 },{ 2, 0, 0, 0, 1 },{ 0, -1, 1, 0, 0 },{ -2, -1, 0, 2, 1 },{ -2, 0, 0, 0, 1 },
{ 0, 0, 2, 2, 1 },{ -2, 0, 2, 0, 1 },{ -2, 1, 0, 2, 1 },{ 0, 0, 1, -2, 0 },{ -1, 0, 1, 0, 0 },
{ -2, 1, 0, 0, 0 },{ 1, 0, 0, 0, 0 },{ 0, 0, 1, 2, 0 },{ 0, 0, -2, 2, 2 },{ -1, -1, 1, 0, 0 },
{ 0, 1, 1, 0, 0 },{ 0, -1, 1, 2, 2 },{ 2, -1, -1, 2, 2 },{ 0, 0, 3, 2, 2 },{ 2, -1, 0, 2, 2 } };

std::vector<std::vector<double>> TERMS_PE = {
	{ -171996, -174.2, 92025, 8.9 },{ -13187, -1.6, 5736, -3.1 },
	{ -2274, -0.2, 977, -0.5 },{ 2062, 0.2, -895, 0.5 },{ 1426, -3.4, 54, -0.1 },{ 712, 0.1, -7, 0 },
	{ -517, 1.2, 224, -0.6 },{ -386, -0.4, 200, 0 },{ -301, 0, 129, -0.1 },{ 217, -0.5, -95, 0.3 },
	{ -158, 0, 0, 0 },{ 129, 0.1, -70, 0 },{ 123, 0, -53, 0 },{ 63, 0, 0, 0 },{ 63, 0.1, -33, 0 },
	{ -59, 0, 26, 0 },{ -58, -0.1, 32, 0 },{ -51, 0, 27, 0 },{ 48, 0, 0, 0 },{ 46, 0, -24, 0 },
	{ -38, 0, 16, 0 },{ -31, 0, 13, 0 },{ 29, 0, 0, 0 },{ 29, 0, -12, 0 },{ 26, 0, 0, 0 },
	{ -22, 0, 0, 0 },{ 21, 0, -10, 0 },{ 17, -0.1, 0, 0 },{ 16, 0, -8, 0 },{ -16, 0.1, 7, 0 },
	{ -15, 0, 9, 0 },{ -13, 0, 7, 0 },{ -12, 0, 6, 0 },{ 11, 0, 0, 0 },{ -10, 0, 5, 0 },{ -8, 0, 3, 0 },
	{ 7, 0, -3, 0 },{ -7, 0, 0, 0 },{ -7, 0, 3, 0 },{ -7, 0, 3, 0 },{ 6, 0, 0, 0 },{ 6, 0, -3, 0 },
	{ 6, 0, -3, 0 },{ -6, 0, 3, 0 },{ -6, 0, 3, 0 },{ 5, 0, 0, 0 },{ -5, 0, 3, 0 },{ -5, 0, 3, 0 },
	{ -5, 0, 3, 0 },{ 4, 0, 0, 0 },{ 4, 0, 0, 0 },{ 4, 0, 0, 0 },{ -4, 0, 0, 0 },{ -4, 0, 0, 0 },
	{ -4, 0, 0, 0 },{ 3, 0, 0, 0 },{ -3, 0, 0, 0 },{ -3, 0, 0, 0 },{ -3, 0, 0, 0 },{ -3, 0, 0, 0 },
	{ -3, 0, 0, 0 },{ -3, 0, 0, 0 },{ -3, 0, 0, 0 } };

std::vector<double> OBLIQUITY_COEFFS = { 84381.448, -4680.93, -1.55, 1999.25, 51.38, -249.67, -39.05,
7.12, 27.87, 5.79, 2.45 };


void calculateLBRTerms(double jme, std::vector<std::vector<std::vector<double>>>  termCoeffs, std::vector<double> &lbrTerms)
{
	for (int i = 0; i < termCoeffs.size(); i++) { // L0, L1, ... Ln
		double lbrSum = 0;
		for (int v = 0; v < termCoeffs[i].size(); v++) { // rows of each Li
			double a = termCoeffs[i][v][0]; // coefficients
			double b = termCoeffs[i][v][1];
			double c = termCoeffs[i][v][2];

			lbrSum += a * cos(b + c * jme);
		}
		lbrTerms[i] = lbrSum;
	}
}

double limitTo(double degrees, double max) {
	double dividedDegrees = degrees / max;
	double limited = max * (dividedDegrees - floor(dividedDegrees));
	return (limited < 0) ? limited + max : limited;
}


double calculatePolynomial(double x, std::vector<double> &coeffs) {
	double sum = 0;
	for (int i = 0; i < coeffs.size(); i++) {
		sum += coeffs[i] * pow(x, i);
	}
	return sum;
}

double limitDegreesTo360(double degrees) {
	return limitTo(degrees, 360.0);
}

AzimuthZenithAngle calculateTopocentricSolarPosition(double p, double t, double phi,
	double deltaPrime, double hPrime) {
	// calculate topocentric zenith angle
	double eZero = asin(sin(phi) * sin(deltaPrime) + cos(phi) * cos(deltaPrime) * cos(hPrime));
	double eZeroDegrees = toDegrees(eZero);

	// sanity check: extremely silly values for p and t are silently ignored, disabling refraction correction
	double deltaEdegrees = ( p < 0.0 || p > 3000.0 || t < -273 || t > 273 || (eZeroDegrees + 5.11) == 0.0f ) ?
		0.0 :
		((p / 1010) * (283 / (273 + t))
			* (1.02 / (60 * tan(toRadians(eZeroDegrees + 10.3 / (eZeroDegrees + 5.11))))));

	double topocentricZenithAngle = 90 - (eZeroDegrees + deltaEdegrees);

	// Calculate the topocentric azimuth angle
	double gamma = atan2(sin(hPrime), cos(hPrime) * sin(phi) - tan(deltaPrime) * cos(phi));
	double gammaDegrees = limitDegreesTo360(toDegrees(gamma));
	double topocentricAzimuthAngle = limitDegreesTo360(gammaDegrees + 180);

	AzimuthZenithAngle azimuthZenithAngle(topocentricAzimuthAngle, topocentricZenithAngle);

	return azimuthZenithAngle;
}

double calculateGeocentricSunDeclination(double betaRad, double epsilonRad,
	double lambdaRad) {
	return asin(sin(betaRad) * cos(epsilonRad) + cos(betaRad) * sin(epsilonRad) * sin(lambdaRad));
}

double calculateGeocentricSunRightAscension(double betaRad, double epsilonRad,
	double lambdaRad) {
	double alpha = atan2(sin(lambdaRad) * cos(epsilonRad) - tan(betaRad) * sin(epsilonRad), cos(lambdaRad));

	return limitDegreesTo360(toDegrees(alpha));
}

double calculateTrueObliquityOfEcliptic(double jme, double deltaEpsilon) {
	double epsilon0 = calculatePolynomial(jme / 10.0, OBLIQUITY_COEFFS);
	return epsilon0 / 3600 + deltaEpsilon;
}

double calculateApparentSiderealTimeAtGreenwich(JulianDate jd, double jce, double deltaPsi, double epsilonDegrees) {
	double nu0degrees = limitDegreesTo360(280.46061837 + 360.98564736629 * (jd - 2451545)
		+ 0.000387933 * pow(jce, 2) - pow(jce, 2) / 38710000);
	return nu0degrees + deltaPsi * cos(toRadians(epsilonDegrees));
}

double calculateDeltaPsiEpsilon(std::vector<double> &deltapsiorepsiloni) {
	double sum = 0;
	for (double element : deltapsiorepsiloni) {
		sum += element;
	}
	return sum / 36000000;
}

double calculateXjYtermSum(int i, std::vector<double> &x) {
	double sum = 0;
	for (int j = 0; j < x.size(); j++) {
		sum += x[j] * TERMS_Y[i][j];
	}
	return sum;
}

void calculateDeltaPsiI(double jce, std::vector<double> x, std::vector<double> &deltaPsiI) {
	deltaPsiI.resize(TERMS_PE.size());
	for (int i = 0; i < TERMS_PE.size(); i++) {
		double a = TERMS_PE[i][0];
		double b = TERMS_PE[i][1];
		deltaPsiI[i] = (a + b * jce) * sin(toRadians(calculateXjYtermSum(i, x)));
	}
}

void calculateDeltaEpsilonI(double jce, std::vector<double> &x, std::vector<double> &deltaEpsilonI) {
	deltaEpsilonI.resize(TERMS_PE.size());
	for (int i = 0; i < TERMS_PE.size(); i++) {
		double c = TERMS_PE[i][2];
		double d = TERMS_PE[i][3];
		deltaEpsilonI[i] = (c + d * jce) * cos(toRadians(calculateXjYtermSum(i, x)));
	}
}


void calculateNutationTerms(double jce, std::vector<double> &x) {
	x.resize(NUTATION_COEFFS.size());
	for (int i = 0; i < NUTATION_COEFFS.size(); i++) {
		x[i] = calculatePolynomial(jce, NUTATION_COEFFS[i]);
	}
}

double calculateLBRPolynomial(double jme, std::vector<double> &terms) {
	return calculatePolynomial(jme, terms) / 1e8;
}

AzimuthZenithAngle calculateSolarPosition(JulianDate jd, double latitude,
	double longitude, double elevation, double deltaT, double pressure,
	double temperature) {

	double jde = getJulianEphemerisDay(jd, deltaT);
	double jce = getJulianEphemerisCentury(jde);
	double jme = getJulianEphemerisMillennium(jce);


	// calculate Earth heliocentric longitude, L
	std::vector<double> lTerms = { 0, 0, 0, 0, 0, 0 };
	calculateLBRTerms(jme, TERMS_L, lTerms);
	double lDegrees = limitDegreesTo360(toDegrees(calculateLBRPolynomial(jme, lTerms)));

	// calculate Earth heliocentric latitude, B
	std::vector<double> bTerms = { 0, 0, 0, 0, 0, 0 };
	calculateLBRTerms(jme, TERMS_B, bTerms);
	double bDegrees = limitDegreesTo360(toDegrees(calculateLBRPolynomial(jme, bTerms)));

	// calculate Earth radius vector, R
	std::vector<double> rTerms = { 0, 0, 0, 0, 0, 0 };
	calculateLBRTerms(jme, TERMS_R, rTerms);
	double r = calculateLBRPolynomial(jme, rTerms);

	// calculate geocentric longitude, theta
	double thetaDegrees = limitDegreesTo360(lDegrees + 180);
	// calculate geocentric latitude, beta
	double betaDegrees = -bDegrees;
	double beta = toRadians(betaDegrees);

	//calculate nutation
	std::vector<double> xTerms;
	calculateNutationTerms(jce, xTerms);
	std::vector<double> deltaPsiI;
	calculateDeltaPsiI(jce, xTerms, deltaPsiI);
	std::vector<double> deltaEpsilonI;
	calculateDeltaEpsilonI(jce, xTerms, deltaEpsilonI);

	double deltaEpsilon = calculateDeltaPsiEpsilon(deltaEpsilonI);
	double deltaPsi = calculateDeltaPsiEpsilon(deltaPsiI);

	// calculate the true obliquity of the ecliptic
	double epsilonDegrees = calculateTrueObliquityOfEcliptic(jme, deltaEpsilon);
	double epsilon = toRadians(epsilonDegrees);

	// calculate aberration correction
	double deltaTau = -20.4898 / (3600 * r);

	// calculate the apparent sun longitude
	double lambdaDegrees = thetaDegrees + deltaPsi + deltaTau;
	double lambda = toRadians(lambdaDegrees);

	// Calculate the apparent sidereal time at Greenwich
	double nuDegrees = calculateApparentSiderealTimeAtGreenwich(jd, jce, deltaPsi, epsilonDegrees);

	// Calculate the geocentric sun right ascension
	double alphaDegrees = calculateGeocentricSunRightAscension(beta, epsilon, lambda);

	// Calculate geocentric sun declination
	double deltaDegrees = toDegrees(calculateGeocentricSunDeclination(beta, epsilon, lambda));

	// Calculate observer local hour angle
	double hDegrees = limitDegreesTo360(nuDegrees + longitude - alphaDegrees);
	double h = toRadians(hDegrees);

	// Calculate the topocentric sun right ascension and sun declination
	double xiDegrees = 8.794 / (3600 * r);
	double xi = toRadians(xiDegrees);
	double phi = toRadians(latitude);
	double delta = toRadians(deltaDegrees);
	double u = atan(0.99664719 * tan(phi));
	double x = cos(u) + elevation * cos(phi) / 6378140;
	double y = 0.99664719 * sin(u) + (elevation * sin(phi)) / 6378140;
	double deltaAlphaDegrees = toDegrees(atan2(-x * sin(xi) * sin(h), cos(delta) - x * sin(xi) * cos(h)));

	double deltaPrime = atan2((sin(delta) - y * sin(xi)) * cos(toRadians(deltaAlphaDegrees)), cos(delta) - x
		* sin(xi) * cos(h));

	// Calculate the topocentric local hour angle,
	double hPrimeDegrees = hDegrees - deltaAlphaDegrees;
	double hPrime = toRadians(hPrimeDegrees);

	return calculateTopocentricSolarPosition(pressure, temperature, phi, deltaPrime, hPrime);
}

double julian_day(int y, int m, int day, int hour, int minute, int second, double tz)
{
	m += 1;
	//m = m; //todo check if + 1 needed

	if (m < 3) {
		y = y - 1;
		m = m + 12;
	}

	double d = day + (hour - tz + (minute + second / 60.0) / 60.0) / 24.0;
	double jd = floor(365.25 * (y + 4716.0)) + floor(30.6001 * (m + 1)) + d - 1524.5;
	double a = floor(y / 100.0);
	double b = jd > 2299160.0 ? (2.0 - a + floor(a / 4.0)) : 0.0;

	return jd + b;
}
