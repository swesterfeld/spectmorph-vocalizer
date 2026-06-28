#pragma once

#include <cmath>
#include <algorithm>

enum class SmootherType {
  linear,
  logarithmic
};

template <SmootherType smoother_type>
class ParamSmoother
{
public:
  ParamSmoother (float start_value)
  {
    set_target (start_value, true);
  }

  /**
   * Initializes the smoother with sample rate and ramp time constants.
   */
  void reset (double sample_rate, float ramp_time_sec)
  {
    sample_rate_ = sample_rate;
    ramp_time_sec_ = ramp_time_sec;
  }

  /**
   * Sets a new destination target for the parameter.
   */
  void set_target (float target, bool now = false)
  {
    // safety clipping for log curves
    if constexpr (smoother_type == SmootherType::logarithmic)
      target = std::max(target, 0.00001f);

    if (target == target_ && !now)
      return;

    if (target == current_)
      now = true;

    target_ = target;

    if (now)
      {
        current_ = target_;
        if constexpr (smoother_type == SmootherType::linear)
          {
            step_or_factor_ = 0.0f;
          }
        else
          {
            step_or_factor_ = 1.0f;
          }
        ramp_counter_ = 0;
        return;
      }

    float total_ramp_samples = ramp_time_sec_ * sample_rate_;

    if (total_ramp_samples > 0.0f)
      {
        ramp_counter_ = static_cast<unsigned int>(total_ramp_samples);

        if constexpr (smoother_type == SmootherType::linear)
          {
            step_or_factor_ = (target_ - current_) / total_ramp_samples;
          }
        else
          {
            float sanitized_current = std::max (current_, 0.00001f);
            step_or_factor_ = std::pow (target_ / sanitized_current, 1.0f / total_ramp_samples);
          }
      }
    else
      {
        current_ = target_;
        ramp_counter_ = 0;
      }
  }

  /**
   * Get next smoothed value
   */
  inline float
  get_next()
  {
    if (ramp_counter_ > 0)
      {
        if constexpr (smoother_type == SmootherType::linear)
          {
            current_ += step_or_factor_;
          }
        else
          {
            current_ *= step_or_factor_;
          }

        ramp_counter_--;

        if (ramp_counter_ == 0)
          current_ = target_;
      }
    return current_;
  }
  /**
   * Check wether we're currently smoothing or if the output is a constant value
   */
  bool
  is_constant()
  {
    return ramp_counter_ == 0;
  }

  /**
   * Fills an entire buffer array block.
   */
  void
  process_block (float* output_buffer, unsigned int num_samples)
  {
    for (unsigned int i = 0; i < num_samples; ++i)
      output_buffer[i] = get_next();
  }

private:
  double sample_rate_ = 44100.0;
  float ramp_time_sec_ = 0.025f;

  float target_ = 0.0f;
  float current_ = 0.0f;
  float step_or_factor_ = 0.0f;
  unsigned int ramp_counter_ = 0;
};
