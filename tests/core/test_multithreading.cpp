#include "RadeonProRender.h"
#include "Math/mathutils.h"

#include <assert.h>

#include <string>
#include <iostream>
#include <thread>

using namespace RadeonProRender;

template<typename A, typename B>
void ASSERT_EQ(A a, B b){
    assert(a==b);
}

#define CHECK(x) status = x; assert(status == FR_SUCCESS);

// Number of iterations for rendering
int const NUM_ITERATIONS = 100;

// Structure to describe vertex layout
struct vertex
{
    fr_float pos[3];
    fr_float norm[3];
    fr_float tex[2];
};

// Cube geometry
vertex cube_data[] = 
{
    { -1.0f, 1.0f, -1.0f, 0.f, 1.f, 0.f, 0.f, 0.f },
    {  1.0f, 1.0f, -1.0f, 0.f, 1.f, 0.f, 0.f, 0.f },
    {  1.0f, 1.0f, 1.0f , 0.f, 1.f, 0.f, 0.f, 0.f },
    {  -1.0f, 1.0f, 1.0f , 0.f, 1.f, 0.f, 0.f, 0.f},

    {  -1.0f, -1.0f, -1.0f , 0.f, -1.f, 0.f, 0.f, 0.f },
    {  1.0f, -1.0f, -1.0f , 0.f, -1.f, 0.f, 0.f, 0.f },
    {  1.0f, -1.0f, 1.0f , 0.f, -1.f, 0.f, 0.f, 0.f },
    {  -1.0f, -1.0f, 1.0f , 0.f, -1.f, 0.f, 0.f, 0.f },

    {  -1.0f, -1.0f, 1.0f , -1.f, 0.f, 0.f, 0.f, 0.f },
    {  -1.0f, -1.0f, -1.0f , -1.f, 0.f, 0.f, 0.f, 0.f },
    {  -1.0f, 1.0f, -1.0f , -1.f, 0.f, 0.f, 0.f, 0.f },
    {  -1.0f, 1.0f, 1.0f , -1.f, 0.f, 0.f, 0.f, 0.f },

    {  1.0f, -1.0f, 1.0f ,  1.f, 0.f, 0.f, 0.f, 0.f },
    {  1.0f, -1.0f, -1.0f ,  1.f, 0.f, 0.f, 0.f, 0.f },
    {  1.0f, 1.0f, -1.0f ,  1.f, 0.f, 0.f, 0.f, 0.f },
    {  1.0f, 1.0f, 1.0f ,  1.f, 0.f, 0.f, 0.f, 0.f },

    {  -1.0f, -1.0f, -1.0f ,  0.f, 0.f, -1.f , 0.f, 0.f },
    {  1.0f, -1.0f, -1.0f ,  0.f, 0.f, -1.f , 0.f, 0.f },
    {  1.0f, 1.0f, -1.0f ,  0.f, 0.f, -1.f, 0.f, 0.f },
    {  -1.0f, 1.0f, -1.0f ,  0.f, 0.f, -1.f, 0.f, 0.f },

    {  -1.0f, -1.0f, 1.0f , 0.f, 0.f, 1.f, 0.f, 0.f },
    {  1.0f, -1.0f, 1.0f , 0.f, 0.f,  1.f, 0.f, 0.f },
    {  1.0f, 1.0f, 1.0f , 0.f, 0.f, 1.f, 0.f, 0.f },
    {  -1.0f, 1.0f, 1.0f , 0.f, 0.f, 1.f, 0.f, 0.f },
};

// Plane geometry
vertex plane_data[] = 
{
    {-15.f, 0.f, -15.f, 0.f, 1.f, 0.f, 0.f, 0.f},
    {-15.f, 0.f,  15.f, 0.f, 1.f, 0.f, 0.f, 1.f},
    { 15.f, 0.f,  15.f, 0.f, 1.f, 0.f, 1.f, 1.f},
    { 15.f, 0.f, -15.f, 0.f, 1.f, 0.f, 1.f, 0.f},
};

// Cube indices
fr_int indices[] = 
{
    3,1,0,
    2,1,3,

    6,4,5,
    7,4,6,

    11,9,8,
    10,9,11,

    14,12,13,
    15,12,14,

    19,17,16,
    18,17,19,

    22,20,21,
    23,20,22
};

// Number of vertices per face
fr_int num_face_vertices[] = 
{
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3
};


struct SimpleRender{

	fr_context context;
	fr_framebuffer frame_buffer;

