/* SVF: The Art of VA Filter Desgin 2.1.2 by Vadim Zavalishin */
class SVF
{
  float g = 0;
  float d = 1;
  float g1 = 1;

  float s1l = 0;
  float s1r = 0;
  float s2l = 0;
  float s2r = 0;

  float m_lp = 0;
  float m_bp = 0;
  float m_hp = 0;

  float cutoff_warp_factor = 0;

  /* tan(x) approximation for x in [0:pi/2] with low relative error (a lot better than 0.1 cent) */
  float
  tan_approx (float x)
  {
    const float c1 = -2.4908436646011975;
    const float c2 = 0.16995685098890287;
    if (x < float (M_PI / 4))
      {
        float x2 = x * x;
        return x * (c1 + c2 * x2) / (c1 + x2);
      }
    else /* for x > pi/4, use (1 / approx (pi/2 - x)) */
      {
        x = float (M_PI / 2) - x;

        float x2 = x * x;
        return (c1 + x2) / (x * (c1 + c2 * x2));
      }
  }

  float
  cutoff_warp (float cutoff)
  {
    return tan_approx (cutoff * cutoff_warp_factor);
  }

  void
  set_params_g_Q_inv (float Q_inv)
  {
    /* instead of using R to compute the SVF parameters, use Q_inv == 1 / Q == 2 * R */
    d = 1.f / (1 + Q_inv*g + g*g);
    g1 = Q_inv + g;
  }
public:
  enum Output {
    LP,
    BP,
    HP,
    AP,
    PEQ,
    LSH,
    HSH,
    NOTCH
  };
  static constexpr std::array<const char *, 8> output_name = { "lp", "bp", "hp", "ap", "peq", "lsh", "hsh", "notch" };
  void
  reset (float sample_rate)
  {
    s1l = s1r = 0;
    s2l = s2r = 0;

    cutoff_warp_factor = M_PI / sample_rate;
  }
  void
  set_params (Output output, float cutoff, float Q_inv, float gain_db)
  {
    if (output == LP || output == BP || output == HP || output == AP || output == NOTCH)
      {
        g = cutoff_warp (cutoff);
        set_params_g_Q_inv (Q_inv);
        if (output == BP)
          m_bp = Q_inv;
        else if (output == AP)
          m_bp = -Q_inv;
      }
    else if (output == PEQ)
      set_peq_params_A (cutoff, Q_inv, powf (10, gain_db / 40));
    else if (output == LSH)
      set_lsh_params_M (cutoff, Q_inv, powf (10, gain_db / 80));
    else if (output == HSH)
      set_hsh_params_M (cutoff, Q_inv, powf (10, gain_db / 80));
    else
      {
        assert (false);
      }
  }
  void
  set_peq_params_A (float cutoff, float Q_inv, float A)
  {
    g = cutoff_warp (cutoff);
    set_params_g_Q_inv (Q_inv / A);

    m_bp = A * Q_inv;
  }
  void
  set_lsh_params_M (float cutoff, float Q_inv, float M)
  {
    float A = M * M;

    m_lp = A * A;
    m_bp = A * Q_inv;
    g = cutoff_warp (cutoff) / M;
    set_params_g_Q_inv (Q_inv);
  }
  void
  set_hsh_params_M (float cutoff, float Q_inv, float M)
  {
    float A = M * M;

    m_bp = A * Q_inv;
    m_hp = A * A;
    g = cutoff_warp (cutoff) * M;
    set_params_g_Q_inv (Q_inv);
  }
  template<Output output>
  void
  process_mod (float *left, float *right, float *freq_in, float *Q_inv_in, float *gain_db_in, uint n_frames)
  {
    if (!n_frames)
      return;

    auto convert_gain_to_F = [gain_db_in] (uint i)
      {
        if constexpr (output == PEQ)
          return powf (10, gain_db_in[i] / 40);
        else if constexpr (output == LSH || output == HSH)
          return powf (10, gain_db_in[i] / 80);
        else
          return 0.f;
      };
    static constexpr int BS = 16;
    float next_F = convert_gain_to_F (0);
    uint i = 0;
    while (i < n_frames)
      {
        float delta_F = 0;
        float F = next_F;

        uint todo = std::min<uint> (BS, n_frames - i);
        if (n_frames - i > BS)
          {
            next_F = convert_gain_to_F (i + BS);
            delta_F = (next_F - F) / BS;
          }
        else if (todo > 1)
          {
            next_F = convert_gain_to_F (i + todo - 1);
            delta_F = (next_F - F) / (todo - 1);
          }
        for (uint j = 0; j < todo; j++)
          {
            const float freq = freq_in[i + j];
            const float Q_inv = Q_inv_in[i + j];

            if constexpr (output == PEQ)
              {
                set_peq_params_A (freq, Q_inv, F);
                F += delta_F;
              }
            else if constexpr (output == LSH)
              {
                set_lsh_params_M (freq, Q_inv, F);
                F += delta_F;
              }
            else if constexpr (output == HSH)
              {
                set_hsh_params_M (freq, Q_inv, F);
                F += delta_F;
              }
            else
              {
                g = cutoff_warp (freq);

                set_params_g_Q_inv (Q_inv);

                if (output == BP)
                  m_bp = Q_inv;
                if (output == AP)
                  m_bp = -Q_inv;
              }
            process_s<output> (left + i + j, right + i + j);
          }
        i += todo;
      }
  }
  template<Output output>
  float process (float l)
  {
    float dummy = 0;
    process_s<output> (&l, &dummy);
    return l;
  }
  template<Output output>
  void process_s (float *l, float *r) __restrict__
  {
    // hp
    float hpl, hpr;
    hpl = (*l - g1*s1l - s2l) * d;
    hpr = (*r - g1*s1r - s2r) * d;

    // first integrator
    float v1l, v1r;
    v1l = g * hpl;
    v1r = g * hpr;

    float bpl, bpr;
    bpl = v1l + s1l;
    bpr = v1r + s1r;
    s1l = bpl + v1l;
    s1r = bpr + v1r;

    // second integrator
    float v2l, v2r;
    v2l = g * bpl;
    v2r = g * bpr;

    float lpl, lpr;
    lpl = v2l + s2l;
    lpr = v2r + s2r;
    s2l = lpl + v2l;
    s2r = lpr + v2r;

    if (output == LP)
      {
        *l = lpl;
        *r = lpr;
      }
    else if (output == BP)
      {
        *l = bpl * m_bp;
        *r = bpr * m_bp;
      }
    else if (output == HP)
      {
        *l = hpl;
        *r = hpr;
      }
    else if (output == AP)
      {
        *l = lpl + bpl * m_bp + hpl;
        *r = lpr + bpr * m_bp + hpr;
      }
    else if (output == PEQ)
      {
        *l = lpl + hpl + bpl * m_bp;
        *r = lpr + hpr + bpr * m_bp;
      }
    else if (output == LSH)
      {
        *l = m_lp * lpl + bpl * m_bp + hpl;
        *r = m_lp * lpr + bpr * m_bp + hpr;
      }
    else if (output == HSH)
      {
        *l = lpl + bpl * m_bp + m_hp * hpl;
        *r = lpr + bpr * m_bp + m_hp * hpr;
      }
    else if (output == NOTCH)
      {
        *l = lpl + hpl;
        *r = lpr + hpr;
      }
    else
      {
        assert (false);
      }
  }
  template<Output output>
  void
  process_block (float *left, float *right, uint n_samples)
  {
    for (uint i = 0; i < n_samples; i++)
      {
        process_s<output> (left + i, right + i);
      }
  }
  void
  process_block (SVF::Output output, float *left, float *right, uint n_samples)
  {
    switch (output)
      {
        case LP:    process_block<LP> (left, right, n_samples);
                    break;
        case BP:    process_block<BP> (left, right, n_samples);
                    break;
        case HP:    process_block<HP> (left, right, n_samples);
                    break;
        case AP:    process_block<AP> (left, right, n_samples);
                    break;
        case PEQ:   process_block<PEQ> (left, right, n_samples);
                    break;
        case LSH:   process_block<LSH> (left, right, n_samples);
                    break;
        case HSH:   process_block<HSH> (left, right, n_samples);
                    break;
        case NOTCH: process_block<NOTCH> (left, right, n_samples);
                    break;
        default:    assert (false);
      }
  }
  void
  process_mod (SVF::Output output, float *left, float *right, float *freq_in, float *Q_inv_in, float *gain_db_in, uint n_frames)
  {
    switch (output)
      {
        case LP:    process_mod<LP> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        case BP:    process_mod<BP> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        case HP:    process_mod<HP> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        case AP:    process_mod<AP> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        case PEQ:   process_mod<PEQ> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        case LSH:   process_mod<LSH> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        case HSH:   process_mod<HSH> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        case NOTCH: process_mod<NOTCH> (left, right, freq_in, Q_inv_in, gain_db_in, n_frames);
                    break;
        default:    assert (false);
      }
  }
};


