/*********************************************************************************************************************************
* Radeon ProRender for plugins
* Copyright (c) 2017 AMD
* All Rights Reserved
*
* IES light representation calculation
*********************************************************************************************************************************/

#include "Math/mathutils.h"
#include "Math/float3.h"
#include "Math/matrix.h"

#include "IESLightRepresentationCalc.h"
#include "IESprocessor.h"

#define DEG2RAD (MY_PI / 180.0f)

void Polar2XYZ(RadeonProRender::float3 &outPoint, double verticalAngle /*polar*/, double horizontalAngle /*azimuth*/, double dist)
{
	//VERTICAL_ANGLES aka polar angles aka theta
	//HORIZONTAL_ANGLES aka azimuthal angles aka phi

	// Theta is vertical angle
	double theta = verticalAngle * DEG2RAD;

	// Phi is horizontal angle
	double phi = horizontalAngle * DEG2RAD;

	outPoint.x = dist * sin(theta) * cos(phi);
	outPoint.y = dist * sin(theta) * sin(phi);
	outPoint.z = dist * cos(theta);
}

// clones all edges in edges array, transforms cloned edges by matrTransform and inserts them to edges array
void CloneAndTransform(std::vector<std::vector<RadeonProRender::float3>>& edges, const RadeonProRender::matrix &matrTransform)
{
	size_t length = edges.size();
	edges.reserve(length * 2);

	for (size_t idx = 0; idx < length; ++idx) // using length here because new elements are added to this array during execution (mirrored ones)
	{
		edges.emplace_back();
		std::vector<RadeonProRender::float3> &newEdge = edges.back();
		newEdge.reserve(edges[idx].size());
		for (const RadeonProRender::float3& point : edges[idx])
		{
			newEdge.emplace_back(matrTransform * point);
		}
	}
}

void MirrorEdges(std::vector<std::vector<RadeonProRender::float3>>& edges, const IESProcessor::IESLightData &data)
{
	if (data.IsAxiallySymmetric())
	{
		// mirror around xy plane
		RadeonProRender::matrix matrMirrorYZ(
			-1.0, 0.0, 0.0, 0.0,
			0.0, 1.0, 0.0, 0.0,
			0.0, 0.0, 1.0, 0.0,
			0.0, 0.0, 0.0, 1.0
		);
		CloneAndTransform(edges, matrMirrorYZ);

		// rotate around z axis by 90 degrees
		RadeonProRender::matrix matrRotateAroundZ(
			0.0, -1.0, 0.0, 0.0,
			1.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 1.0, 0.0,
			0.0, 0.0, 0.0, 1.0
		);
		CloneAndTransform(edges, matrRotateAroundZ);
	}

	else if (data.IsQuadrantSymmetric())
	{
		// mirror around xz plane
		RadeonProRender::matrix matrMirrorXZ(
			1.0, 0.0, 0.0, 0.0,
			0.0, -1.0, 0.0, 0.0,
			0.0, 0.0, 1.0, 0.0,
			0.0, 0.0, 0.0, 1.0
		);
		CloneAndTransform(edges, matrMirrorXZ);

		// mirror around yz plane
		RadeonProRender::matrix matrMirrorYZ(
			-1.0, 0.0, 0.0, 0.0,
			0.0, 1.0, 0.0, 0.0,
			0.0, 0.0, 1.0, 0.0,
			0.0, 0.0, 0.0, 1.0
		);
		CloneAndTransform(edges, matrMirrorYZ);
	}

	else if (data.IsPlaneSymmetric())
	{
		// mirror around xz plane
		RadeonProRender::matrix matrMirrorXZ(
			1.0, 0.0, 0.0, 0.0,
			0.0, -1.0, 0.0, 0.0,
			0.0, 0.0, 1.0, 0.0,
			0.0, 0.0, 0.0, 1.0
		);
		CloneAndTransform(edges, matrMirrorXZ);
	}
}

IESLightRepresentationErrorCode CalculateIESLightRepresentation(std::vector<std::vector<RadeonProRender::float3>>& plines, const IESLightRepresentationParams& params)
{
	// fluh input container
	plines.clear();
	
	// check input data
	bool invalidData = !params.data.IsValid();
	if (invalidData)
	{
		return IESLightRepresentationErrorCode::INVALID_DATA;
	}

	// calculate points of the mesh
	// - verticle angles count is number of columns in candela values table
	// - horizontal angles count is number of rows in candela values table
	std::vector<RadeonProRender::float3> candela_XYZ;
	candela_XYZ.reserve(params.data.m_candelaValues.size());
	auto it_candela = params.data.m_candelaValues.begin();

	for (double horizontalAngle : params.data.m_horizontalAngles)
	{
		for (double verticleAngle : params.data.m_verticalAngles)
		{
			// get world coordinates from polar representation in .ies
			candela_XYZ.emplace_back(0.0f, 0.0f, 0.0f);
			Polar2XYZ(candela_XYZ.back(), verticleAngle, horizontalAngle, *it_candela);
			candela_XYZ.back() *= params.webScale;

			++it_candela;
		}
	}

	// generate edges for each verticle angle (slices)
	const size_t MAX_POINTS_PER_POLYLINE = 32; // this is 3DMax limitation!
	size_t valuesPerRow = params.data.m_verticalAngles.size(); // verticle angles count is number of columns in candela values table

	auto it_points = candela_XYZ.begin();
	while (it_points != candela_XYZ.end())
	{
		auto endRow = it_points + valuesPerRow;
		std::vector<RadeonProRender::float3> pline;
		pline.reserve(MAX_POINTS_PER_POLYLINE);
		bool isClosed = true;

		for (; it_points != endRow; ++it_points)
		{
			pline.push_back(*it_points);

			if (pline.size() == MAX_POINTS_PER_POLYLINE)
			{
				plines.push_back(pline);
				pline.clear();
				isClosed = false;
				--it_points; // want to view continuous line
			}
		}

		if (!pline.empty())
		{
			plines.push_back(pline);
		}
	}

	// generate edges for mesh (edges crossing slices)
	// - under define because not sure if it looks good...
#ifdef IES_LIGHT_DONT_GEN_EXTRA_EDGES
	if (!data.IsAxiallySymmetric()) // axially simmetric light field is a special case (should be processed after mirroring)
	{
		size_t columnCount = data.VerticalAngles().size();
		size_t rowCount = data.HorizontalAngles().size();

		for (size_t idx_column = 0; idx_column < columnCount; idx_column++) // 0 - 180
		{

			std::vector<Point3> pline; pline.reserve(MAX_POINTS_PER_POLYLINE);
			for (size_t idx_row = 0; idx_row < rowCount; idx_row++) // 0 - 360
			{
				Point3 &tpoint = candela_XYZ[idx_row*columnCount + idx_column];
				pline.push_back(tpoint);

				if (pline.size() == MAX_POINTS_PER_POLYLINE)
				{
					edges.push_back(pline);
					pline.clear();
					--i; // want to view continuous line
				}
			}

			if (!pline.empty())
			{
				edges.push_back(pline);
			}
		}

	}
#endif

	// mirror edges if necessary
	// symmetric data is not written in IES file thus we have to mirror points to get full graphic representation of light source;
	// there are 3 different types of symmetry and asymmetric light source is also possible
	MirrorEdges(plines, params.data);

	return IESLightRepresentationErrorCode::SUCCESS;
}
