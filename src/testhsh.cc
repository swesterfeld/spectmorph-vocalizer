#include <cmath>
#include <cstdio>
#include <cassert>
#include <array>

#include "svf.hh"

#if 0
class HighShelfSVF
{
public:
    void prepare(double sampleRate)
    {
        fs = sampleRate;
        lp = bp = 0.0f;
    }

    // Audio-rate modulation version:
    float process(float x, float freqHz, float gainDb, float Q = 0.707f)
    {
        // ---- convert audio-rate params ----
        float A = std::pow(10.0f, gainDb / 40.0f); // amplitude (sqrt-power relationship)

        // clamp frequency to stability range
        if (freqHz < 10.0f) freqHz = 10.0f;
        if (freqHz > fs * 0.45f) freqHz = fs * 0.45f;

        // TPT coefficient (recomputed every sample)
        float g = std::tan(float(M_PI) * freqHz / fs);

        // damping
        float R = 1.0f / Q;

        // ---- SVF core (stable form) ----
        // integrator update structure
        float hp = (x - lp - R * bp) / (1.0f + g * (g + R));
        float v  = g * hp;

        bp += v;
        lp += g * bp;

        hp = x - lp - R * bp;

        // ---- high shelf mix ----
        // standard SVF-derived shelf:
        // low stays ~1, high becomes A^2
        float y =
            lp +
            A * bp +
            (A * A) * hp;

        return y;
    }

private:
    double fs = 44100.0;

    float lp = 0.0f;
    float bp = 0.0f;
};
#pragma once
#include <cmath>

class HighShelfSVF
{
public:
    void prepare(double sampleRate)
    {
        fs = sampleRate;
        z1 = z2 = 0.0f;
    }

    float process(float x, float freqHz, float gainDb, float Q = 0.707f)
    {
        float A = std::pow(10.0f, gainDb / 40.0f);

        if (freqHz < 10.0f) freqHz = 10.0f;
        if (freqHz > fs * 0.45f) freqHz = fs * 0.45f;

        float g = std::tan(float(M_PI) * freqHz / fs);
        float R = 1.0f / Q;

        // ---- TPT normalization ----
        float d = 1.0f / (1.0f + g * (g + R));

        // state variables (low-pass style integrators)
        float v3 = x - z2;

        float v1 = (g * z1 + g * v3) * d;
        float v2 = (z2 + g * z1 + g * v3) * d;

        z1 = 2.0f * v1 - z1;
        z2 = 2.0f * v2 - z2;

        float lp = v2;
        float hp = x - R * v1 - lp;

        // ---- KEY FIX: gain applied in orthogonal domain ----
        // avoids BP cancellation entirely
        float y = (A * A) * hp + A * R * v1 + lp;

        return y;
    }

private:
    double fs = 44100.0;
    float z1 = 0.0f, z2 = 0.0f;
};


#pragma once
#include <cmath>

class HighShelfSVF
{
public:
    void prepare(double sampleRate)
    {
        fs = sampleRate;
        ic1eq = 0.0f;
        ic2eq = 0.0f;
    }

    float process(float x, float freqHz, float gainDb, float Q = 0.707f)
    {
        float A = std::pow(10.0f, gainDb / 40.0f);

        if (freqHz < 10.0f) freqHz = 10.0f;
        if (freqHz > fs * 0.45f) freqHz = fs * 0.45f;

        float g = std::tan(float(M_PI) * freqHz / fs);
        float k = 1.0f / Q;

        // --- TPT SVF core (Zavalishin form) ---
        float v0 = x;
        float v3 = v0 - ic2eq;

        float v1 = (g * v3 + ic1eq) / (1.0f + g * (g + k));
        float v2 = (g * v1 + ic2eq + g * v3) / (1.0f + g * (g + k));

        ic1eq = 2.0f * v1 - ic1eq;
        ic2eq = 2.0f * v2 - ic2eq;

        float lp = v2;
        float bp = v1;
        float hp = v0 - k * bp - lp;

        // ---- CORRECT shelf mapping ----
        // This preserves correct DC / HF gain relationship:
        float y =
            lp +
            A * bp +
            (A * A - 1.0f) * hp;

        return y;
    }

private:
    double fs = 44100.0;

