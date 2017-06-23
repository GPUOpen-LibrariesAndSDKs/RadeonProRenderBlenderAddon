#include <windows.h>
#include <gl/gl.h>

#include <stdio.h>
#include <assert.h>

LRESULT CALLBACK WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam);

int main()
{
    HINSTANCE hInstance = GetModuleHandle(NULL);
    MSG msg          = {0};
    WNDCLASS wc      = {0}; 
    wc.lpfnWndProc   = WndProc;
    wc.hInstance     = hInstance;
    wc.hbrBackground = (HBRUSH)(COLOR_BACKGROUND);
    wc.lpszClassName = "oglversionchecksample";
    wc.style = CS_OWNDC;
    if( !RegisterClass(&wc) )
        return 1;
    CreateWindow(wc.lpszClassName, "openglversioncheck",WS_OVERLAPPEDWINDOW|WS_VISIBLE,0,0,640,480,0,0,hInstance,0);

    while( GetMessage( &msg, NULL, 0, 0 ) > 0 )
        DispatchMessage( &msg );

    return 0;
}

HGLRC ourOpenGLRenderingContext;
HDC ourWindowHandleToDeviceContext;

HMODULE thelib;

LRESULT CALLBACK WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam)
{
    switch(message)
    {
    case WM_CLOSE:
        printf("WM_CLOSE");
        wglDeleteContext(ourOpenGLRenderingContext);
        FreeLibrary(thelib);
        PostQuitMessage(0);
        break;
    case WM_CREATE:
        {
        PIXELFORMATDESCRIPTOR pfd =
        {
            sizeof(PIXELFORMATDESCRIPTOR),
            1,
            PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER,    //Flags
            PFD_TYPE_RGBA,            //The kind of framebuffer. RGBA or palette.
            32,                        //Colordepth of the framebuffer.
            0, 0, 0, 0, 0, 0,
            0,
            0,
            0,
            0, 0, 0, 0,
            24,                        //Number of bits for the depthbuffer
            8,                        //Number of bits for the stencilbuffer
            0,                        //Number of Aux buffers in the framebuffer.
            PFD_MAIN_PLANE,
            0,
            0, 0, 0
        };

        ourWindowHandleToDeviceContext = GetDC(hWnd);

        int  letWindowsChooseThisPixelFormat;
        letWindowsChooseThisPixelFormat = ChoosePixelFormat(ourWindowHandleToDeviceContext, &pfd); 
        SetPixelFormat(ourWindowHandleToDeviceContext,letWindowsChooseThisPixelFormat, &pfd);

        ourOpenGLRenderingContext = wglCreateContext(ourWindowHandleToDeviceContext);
        wglMakeCurrent (ourWindowHandleToDeviceContext, ourOpenGLRenderingContext);

        HMODULE ogllib = LoadLibrary("OpenGL32.dll");
        assert(ogllib);

        char ogllib_name[MAX_PATH];
        GetModuleFileName(ogllib, ogllib_name, sizeof(ogllib_name));
        printf("ogllib_name: %s\n", ogllib_name);

        FreeLibrary(ogllib);

        printf("GL_VERSION: >>>%s<<<\n",(char*)glGetString(GL_VERSION));


        thelib = LoadLibrary("lib.dll");
        assert(thelib);

		typedef void F();
		F* f = (F*)GetProcAddress(thelib, "libfun");
		assert(f);
		f();


        }
        break;
	case WM_PAINT: {
		glClearColor(1, 0, 0, 1);
		glClear(GL_COLOR_BUFFER_BIT);

		typedef void F();
		F* f = (F*)GetProcAddress(thelib, "libdraw");
		assert(f);
		f();


		SwapBuffers(ourWindowHandleToDeviceContext);

	}break;
    default:
        return DefWindowProc(hWnd, message, wParam, lParam);
    }
    return 0;

}