	SimpleRender(){
		fr_int status = FR_SUCCESS;

		status = frContextSetParameter1u(nullptr, "tracing", 0);
		ASSERT_EQ(status, FR_SUCCESS);

		fr_int tahoePluginID = frRegisterPlugin("Tahoe64.dll");
		assert(tahoePluginID!=-1);

		fr_int plugins[] = { tahoePluginID};
		size_t pluginCount = sizeof(plugins) / sizeof(plugins[0]);
     
		status = frCreateContext(FR_API_VERSION, plugins, pluginCount, FR_CREATION_FLAGS_ENABLE_GPU0, NULL, NULL, &context);
		ASSERT_EQ(status, FR_SUCCESS);


		fr_material_system matsys;
		CHECK( frContextCreateMaterialSystem(context, 0, &matsys) );

		std::cout << "Context successfully created.\n";

		// Create a scene
		fr_scene scene;
		CHECK( frContextCreateScene(context, &scene) );

		// Create cube mesh
		fr_shape cube;
		CHECK( frContextCreateMesh(context,
			(fr_float const*)&cube_data[0], 24, sizeof(vertex),
			(fr_float const*)((char*)&cube_data[0] + sizeof(fr_float)*3), 24, sizeof(vertex),
			(fr_float const*)((char*)&cube_data[0] + sizeof(fr_float)*6), 24, sizeof(vertex),
			(fr_int const*)indices, sizeof(fr_int),
			(fr_int const*)indices, sizeof(fr_int),
			(fr_int const*)indices, sizeof(fr_int),
			num_face_vertices, 12, &cube) );

		// Create plane mesh
		fr_shape plane;
		CHECK( frContextCreateMesh(context,
			(fr_float const*)&plane_data[0], 4, sizeof(vertex),
			(fr_float const*)((char*)&plane_data[0] + sizeof(fr_float)*3), 4, sizeof(vertex),
			(fr_float const*)((char*)&plane_data[0] + sizeof(fr_float)*6), 4, sizeof(vertex),
			(fr_int const*)indices, sizeof(fr_int),
			(fr_int const*)indices, sizeof(fr_int),
			(fr_int const*)indices, sizeof(fr_int),
			num_face_vertices, 2, &plane) );

		// Add cube into the scene
		CHECK( frSceneAttachShape(scene, cube) );

		// Create a transform: -2 unit along X axis and 1 unit up Y axis
		matrix m = translation(float3(-2, 1, 0));

		// Set the transform 
		CHECK( frShapeSetTransform(cube, FR_TRUE, &m.m00) );

		// Add plane into the scene
		CHECK( frSceneAttachShape(scene, plane) );

		// Create camera
		fr_camera camera;
		CHECK( frContextCreateCamera(context, &camera) );

		// Position camera in world space: 
		// Camera position is (5,5,20)
		// Camera aimed at (0,0,0)
		// Camera up vector is (0,1,0)
		CHECK( frCameraLookAt(camera, 5, 5, 20, 0, 0, 0, 0, 1, 0) );

		CHECK( frCameraSetFocalLength(camera, 75.f) );

		// Set camera for the scene
		CHECK( frSceneSetCamera(scene, camera) );

		// Set scene to render for the context
		CHECK( frContextSetScene(context, scene) );
 
		// Create simple diffuse shader
		fr_material_node diffuse;
		CHECK( frMaterialSystemCreateNode(matsys, FR_MATERIAL_NODE_DIFFUSE, &diffuse) );

		// Set diffuse color parameter to gray
		CHECK( frMaterialNodeSetInputF(diffuse, "color", 0.5f, 0.5f, 0.5f, 1.f) );

		// Set shader for cube & plane meshes
		//CHECK( frShapeSetMaterial(cube, diffuse) );

		//CHECK( frShapeSetMaterial(plane, diffuse) );

		// Create point light
		fr_light light;
		CHECK( frContextCreatePointLight(context, &light) );

		// Create a transform: move 5 units in X axis, 8 units up Y axis, -2 units in Z axis
		matrix lightm = translation(float3(5,8,-2));

		// Set transform for the light
		CHECK( frLightSetTransform(light, FR_TRUE, &lightm.m00) );

		// Set light radiant power in Watts
		CHECK( frPointLightSetRadiantPower3f(light, 255, 241, 224) );

		// Attach the light to the scene
		CHECK( frSceneAttachLight(scene, light) );

		// Create framebuffer to store rendering result
		fr_framebuffer_desc desc;
		desc.fb_width = 800;
		desc.fb_height = 600;

		// 4 component 32-bit float value each
		fr_framebuffer_format fmt = {4, FR_COMPONENT_TYPE_FLOAT32};
		CHECK( frContextCreateFrameBuffer(context, fmt, &desc, &frame_buffer) );

		// Clear framebuffer to black color
		CHECK( frFrameBufferClear(frame_buffer) );

		// Set framebuffer for the context
		CHECK( frContextSetAOV(context, FR_AOV_COLOR, frame_buffer) );

		// Set antialising options
		CHECK( frContextSetParameter1u(context, "aasamples", 2) );
	}

	void render() {
		fr_int status = FR_SUCCESS;

		// Progressively render an image
		for (int i = 0; i < NUM_ITERATIONS; ++i)
		{
			CHECK( frContextRender(context) );
		}

		std::cout << "Rendering finished.\n";

		// Save the result to file
		CHECK( frFrameBufferSaveToFile(frame_buffer, "simple_render.png") );

	}

};

bool test()
{
    // Indicates whether the last operation has suceeded or not
    fr_int status = FR_SUCCESS;

	fr_int tahoePluginID = frRegisterPlugin("Tahoe64.dll");
	assert(tahoePluginID!=-1);

	fr_int plugins[] = { tahoePluginID};
	size_t pluginCount = sizeof(plugins) / sizeof(plugins[0]);

	SimpleRender renderer;

	bool done = false;
	std::thread render_thread([&](){renderer.render(); done = true;});

	for(int i=0;!done;++i){
		printf("context # %03d\n", i);
		//fr_int tahoePluginID = frRegisterPlugin("Tahoe64.dll");
		//assert(tahoePluginID!=-1);

		//fr_int plugins[] = { tahoePluginID};
		//size_t pluginCount = sizeof(plugins) / sizeof(plugins[0]);

		fr_context context;
		status = frCreateContext(FR_API_VERSION, plugins, pluginCount, FR_CREATION_FLAGS_ENABLE_GPU0, NULL, NULL, &context);
		ASSERT_EQ(status, FR_SUCCESS);
	}
	render_thread.join();

    return true;
}

int main()
{
	test();
	printf("OK\n");
}
