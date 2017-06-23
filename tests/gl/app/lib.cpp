#include <windows.h>
#include <gl/gl.h>

#include <stdio.h>
#include <assert.h>

extern "C"
__declspec(dllexport)
void libfun()
{
    printf("hello from lib, GL_VERSION: >>>%s<<<\n",(char*)glGetString(GL_VERSION));
}

extern "C"
__declspec(dllexport)
void libdraw()
{
    glClearColor(1, 1, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
}


BOOL WINAPI DllMain(HINSTANCE hinstDLL,
    DWORD fdwReason,
    LPVOID lpReserved)
{
    switch(fdwReason) 
    { 
        case DLL_PROCESS_ATTACH:
            printf("DLL_PROCESS_ATTACH\n");
            break;

        case DLL_PROCESS_DETACH:
            printf("DLL_PROCESS_DETACH\n");
            break;
    }
    return TRUE;
}