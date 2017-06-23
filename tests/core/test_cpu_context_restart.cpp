#include <thread>
#include <condition_variable>
#include <RadeonProRender.h>

#include <chrono>
#include <windows.h>
#include <rtcapi.h>
#include <assert.h>

void CheckFrStatus(rpr_int status)
{
	if ( status != RPR_SUCCESS )
	{
		//manage error here
		int a = 0;
	}
}

#define RPRTRACE_CHECK  CheckFrStatus(status);
#define RPRTRACE_DEV 1

#include <Dbghelp.h>
void make_minidump(EXCEPTION_POINTERS* e)
{
    auto hDbgHelp = LoadLibraryA("dbghelp");
    if(hDbgHelp == nullptr)
        return;
    auto pMiniDumpWriteDump = (decltype(&MiniDumpWriteDump))GetProcAddress(hDbgHelp, "MiniDumpWriteDump");
    if(pMiniDumpWriteDump == nullptr)
        return;

    char name[MAX_PATH];
    {
        auto nameEnd = name + GetModuleFileNameA(GetModuleHandleA(0), name, MAX_PATH);
        SYSTEMTIME t;
        GetSystemTime(&t);
        wsprintfA(nameEnd - strlen(".exe"),
            "_%4d%02d%02d_%02d%02d%02d.dmp",
            t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond);
    }

    auto hFile = CreateFileA(name, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if(hFile == INVALID_HANDLE_VALUE)
        return;

    MINIDUMP_EXCEPTION_INFORMATION exceptionInfo;
    exceptionInfo.ThreadId = GetCurrentThreadId();
    exceptionInfo.ExceptionPointers = e;
    exceptionInfo.ClientPointers = FALSE;

    auto dumped = pMiniDumpWriteDump(
        GetCurrentProcess(),
        GetCurrentProcessId(),
        hFile,
        MINIDUMP_TYPE(MiniDumpWithIndirectlyReferencedMemory | MiniDumpScanMemory),
        e ? &exceptionInfo : nullptr,
        nullptr,
        nullptr);

    CloseHandle(hFile);

    return;
}


int exception_handler(EXCEPTION_POINTERS* p)
{
    printf("Exception: 0x%08X !\n", p->ExceptionRecord->ExceptionCode);
    make_minidump(p);

    exit(1);
}

int runtime_check_handler(int errorType, const char *filename, int linenumber, const char *moduleName, const char *format, ...)
{
    printf("Error type %d at %s line %d in %s", errorType, filename, linenumber, moduleName);
    exit(1);
}


int main() {

    DWORD dwMode = SetErrorMode(SEM_NOGPFAULTERRORBOX);
    SetErrorMode(dwMode | SEM_NOGPFAULTERRORBOX);
    SetUnhandledExceptionFilter((LPTOP_LEVEL_EXCEPTION_FILTER)&exception_handler); 
    _RTC_SetErrorFunc(&runtime_check_handler);

    rpr_int status = RPR_SUCCESS;
    rpr_int tahoePluginID_0x0000000000000008 = NULL;
    rpr_context context_0x0000000007623780 = NULL;
    rpr_framebuffer framebuffer_0x000000000D5E2850 = NULL;
    rpr_framebuffer framebuffer_0x000000000D5E28B0 = NULL;
    rpr_scene scene_0x000000000D5E2910 = NULL;
    rpr_material_system materialsystem_0x000000000D5E2970 = NULL;
    rpr_camera camera_0x000000000D5E29D0 = NULL;
    rpr_shape shape_0x000000000D5E2A90 = NULL;
    rpr_light light_0x000000000D5E2AF0 = NULL;

    auto time_start = std::chrono::system_clock::now();
    for(int i=0;i!=50;++i){
        printf("running: %d ...", i);
        tahoePluginID_0x0000000000000008 = rprRegisterPlugin((rpr_char*)"Tahoe64.dll");  RPRTRACE_CHECK
        //Context creation
        #if defined(RPRTRACE_DEV)
        rpr_int tahoePluginIDlist_0[1] = { tahoePluginID_0x0000000000000008};
        status = rprCreateContext((rpr_int)RPR_API_VERSION,(rpr_int*)&tahoePluginIDlist_0,(size_t)1,RPR_CREATION_FLAGS_ENABLE_CPU | 0,(const rpr_context_properties*)NULL,0,&context_0x0000000007623780);
        #else
        rpr_int tahoePluginIDlist_1[1] = { tahoePluginID_0x0000000000000008};
        rpr_context context_0x0000000007623780 = NULL; status = rprCreateContext((rpr_int)0x0000000010000255,(rpr_int*)&tahoePluginIDlist_1,(size_t)1,RPR_CREATION_FLAGS_ENABLE_CPU | 0,(const rpr_context_properties*)NULL,(rpr_char*)"src\\rprblender\\.core_cache\\0x10000255",&context_0x0000000007623780);
        #endif
        RPRTRACE_CHECK
        status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"xflip",(rpr_uint)0);  RPRTRACE_CHECK
        status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"yflip",(rpr_uint)1);  RPRTRACE_CHECK
        rpr_framebuffer_format framebuffer_format0 = { 4, 3 };
        rpr_framebuffer_desc framebuffer_desc0 = { 128, 128 };
        //FrameBuffer creation
        status = rprContextCreateFrameBuffer(context_0x0000000007623780,(rpr_framebuffer_format)framebuffer_format0,(rpr_framebuffer_desc*)&framebuffer_desc0,&framebuffer_0x000000000D5E2850);  RPRTRACE_CHECK
        status = rprContextSetAOV(context_0x0000000007623780,RPR_AOV_COLOR,framebuffer_0x000000000D5E2850);  RPRTRACE_CHECK
        rpr_framebuffer_format framebuffer_format1 = { 4, 3 };
        rpr_framebuffer_desc framebuffer_desc1 = { 128, 128 };
        //FrameBuffer creation
        status = rprContextCreateFrameBuffer(context_0x0000000007623780,(rpr_framebuffer_format)framebuffer_format1,(rpr_framebuffer_desc*)&framebuffer_desc1,&framebuffer_0x000000000D5E28B0);  RPRTRACE_CHECK
        //Scene creation
        status = rprContextCreateScene(context_0x0000000007623780,&scene_0x000000000D5E2910);  RPRTRACE_CHECK
        status = rprContextSetScene(context_0x0000000007623780,scene_0x000000000D5E2910);  RPRTRACE_CHECK
        //MaterialSystem creation
        status = rprContextCreateMaterialSystem(context_0x0000000007623780,0,&materialsystem_0x000000000D5E2970);  RPRTRACE_CHECK
        status = rprSceneClear(scene_0x000000000D5E2910);  RPRTRACE_CHECK
        //Camera creation
        status = rprContextCreateCamera(context_0x0000000007623780,&camera_0x000000000D5E29D0);  RPRTRACE_CHECK
        status = rprCameraLookAt(camera_0x000000000D5E29D0,(rpr_float)7.481132f,(rpr_float)-6.507640f,(rpr_float)5.343665f,(rpr_float)6.826270f,(rpr_float)-5.896974f,(rpr_float)4.898420f,(rpr_float)-0.317370f,(rpr_float)0.312469f,(rpr_float)0.895343f);  RPRTRACE_CHECK
        //rprCameraGetInfo();  RPRTRACE_CHECK
        status = rprCameraSetFocalLength(camera_0x000000000D5E29D0,(rpr_float)35.000000f);  RPRTRACE_CHECK
        status = rprCameraSetSensorSize(camera_0x000000000D5E29D0,(rpr_float)32.000000f,(rpr_float)24.000000f);  RPRTRACE_CHECK
        status = rprCameraSetFStop(camera_0x000000000D5E29D0,(rpr_float)std::numeric_limits<float>::infinity());  RPRTRACE_CHECK
        status = rprCameraSetMode(camera_0x000000000D5E29D0,RPR_CAMERA_MODE_PERSPECTIVE);  RPRTRACE_CHECK
        status = rprSceneSetCamera(scene_0x000000000D5E2910,camera_0x000000000D5E29D0);  RPRTRACE_CHECK
        status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"texturecompression",(rpr_uint)0);  RPRTRACE_CHECK
        //Mesh creation
        //size in data file for this mesh: 1296
        //number of indices: 36
        //PointLight creation
        status = rprContextCreatePointLight(context_0x0000000007623780,&light_0x000000000D5E2AF0);  RPRTRACE_CHECK
        status = rprPointLightSetRadiantPower3f(light_0x000000000D5E2AF0,(rpr_float)100.000000f,(rpr_float)100.000000f,(rpr_float)100.000000f);  RPRTRACE_CHECK
        rpr_float float_P16_1[] = { -0.290865f,-0.771101f,0.566393f,4.076245f,0.955171f,-0.199883f,0.218391f,1.005454f,-0.055189f,0.604525f,0.794672f,5.903862f,0.000000f,0.000000f,0.000000f,1.000000f };
        status = rprLightSetTransform(light_0x000000000D5E2AF0,true,(rpr_float*)&float_P16_1);  RPRTRACE_CHECK
        status = rprSceneAttachLight(scene_0x000000000D5E2910,light_0x000000000D5E2AF0);  RPRTRACE_CHECK

        std::mutex render_completed_mutex;
        std::condition_variable render_completed_event;

        bool render_completed_flag = false;

        std::thread t([&](){
            std::lock_guard<std::mutex> render_completed_guard(render_completed_mutex);
            printf("running thread: %d ...", i);

            status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"rendermode",(rpr_uint)1);  RPRTRACE_CHECK
            status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"aasamples",(rpr_uint)1);  RPRTRACE_CHECK
            status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"aacellsize",(rpr_uint)1);  RPRTRACE_CHECK
            status = rprContextSetParameter1f(context_0x0000000007623780,(rpr_char*)"radianceclamp",(rpr_float)std::numeric_limits<float>::infinity());  RPRTRACE_CHECK
            status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"maxRecursion",(rpr_uint)10);  RPRTRACE_CHECK
            status = rprContextSetParameter1u(context_0x0000000007623780,(rpr_char*)"imagefilter.type",(rpr_uint)1);  RPRTRACE_CHECK
            status = rprContextSetParameter1f(context_0x0000000007623780,(rpr_char*)"imagefilter.box.radius",(rpr_float)0.000000f);  RPRTRACE_CHECK
            status = rprFrameBufferClear(framebuffer_0x000000000D5E2850);  RPRTRACE_CHECK

            for(int iteration=0;2!=iteration;++iteration){
                status = rprContextRender(context_0x0000000007623780);  RPRTRACE_CHECK
                //rprFrameBufferSaveToFile(framebuffer_0x000000000D5E2850, "img_00001.png"); // <-- uncomment if you want export image
                ////rprFrameBufferGetInfo();  RPRTRACE_CHECK
                ////rprFrameBufferGetInfo();  RPRTRACE_CHECK

                ////rprFrameBufferGetInfo(framebuffer_0x000000000D5E2850, info: 4867, size: 0, data: <cdata 'void *' NULL>, size_ret: <cdata 'size_t *' owning 8 bytes>
                //void* data = malloc(1228800);
                //rprFrameBufferGetInfo(framebuffer_0x000000000D5E2850, 
                //    4867, 1228800, data, NULL);
                //free(data);
                //Sleep(0);
            }

            //printf("running thread notify_all: %d ...", i);
            ////render_completed_event.notify_all();
            //printf("running thread notify_all - done: %d ...", i);
            render_completed_flag = true;
        });

        render_completed_mutex.lock();

        while(!render_completed_flag){
            render_completed_mutex.unlock();
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
            render_completed_mutex.lock();
        }
        render_completed_mutex.unlock();

        

        //std::unique_lock<std::mutex> render_completed_lock(render_completed_mutex);

        //for(int wait_i=0;wait_i<100000;++wait_i){
        //    //assert(t.joinable());
        //    if(std::cv_status::no_timeout==render_completed_event.wait_for(render_completed_lock, std::chrono::milliseconds(1)))
        //        break;
        //}
        t.join();

        status = rprObjectDelete(scene_0x000000000D5E2910);  RPRTRACE_CHECK
        scene_0x000000000D5E2910=NULL;
        status = rprObjectDelete(camera_0x000000000D5E29D0);  RPRTRACE_CHECK
        camera_0x000000000D5E29D0=NULL;
        status = rprObjectDelete(light_0x000000000D5E2AF0);  RPRTRACE_CHECK
        light_0x000000000D5E2AF0=NULL;
        status = rprObjectDelete(materialsystem_0x000000000D5E2970);  RPRTRACE_CHECK
        materialsystem_0x000000000D5E2970=NULL;
        status = rprContextSetAOV(context_0x0000000007623780,RPR_AOV_COLOR,(rpr_framebuffer)NULL);  RPRTRACE_CHECK
        status = rprObjectDelete(framebuffer_0x000000000D5E2850);  RPRTRACE_CHECK
        framebuffer_0x000000000D5E2850=NULL;
        status = rprObjectDelete(framebuffer_0x000000000D5E28B0);  RPRTRACE_CHECK
        framebuffer_0x000000000D5E28B0=NULL;
        status = rprObjectDelete(context_0x0000000007623780);  RPRTRACE_CHECK
        context_0x0000000007623780=NULL;
        printf("done\n");
    }

    auto time_elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now()-time_start).count();

    //test crash
    //volatile int * p;
    //p = 0;
    //*p = 0;

    printf("ALL DONE IN: %d ms\n", time_elapsed);

	return RPR_SUCCESS;
}
//End of trace.

