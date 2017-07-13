#include "RadeonProRender.h"

#include <assert.h>
#include <cstddef>
#include <string>

template<typename A, typename B>
void ASSERT_EQ(A a, B b){
    assert(a==b);
}

#define CHECK(x) status = x; assert(status == FR_SUCCESS);


bool test()
{
    // Indicates whether the last operation has suceeded or not
    fr_int status = FR_SUCCESS;


    const char* traceDir = ".\\notexistant";
    status = frContextSetParameterString(nullptr, "tracingfolder", traceDir);
    
    ASSERT_EQ(status, FR_SUCCESS);
    status = frContextSetParameter1u(nullptr, "tracing", 1);
    ASSERT_EQ(status, FR_SUCCESS);

    std::string tahoe_name;
    #ifdef WIN32 
        tahoe_name = "Tahoe64.dll";
    #else
        tahoe_name = "libTahoe64.so";
    #endif

    fr_int tahoePluginID = frRegisterPlugin(tahoe_name.c_str());
    assert(tahoePluginID!=-1);

    fr_int plugins[] = { tahoePluginID};
    size_t pluginCount = sizeof(plugins) / sizeof(plugins[0]);
     
    fr_context context;
    status = frCreateContext(FR_API_VERSION, plugins, pluginCount, FR_CREATION_FLAGS_ENABLE_GPU0, NULL, NULL, &context);
    ASSERT_EQ(status, FR_SUCCESS);

    size_t contextParameterCount = 0;
    CHECK(frContextGetInfo(context, FR_CONTEXT_PARAMETER_COUNT, sizeof(contextParameterCount), &contextParameterCount, nullptr));

    assert(0<contextParameterCount);

    for(int i=0;i!=contextParameterCount;++i){
        // get name
        size_t size;
        auto res = frContextGetParameterInfo(context, i, FR_PARAMETER_NAME_STRING, 0, nullptr, &size);
        assert(res == FR_SUCCESS);
        std::string name; name.resize(size);
        res = frContextGetParameterInfo(context, i, FR_PARAMETER_NAME_STRING, size, const_cast<char*>(name.data()), nullptr);
        assert(res == FR_SUCCESS);

        fr_int nameId;
        res = frContextGetParameterInfo(context, i, FR_PARAMETER_NAME, sizeof(nameId), &nameId, nullptr);
        assert(res == FR_SUCCESS);

        // get description
        res = frContextGetParameterInfo(context, i, FR_PARAMETER_DESCRIPTION, 0, nullptr, &size);
        assert(res == FR_SUCCESS);
        std::string description;
        description.resize(size);
        res = frContextGetParameterInfo(context, i, FR_PARAMETER_DESCRIPTION, size, const_cast<char*>(description.data()), nullptr);
        assert(res == FR_SUCCESS);

        // get type
        fr_int type;
        res = frContextGetParameterInfo(context, i, FR_PARAMETER_TYPE, sizeof(type), &type, nullptr);
        assert(res == FR_SUCCESS);

        std::string typeStr;
        std::string valueStr = "<unknown>";
        switch(type){
        case FR_PARAMETER_TYPE_FLOAT:{ typeStr = "float";
            fr_float value;
            res = frContextGetParameterInfo(context, i, FR_PARAMETER_VALUE, sizeof(value), &value, nullptr);
            assert(res == FR_SUCCESS);
            valueStr = std::to_string(value);
        }
            break;
        case FR_PARAMETER_TYPE_FLOAT2:{ typeStr = "float2";
            fr_float value[2];
            res = frContextGetParameterInfo(context, i, FR_PARAMETER_VALUE, sizeof(value), &value, nullptr);
            assert(res == FR_SUCCESS);
            valueStr = std::to_string(value[0])+", "+std::to_string(value[1]);
        }
            break;
        case FR_PARAMETER_TYPE_FLOAT3:typeStr = "float3";break;
        case FR_PARAMETER_TYPE_FLOAT4:typeStr = "float4";break;
        case FR_PARAMETER_TYPE_IMAGE:typeStr = "image";break;
        case FR_PARAMETER_TYPE_STRING:typeStr = "string";break;
        case FR_PARAMETER_TYPE_SHADER:typeStr = "shader";break;
        case FR_PARAMETER_TYPE_UINT:{ typeStr = "uint";
            fr_uint value;
            res = frContextGetParameterInfo(context, i, FR_PARAMETER_VALUE, sizeof(value), &value, nullptr);
            assert(res == FR_SUCCESS);
            valueStr = std::to_string(value);
        }
            break;
        default:
            typeStr = "<invalid>";break;
        };

        printf("%s(0x%x)=%s of type %d(%s): %s\n", name.c_str(), nameId, valueStr.c_str(), type, typeStr.c_str(), description.c_str());
    }

    //TEST for context failure
    {
        const char* traceDir = ".\\notexistant";
        status = frContextSetParameterString(nullptr, "tracingfolder", traceDir);
    
        ASSERT_EQ(status, FR_SUCCESS);
        status = frContextSetParameter1u(nullptr, "tracing", 1);
        ASSERT_EQ(status, FR_SUCCESS);

        fr_int tahoePluginID = frRegisterPlugin(tahoe_name.c_str());
        assert(tahoePluginID!=-1);

        fr_int plugins[] = { tahoePluginID};
        size_t pluginCount = sizeof(plugins) / sizeof(plugins[0]);
     
        fr_context context;
        status = frCreateContext(FR_API_VERSION, plugins, pluginCount, 
            FR_CREATION_FLAGS_ENABLE_GPU0|
            FR_CREATION_FLAGS_ENABLE_GPU1|
            FR_CREATION_FLAGS_ENABLE_GPU2|
            FR_CREATION_FLAGS_ENABLE_GPU3
            , NULL, NULL, &context);
        ASSERT_EQ(status, FR_ERROR_UNSUPPORTED);
    }

    fr_camera camera;
    status = frContextCreateCamera(context, &camera);
    ASSERT_EQ(status, FR_SUCCESS);

    return true;
}

