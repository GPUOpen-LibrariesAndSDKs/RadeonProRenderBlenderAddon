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
#include "SkyGen.h"

template<class T> inline T lerp(const T& A, const T& B, float Alpha)
{
    return A + Alpha * (B-A);
}

void SkyGen::generate(int w, int h, SkyRgbFloat32 *buffer)
{
    // Adjust sun glow value for better appearance.
    // Glow remap table. Pairs of floats. 1st value is sun disk size, 2nd value is minimal
    // glow which will make sun appearance acceptable. Note: this value depends on buffer resolution,
    // so if we'll use different IBL resolution, values should be changed!
    static const float glowRemap[] =
    {
        5.0f, 0.002f,
        2.5f, 0.02f,
        1.0f, 0.05f,
        0.5f, 0.1f,
        0.25f, 2.0f
    };

    static const int numGlowRemapItems = sizeof(glowRemap) / (sizeof(glowRemap[0]) * 2);
    float glowMinValue;
    if (sun_disk_scale >= glowRemap[0])
    {
        glowMinValue = glowRemap[1];
    }
    else
    {
        glowMinValue = glowRemap[(numGlowRemapItems-1)*2+1];
        for (int i = 1; i < numGlowRemapItems; i++)
        {
            float scale1 = glowRemap[(i-1)*2];
            float scale2 = glowRemap[i*2];
            if (sun_disk_scale >= scale2)
            {
                float value1 = glowRemap[(i-1)*2+1];
                float value2 = glowRemap[i*2+1];
                float alpha = ((float)sun_disk_scale - scale1) / (scale2 - scale1);
                glowMinValue = lerp(value1, value2, alpha);
                break;
            }
        }
    }
    sun_glow_intensity_adjusted = lerp(glowMinValue, 100.0f, (float)sun_glow_intensity / 100.0f);

    float nw = 1.0f / float(w);
    float nh = 1.0f / float(h);

    bool canMirrorSky = (fabs(sun_direction.y) < 0.00001f);
    int w2 = canMirrorSky ? (w + 1) / 2 : w; // divide by 2 with rounding up

#pragma omp parallel for
    for (int i = 0; i < h; i++)
    {
        float phi = float(PI * i * nh);
        int ii = h - i - 1;
        for (int j = 0; j < w2; j++)
        {
            float theta = float(2.0f * PI * j * nw);
            float sinphi = sin(phi);
            Point3 dir(
                cos(theta) * sinphi, // *radius,
                sin(theta) * sinphi, // *radius,
                -cos(phi) // *radius
            );
            SkyColor pix = computeColor(dir);

            SkyRgbFloat32 &bpix = buffer[ii * w + j];
            bpix.r = static_cast<float>(pix.r);
            bpix.g = static_cast<float>(pix.g);
            bpix.b = static_cast<float>(pix.b);

            if (canMirrorSky)
            {
                SkyRgbFloat32 &bpix2 = buffer[ii * w + (w - j - 1)];
                bpix2 = bpix;
            }
        }
    }
}
