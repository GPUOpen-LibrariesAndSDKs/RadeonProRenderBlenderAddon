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

#include "stdafx.h"
#include "../../RadeonProRenderLibs/rprLibs/pluginUtils.hpp"


////////////////////////////////////////////////////////////////////////////////////
// > Exports
////////////////////////////////////////////////////////////////////////////////////

std::string vdb_last_error;
std::string vdb_grid_list;

struct GridData
{
	int x, y, z;
	uint32_t *indices;
	int indicesSize;
	float *values;
	int valuesSize;
};


extern "C"
{

EXPORT const char *vdb_read_grids_list(const char* vdbFile)
{
	GridParams params;
	bool res;
	std::tie(res, vdb_last_error) = ReadVolumeDataFromFile(vdbFile, params);
	if (!res)
		return NULL;

	vdb_grid_list = "";
	for (auto it : params)
	{
		if (!vdb_grid_list.empty())
			vdb_grid_list += "\n";
		vdb_grid_list += it.first;
	}

	return vdb_grid_list.c_str();
}

EXPORT bool vdb_read_grid_data(const char *vdbFile, const char *gridName, GridData *data)
{
	bool res = false;

	openvdb::initialize();
	openvdb::io::File file(vdbFile);
	try
	{
		file.open();
	}
	catch (openvdb::IoError ex)
	{
		vdb_last_error = ex.what();
		return res;
	}

	VDBGrid<float> vdbGrid;
	std::tie(res, vdb_last_error) = ReadFileGridToVDBGrid(vdbGrid, file, gridName);
	file.close();

	if (!res)
		return res;

	data->x = vdbGrid.gridSizeX;
	data->y = vdbGrid.gridSizeY;
	data->z = vdbGrid.gridSizeZ;

	data->indicesSize = vdbGrid.gridOnIndices.size();
	data->indices = new uint32_t[data->indicesSize];
	memcpy(data->indices, vdbGrid.gridOnIndices.data(), data->indicesSize * sizeof(uint32_t));

	data->valuesSize = vdbGrid.gridOnValueIndices.size();
	data->values = new float[data->valuesSize];
	memcpy(data->values, vdbGrid.gridOnValueIndices.data(), data->valuesSize * sizeof(float));

	return res;
}

EXPORT void vdb_free_grid_data(GridData *data)
{
	delete[] data->indices;
	delete[] data->values;
}

EXPORT const char* vdb_get_last_error()
{
	return vdb_last_error.c_str();
}

}
