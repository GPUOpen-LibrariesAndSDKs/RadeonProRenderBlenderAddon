cdef extern from "windows.h":
    pass


cdef extern from "gl/gl.h":

    ctypedef unsigned int GLenum;
    ctypedef unsigned char GLboolean;
    ctypedef unsigned int GLbitfield;
    ctypedef signed char GLbyte;
    ctypedef short GLshort;
    ctypedef int GLint;
    ctypedef int GLsizei;
    ctypedef unsigned char GLubyte;
    ctypedef unsigned short GLushort;
    ctypedef unsigned int GLuint;
    ctypedef float GLfloat;
    ctypedef float GLclampf;
    ctypedef void GLvoid;
    ctypedef int GLintptrARB;
    ctypedef int GLsizeiptrARB;
    ctypedef int GLfixed;
    ctypedef int GLclampx;
    
    ctypedef void (*_GLfuncptr)();

    GLenum glGetError();

def getError():
    return glGetError(); 


