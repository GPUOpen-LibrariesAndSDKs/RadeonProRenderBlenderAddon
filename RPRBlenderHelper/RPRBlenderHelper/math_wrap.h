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
#pragma once

#define _USE_MATH_DEFINES

#include <math.h>


/** Define PI. */
#define PI 3.14159265358979323846
#define PI_F 3.14159265358979323846f

/** Convert degrees to radians. */
inline float toDegrees(float radians)
{
	return radians * (180.0f / PI_F);
}

/** Convert radians to degrees. */
inline float toRadians(float degrees)
{
	return degrees * (PI_F / 180.0f);
}



class Point2
{
public:
	Point2()
	{}
	Point2(float inX, float inY)
	: x(inX)
	, y(inY)
	{}

	float	x;
	float	y;
};



class Point3
{
	
public:
	float x, y, z;

	Point3	()	{ x = y = z = 0.0f; };
	Point3	( const float * pf );
	Point3	( const Point3& v );
	Point3	( float x, float y, float z );


	operator float * ();
    operator const float * () const;

	// assignment operators
    inline Point3& operator () ( float _x, float _y, float _z);
    
	inline Point3& operator += ( const Point3& v );
    inline Point3& operator -= ( const Point3& v );
	inline Point3& operator *= ( const Point3& v );
	inline Point3& operator /= ( const Point3& v );

    inline Point3& operator *= ( float f );
    inline Point3& operator /= ( float f );
	
	inline Point3& operator += ( float f );

	Point3& operator = ( const float * pf );

	// unary operators
    Point3 operator + () const;
    Point3 operator - () const;

	// binary operators
    Point3 operator + ( const Point3& v ) const;
    Point3 operator - ( const Point3& v ) const;
    Point3 operator * ( float f ) const;
    Point3 operator / ( float f ) const;

	float operator * ( const Point3 &v ) const; // —кал€рное произведение

	bool operator == ( const Point3& v ) const;
    bool operator != ( const Point3& v ) const;
	
	
	
	// Access to ith component of the vector.			 							
	float& operator [] ( int index )				{ return * ( ( &x ) + index ); };
	
	// Returns ith component of the vector.
	const float& operator [] ( int index ) const	{ return * ( ( &x ) + index ); };


	// 
	float			Distance		( const Point3 &v ) const;


	// Returns length of the vector 
	float			Length			() const;


	// Returns the vector scaled to unit length. This vector can't be 0-vector.
	Point3&			Normalize		();

	// Returns vector/cross/outer product of *this and v 
	Point3&			Cross			( const Point3& v1, const Point3& v2 );
	Point3			Cross			( const Point3& v1 );


	// Returns dot/scalar/inner product of *this and v 
	float			Dot				( const Point3& v ) const;

	Point3&			Set				( float x, float y, float z );
	Point3&			SetNull			();


	Point3&			Scale			( const Point3 &vScale );

	friend inline float DotProd(const Point3& A, const Point3& B)
	{
		return A.Dot(B);
	}
};



inline Point3::Point3( const float * pf )
{
    x = pf[ 0 ];
    y = pf[ 1 ];
    z = pf[ 2 ];
}

inline Point3::Point3( const Point3& v )
{
    x = v.x;
    y = v.y;
    z = v.z;
}

inline Point3::Point3( float x, float y, float z )
{
    this->x = x;
    this->y = y;
    this->z = z;
}

inline Point3::operator float * ()
{
    return ( float * ) &x;
}

inline Point3::operator const float * () const
{
    return ( const float * ) &x;
}

inline Point3& Point3::operator () ( float _x, float _y, float _z)
{
 x = _x; y = _y; z = _z; return *this;
}

inline Point3& Point3::operator += ( const Point3& v )
{
    x += v.x;
    y += v.y;
    z += v.z;

    return * this;
}

inline Point3& Point3::operator -= ( const Point3& v )
{
    x -= v.x;
    y -= v.y;
    z -= v.z;
    return * this;
}

