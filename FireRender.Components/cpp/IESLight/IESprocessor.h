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
********************************************************************
*
* IES file parser
********************************************************************/

#pragma once

// process data for IES light sources
class IESProcessor
{
public:
	class IESLightData;
	struct IESUpdateRequest;
	enum class ParseState;

	enum class ErrorCode
	{
		SUCCESS = 0,
		NO_FILE,                    ///< wrong input
		NOT_IES_FILE,               ///< wrong file type
		FAILED_TO_READ_FILE,        ///< failed to open file
		INVALID_DATA_IN_IES_FILE,   ///< parse OK, but data in IES file is not valid (either data in the file was not correct, or something went wrong during the parse)
		PARSE_FAILED,               ///< error during parse or file too big (file is longer than parser assumed it should)
		UNEXPECTED_END_OF_FILE,     ///< have reached end of file before parse was completed
		NOT_SUPPORTED,				///< file have features that are not supported by RPR Core
	};

	/**
	* parse IES file filename and fill lightData with data from this file
	* @param filename name of .ies file to be parsed
	* @param lightData - output lightData
	* @return code of error, zero if parse successful 
	*/
	ErrorCode Parse (IESLightData& lightData, const wchar_t* filename) const;

	/**
	* change light data according to request, e.g. intensity is changed and so on
	* @param req struct with values to be updated in lightData
	* @param lightData input and output struct with IES data that should be changed according to request req
	* @return code of error, zero if parse successful
	*/
	ErrorCode Update (IESLightData& lightData, const IESUpdateRequest& req) const;

	/**
	* returns string representation of IES light source declaration
	* should be used for call to RPR
	* @param lightData data of IES file
	* @return string representing IES data
	*/
	std::string ToString (const IESLightData& lightData) const;

protected:
	static const std::string IES_FileExtraTag;
	static const std::string IES_FileGeneralTag;
	static const std::string IES_FileTag;

	/**
	* Reads file and fills array tokens with numbers (as strings) and text array with data other than numbers
	* read from the file.
	* Basically makes data more convenient to parse
	*/
	ErrorCode GetTokensFromFile (std::vector<std::string>& tokens, std::string& text, std::ifstream& inputFile) const;

	/** 
	* split line with several values separated by space(s) into array of strings each containing single value
	*/
	void SplitLine (std::vector<std::string>& tokens, const std::string& lineToParse) const;

	/**
	fills lightData with data read from tokens
	* @return code of error in case of parse failure, zero if successful
	*/
	ErrorCode ParseTokens (IESLightData& lightData, std::vector<std::string>& tokens) const;

	/**
	* auxilary function that hides interaction with enum
	* @return first value of ParseOrder enum
	*/
	IESProcessor::ParseState FirstParseState (void) const;

	/**
	* fills corresponding to state lightData parameter with data read from value
	* value is supposed to string with one value, double or integer
	* @return false in case of error
	*/
	bool ReadValue (IESLightData& lightData, IESProcessor::ParseState& state, const std::string& value) const;
};

// holds data for IES light source
/**
* NOTE that we render light according to IES specification
* There are differences between IES specification and Autodesk IES lights description 
* That might cause differences in rendered images
*
* Differences:
* number of lamps should always be 1 according to Autodesk specification;
* photometric type should always be 1 according to Autodesk specification;
* ballast should always be 1 according to Autodesk specification;
* version should always be 1 according to Autodesk specification;
* wattage should always be 0 according to Autodesk specification.
*/
class IESProcessor::IESLightData
{
public:
	IESLightData();

	/**
	* Number of lamps.
	*/
	int m_countLamps = 0;

	/**
	* The initial rated lumens for the lamp used in the test or -1 if absolute photometry is used
	* and the intensity values do not depend on different lamp ratings. 
	*/
	double m_lumens = 0.0f;

	/**
	* A multiplying factor for all the candela values in the file. 
	* This makes it possible to easily scale all the candela values in the file 
	* when the measuring device operates in unusual units—for example, 
	* when you obtain the photometric values from a catalog using a ruler on a goniometric diagram.
	* Normally the multiplying factor is 1.
	*/
	double m_multiplier = 0.0f;

	/**
	* The number of vertical (polar) angles in the photometric web. 
	*/
	int m_countVerticalAngles = 0;

	/**
	* The number of horizontal (azimuth) angles in the photometric web. 
	*/
	int m_countHorizontalAngles = 0;

	/**
	* Can be 1, 2 or 3 according to IES specification.
	* RPR Core however supports only m_photometricType == 1
	*/
	int m_photometricType = 0;

	/**
	* The type of unit used to measure the dimensions of the luminous opening.
	* Use 1 for feet or 2 for meters.
	*/
	int m_unit = 0;

	/**
	* The width, length, and height of the luminous opening.
	*/
	double m_width = 0.0f;
	double m_length = 0.0f;
	double m_height = 0.0f;

	/**
	* Multiplier representing difference between lab measurements and real world performance
	*/
	int m_ballast = 0;

	/**
	* Standard version
	*/
	int m_version = 0;

	/**
	* Power of light source
	*/
	double m_wattage = -1;

	/**
	* The set of vertical angles (aka polar angles), listed in increasing order. 
	* If the distribution lies completely in the bottom hemisphere, the first and last angles must be 0° and 90°, respectively.
	* If the distribution lies completely in the top hemisphere, the first and last angles must be 90° and 180°, respectively.
	* Otherwise, they must be 0° and 180°, respectively.
	*/
	std::vector<double> m_verticalAngles;

	/**
	* The set of horizontal angles (aka azimuth angles), listed in increasing order.
	* The first angle must be 0°.
	* The last angle determines the degree of lateral symmetry displayed by the intensity distribution.
	* If it is 0°, the distribution is axially symmetric.
	* If it is 90°, the distribution is symmetric in each quadrant.
	* If it is 180°, the distribution is symmetric about a vertical plane.
	* If it is greater than 180° and less than or equal to 360°, the distribution exhibits no lateral symmetries.
	* All other values are invalid. 
	*/
	std::vector<double> m_horizontalAngles;

	/**
	* The set of candela values.
	* First all the candela values corresponding to the first horizontal angle
	* are listed, starting with the value corresponding to the smallest
	* vertical angle and moving up the associated vertical plane.
	* Then the candela values corresponding to the vertical plane
	* through the second horizontal angle are listed,
	* and so on until the last horizontal angle.
	* Each vertical slice of values must start on a new line.
	* Long lines may be broken between values as needed
	* by following the instructions given earlier. 
	*/
	std::vector<double> m_candelaValues;

	/**
	* this is text data that is written to the IES file before actual data
	*/
	std::string m_extraData;

	/**
	* checks if struct holds correct data values
	* @return false if data is corrupted
	*/
	bool IsValid (void) const;

	/**
	* deletes all data in this container
	*/
	void Clear (void);

	/**
	* the distribution is axially symmetric.
	*/
	bool IsAxiallySymmetric (void) const;

	/**
	* the distribution is symmetric in each quadrant.
	*/
	bool IsQuadrantSymmetric (void) const;

	/**
	* the distribution is symmetric about a vertical plane.
	*/
	bool IsPlaneSymmetric (void) const;

	/**
	* the distribution is asymmetric (and complete).
	*/
	bool IsAsymmetric(void) const;

protected:
};

struct IESProcessor::IESUpdateRequest
{
	float m_scale = 1.0f;
};

