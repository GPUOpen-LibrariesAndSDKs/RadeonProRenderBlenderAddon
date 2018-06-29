/*********************************************************************************************************************************
* Radeon ProRender for plugins
* Copyright (c) 2017 AMD
* All Rights Reserved
*
* IES light representation calculation
*********************************************************************************************************************************/

#pragma once

#include <vector>
#include "Math/float3.h"
#include "IESprocessor.h"

struct IESLightRepresentationParams
{
	IESProcessor::IESLightData data;
	size_t maxPointsPerPLine;
	float webScale;
};

enum class IESLightRepresentationErrorCode
{
	SUCCESS = 0,
	INVALID_DATA,
	NO_EDGES
};

IESLightRepresentationErrorCode CalculateIESLightRepresentation(std::vector<std::vector<RadeonProRender::float3>>& plines, const IESLightRepresentationParams& params);