inline Point3& Point3::operator /= ( const Point3& v )
{
	x /= v.x;
	y /= v.y;
	z /= v.z;
	return * this;
}

inline Point3& Point3::operator *= ( const Point3& v )
{
	x *= v.x;
	y *= v.y;
	z *= v.z;
	return * this;
}

inline Point3& Point3::operator *= ( float f )
{
    x *= f;
    y *= f;
    z *= f;
    return * this;
}

inline Point3& Point3::operator /= ( float f )
{
    float fInv = 1.0f / f;
    x *= fInv;
    y *= fInv;
    z *= fInv;
    return * this;
}

inline Point3& Point3::operator += ( float f )
{
    x += f;
    y += f;
    z += f;
    return * this;
}

inline Point3& Point3::operator = ( const float * pf )
{
	x = pf[ 0 ];
	y = pf[ 1 ];
	z = pf[ 2 ];

	return * this;
}

inline Point3 Point3::operator + () const
{
    return * this;
}

inline Point3 Point3::operator - () const
{
    return Point3( -x, -y, -z );
}

inline Point3 Point3::operator + ( const Point3& v ) const
{
    return Point3( x + v.x, y + v.y, z + v.z );
}

inline Point3 Point3::operator - ( const Point3& v ) const
{
    return Point3( x - v.x, y - v.y, z - v.z );
}

inline Point3 Point3::operator * ( float f ) const
{
    return Point3( x * f, y * f, z * f );
}

inline Point3 Point3::operator / ( float f ) const
{
    float fInv = 1.0f / f;
    return Point3( x * fInv, y * fInv, z * fInv );
}

inline float Point3::operator * ( const Point3 &v ) const
{
	return x * v.x + y * v.y + z * v.z;
}

inline bool Point3::operator == ( const Point3& v ) const
{
    return x == v.x && y == v.y && z == v.z;
}

inline bool Point3::operator != ( const Point3& v ) const
{
    return x != v.x || y != v.y || z != v.z;
}

inline float Point3::Distance( const Point3 &v ) const
{
	
	return Point3( x - v.x, y - v.y, z - v.z ).Length();
}

inline float Point3::Length() const
{
	return ( float ) sqrt( x * x + y * y + z * z );
}

inline Point3& Point3::Normalize()
{
	float l = Length();

	if ( l )
	{
		l = 1.0f / l;
		x *= l;
		y *= l;
		z *= l;
	}
	else
	{
		x = y = z = 0;
	}

	return * this;
}

inline Point3& Point3::Cross( const Point3& v1, const Point3& v2 )	
{
	x = v1.y * v2.z - v1.z * v2.y;
	y = v1.z * v2.x - v1.x * v2.z;
	z = v1.x * v2.y - v1.y * v2.x;

	return * this;
}

inline Point3 Point3::Cross( const Point3& v1 )	
{
	Point3 v;
	v.x = y * v1.z - z * v1.y;
	v.y = z * v1.x - x * v1.z;
	v.z = x * v1.y - y * v1.x;

	return v;
}

inline float Point3::Dot( const Point3& v ) const	
{
	return x * v.x + y * v.y + z * v.z;
}

inline Point3& Point3::Set( float x, float y, float z )
{
	this->x = x;
	this->y = y;
	this->z = z;

	return * this;
}

inline Point3 operator * ( float f, const Point3 & tVec )
{
	return tVec * f;
}





class MColor
{
public:

	MColor()
		: r(0.0f)
		, g(0.0f)
		, b(0.0f)
		, a(1.0f)
	{}
	MColor(float inR, float inG, float inB, float inA)
		: r(inR)
		, g(inG)
		, b(inB)
		, a(inA)
	{}

	MColor(float inR, float inG, float inB)
		: r(inR)
		, g(inG)
		, b(inB)
		, a(1.0f)
	{}

	MColor(float * float3_ptr)
		: r(float3_ptr[0])
		, g(float3_ptr[1])
		, b(float3_ptr[2])
		, a(1.0f)
	{}

	float	r, g, b, a;
};