#ifdef _WIN32

#include <windows.h>
#include <excpt.h>

const char* getExcetionName(int code){

    switch(code){
    case STILL_ACTIVE: return "STILL_ACTIVE";break;
    case EXCEPTION_ACCESS_VIOLATION: return "EXCEPTION_ACCESS_VIOLATION";break;
    case EXCEPTION_DATATYPE_MISALIGNMENT: return "EXCEPTION_DATATYPE_MISALIGNMENT";break;
    case EXCEPTION_BREAKPOINT: return "EXCEPTION_BREAKPOINT";break;
    case EXCEPTION_SINGLE_STEP: return "EXCEPTION_SINGLE_STEP";break;
    case EXCEPTION_ARRAY_BOUNDS_EXCEEDED: return "EXCEPTION_ARRAY_BOUNDS_EXCEEDED";break;
    case EXCEPTION_FLT_DENORMAL_OPERAND: return "EXCEPTION_FLT_DENORMAL_OPERAND";break;
    case EXCEPTION_FLT_DIVIDE_BY_ZERO: return "EXCEPTION_FLT_DIVIDE_BY_ZERO";break;
    case EXCEPTION_FLT_INEXACT_RESULT: return "EXCEPTION_FLT_INEXACT_RESULT";break;
    case EXCEPTION_FLT_INVALID_OPERATION: return "EXCEPTION_FLT_INVALID_OPERATION";break;
    case EXCEPTION_FLT_OVERFLOW: return "EXCEPTION_FLT_OVERFLOW";break;
    case EXCEPTION_FLT_STACK_CHECK: return "EXCEPTION_FLT_STACK_CHECK";break;
    case EXCEPTION_FLT_UNDERFLOW: return "EXCEPTION_FLT_UNDERFLOW";break;
    case EXCEPTION_INT_DIVIDE_BY_ZERO: return "EXCEPTION_INT_DIVIDE_BY_ZERO";break;
    case EXCEPTION_INT_OVERFLOW: return "EXCEPTION_INT_OVERFLOW";break;
    case EXCEPTION_PRIV_INSTRUCTION: return "EXCEPTION_PRIV_INSTRUCTION";break;
    case EXCEPTION_IN_PAGE_ERROR: return "EXCEPTION_IN_PAGE_ERROR";break;
    case EXCEPTION_ILLEGAL_INSTRUCTION: return "EXCEPTION_ILLEGAL_INSTRUCTION";break;
    case EXCEPTION_NONCONTINUABLE_EXCEPTION: return "EXCEPTION_NONCONTINUABLE_EXCEPTION";break;
    case EXCEPTION_STACK_OVERFLOW: return "EXCEPTION_STACK_OVERFLOW";break;
    case EXCEPTION_INVALID_DISPOSITION: return "EXCEPTION_INVALID_DISPOSITION";break;
    case EXCEPTION_GUARD_PAGE: return "EXCEPTION_GUARD_PAGE";break;
    case EXCEPTION_INVALID_HANDLE: return "EXCEPTION_INVALID_HANDLE";break;
    //case EXCEPTION_POSSIBLE_DEADLOCK: return "EXCEPTION_POSSIBLE_DEADLOCK";break;
    case CONTROL_C_EXIT: return "CONTROL_C_EXIT";break;
    }
    return "undefined";
}

#endif

#include <stdio.h>
#include <exception>

bool _test()
{
    try{
        return test();
    } catch (std::exception& e){
        printf("\nException: %s\n", e.what());
    }
    return false;
}

int main()
{
    bool success = false;
#ifdef _WIN32
    __try { 
        success = _test();
    } __except(1) { 
        //EXCEPTION_INT_DIVIDE_BY_ZERO

        auto code = GetExceptionCode();
        printf("\nException: %s(0x%08x)\n", getExcetionName(code), code);
    }
#else 
    try { 
        success = _test();
    } catch(...) { 
        //EXCEPTION_INT_DIVIDE_BY_ZERO
        printf("\nException\n");
    }
#endif

    if(success){
        printf("OK\n");
    } else {
        printf("\nFAILURE!\n");
    }
}