    float ic1eq = 0.0f;
    float ic2eq = 0.0f;
};
#pragma once
#include <cmath>

class HighShelf
{
public:
    void prepare(double sampleRate)
    {
        fs = sampleRate;
        z1 = 0.0f;
        z2 = 0.0f;
    }

    // Audio-rate modulated version
    float process(float x, float freqHz, float gainDb, float Q = 0.707f)
    {
        // --- clamp frequency ---
        if (freqHz < 10.0f) freqHz = 10.0f;
        if (freqHz > fs * 0.45f) freqHz = fs * 0.45f;

        // --- RBJ-style shelf parameters ---
        float A = std::pow(10.0f, gainDb / 20.0f);   // IMPORTANT: NOT /40
        float w0 = 2.0f * float(M_PI) * freqHz / fs;
        float cosw0 = std::cos(w0);
        float sinw0 = std::sin(w0);

        float alpha = sinw0 / (2.0f * Q);

        float sqrtA = std::sqrt(A);

        // --- RBJ high-shelf coefficients ---
        float b0 =    A*( (A+1) + (A-1)*cosw0 + 2*sqrtA*alpha );
        float b1 = -2*A*( (A-1) + (A+1)*cosw0 );
        float b2 =    A*( (A+1) + (A-1)*cosw0 - 2*sqrtA*alpha );
        float a0 =        (A+1) - (A-1)*cosw0 + 2*sqrtA*alpha;
        float a1 =  2*( (A-1) - (A+1)*cosw0 );
        float a2 =        (A+1) - (A-1)*cosw0 - 2*sqrtA*alpha;

        // --- normalize ---
        b0 /= a0;
        b1 /= a0;
        b2 /= a0;
        a1 /= a0;
        a2 /= a0;

        // --- Direct Form II Transposed ---
        float y = b0 * x + z1;
        z1 = b1 * x + z2 - a1 * y;
        z2 = b2 * x - a2 * y;

        return y;
    }

private:
    double fs = 44100.0;

    float z1 = 0.0f;
    float z2 = 0.0f;
};
#pragma once
#include <cmath>

class HighShelf
{
public:
    void prepare(double sampleRate)
    {
        fs = sampleRate;
        z1 = z2 = 0.0f;
    }

    float process(float x, float freqHz, float gainDb, float Q = 0.707f)
    {
        if (freqHz < 10.0f) freqHz = 10.0f;
        if (freqHz > fs * 0.45f) freqHz = fs * 0.45f;

        // ✔ CRITICAL FIX: use power convention consistent with RBJ form
        float A = std::pow(10.0f, gainDb / 20.0f);

        float w0 = 2.0f * float(M_PI) * freqHz / fs;
        float cosw0 = std::cos(w0);
        float sinw0 = std::sin(w0);

        float alpha = sinw0 / (2.0f * Q);
        float sqrtA = std::sqrt(A);

        // RBJ high shelf (consistent normalization)
        float b0 =    A*( (A+1) + (A-1)*cosw0 + 2*sqrtA*alpha );
        float b1 = -2*A*( (A-1) + (A+1)*cosw0 );
        float b2 =    A*( (A+1) + (A-1)*cosw0 - 2*sqrtA*alpha );
        float a0 =        (A+1) - (A-1)*cosw0 + 2*sqrtA*alpha;
        float a1 =  2*( (A-1) - (A+1)*cosw0 );
        float a2 =        (A+1) - (A-1)*cosw0 - 2*sqrtA*alpha;

        // normalize
        b0 /= a0;
        b1 /= a0;
        b2 /= a0;
        a1 /= a0;
        a2 /= a0;

        // DF2T
        float y = b0 * x + z1;
        z1 = b1 * x + z2 - a1 * y;
        z2 = b2 * x - a2 * y;

        return y;
    }

private:
    double fs = 44100.0;
    float z1 = 0.0f, z2 = 0.0f;
};
#endif

