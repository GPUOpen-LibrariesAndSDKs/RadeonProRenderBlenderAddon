cdef extern from "../../ThirdParty/RadeonProRender SDK/Win/inc/RadeonProRender.h":
    ctypedef int fr_int;
    ctypedef         unsigned int         fr_uint;
    ctypedef         fr_uint              fr_bitfield;
    ctypedef         fr_bitfield          fr_creation_flags;
    ctypedef         void*                fr_context_properties;
    ctypedef         char                 fr_char;
    ctypedef         void*                fr_context;
    int FR_API_VERSION
    int FR_CREATION_FLAGS_ENABLE_GPU0
    fr_int frRegisterPlugin(const fr_char* path)
    fr_int frCreateContext(fr_int api_version, fr_int* pluginIDs, size_t pluginCount, fr_creation_flags creation_flags, const fr_context_properties * props, const fr_char* cache_path,  fr_context* out_context)


def createContext():
    cdef fr_int tahoePluginID = frRegisterPlugin("Tahoe64.dll");
    print("tahoePluginID", tahoePluginID)
    #assert tahoePluginID!=-1

    cdef fr_int plugins[1];
    plugins[0] = tahoePluginID;

    cdef fr_context context;
    return frCreateContext(FR_API_VERSION, plugins, 1, FR_CREATION_FLAGS_ENABLE_GPU0, NULL, NULL, &context) 