#include <cmath>

class HighShelfBiquad
{
public:
    HighShelfBiquad() { reset(); }

    void reset()
    {
        z1 = z2 = 0.0f;
    }

    // fs: sample rate
    // freq: shelf frequency (Hz)
    // gainDB: gain in dB
    // Q: interpreted as "sharpness" control (mapped to slope)
    void setParams(float fs, float freq, float gainDB, float Q)
    {
        const float A = std::pow(10.0f, gainDB / 40.0f);
        const float omega = 2.0f * float(M_PI) * freq / fs;
        const float cosw = std::cos(omega);
        const float sinw = std::sin(omega);

        // ---- Q -> S (heuristic mapping) ----
        // RBJ uses S (slope). We map Q -> S in a smooth, usable way.
        // Q ~ 0.5 (gentle)  -> S small
        // Q ~ 1.0 (medium)  -> S medium
        // Q > 1.0 (sharp)   -> S larger
        float S = 1.0f / (2.0f * Q * Q);

        // clamp for stability / usability
        if (S < 0.1f) S = 0.1f;
        if (S > 5.0f) S = 5.0f;

        const float alpha =
            sinw * 0.5f *
            std::sqrt((A + 1.0f / A) * (1.0f / S - 1.0f) + 2.0f);

        const float twoSqrtAAlpha = 2.0f * std::sqrt(A) * alpha;

        // RBJ high-shelf coefficients
        b0 =    A * ((A + 1.0f) + (A - 1.0f) * cosw + twoSqrtAAlpha);
        b1 = -2.0f * A * ((A - 1.0f) + (A + 1.0f) * cosw);
        b2 =    A * ((A + 1.0f) + (A - 1.0f) * cosw - twoSqrtAAlpha);

        a0 =        (A + 1.0f) - (A - 1.0f) * cosw + twoSqrtAAlpha;
        a1 =  2.0f * ((A - 1.0f) - (A + 1.0f) * cosw);
        a2 =        (A + 1.0f) - (A - 1.0f) * cosw - twoSqrtAAlpha;

        // normalize
        b0 /= a0;
        b1 /= a0;
        b2 /= a0;
        a1 /= a0;
        a2 /= a0;
    }

    float process(float x)
    {
        // Direct Form II Transposed
        float y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        return y;
    }

private:
    float b0{}, b1{}, b2{};
    float a0{}, a1{}, a2{};
    float z1{}, z2{};
};

main()
{
  int SR = 44100;
  float buffer[5*SR], buffer2[5*SR], in_freq[5*SR];
  SVF svf;
  //HighShelfBiquad high_shelf_l;
  //HighShelfBiquad high_shelf_r;
  double phase = 0;
  for (int i = 0; i < 5*SR; i++)
    {
      double freq = 20*(pow (1000,(double (i)/44100/5)));
      in_freq[i] = freq;
      buffer[i] = sin (phase);
      buffer2[i] = cos (phase);
      phase += freq * 2 * M_PI / 44100;
    }
  //high_shelf_l.setParams (SR, 312, 4.5, 1.5);
  //high_shelf_r.setParams (SR, 312, 4.5, 1.5);
  svf.reset (44100);
  svf.set_params (SVF::HSH, 312, 1 / 0.34, 4.5);
  int i = 0;
  svf.process_block (SVF::HSH, buffer, buffer2, 5*SR);
#if 0
  while (i < 5 * SR)
    {
      buffer[i] = high_shelf_l.process (buffer[i]);
      buffer2[i] = high_shelf_r.process (buffer2[i]);
      i++;
    }
#endif
  for (int i = 0; i < 5*SR; i++)
    printf ("%f %.8f\n", in_freq[i], sqrt (buffer[i] * buffer[i] + buffer2[i] * buffer2[i]));
}
