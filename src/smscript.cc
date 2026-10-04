// Licensed GNU LGPL v2.1 or later: http://www.gnu.org/licenses/lgpl-2.1.html

#include "smlivedecoder.hh"
#include "smutils.hh"
#include "smmain.hh"
#include "smaudiotool.hh"
#include "smmicroconf.hh"
#include "smwavdata.hh"
#include "smformantcorrection.hh"
#include "smmorphutils.hh"
#include "svf.hh"
#include "paramsmoother.hh"

using namespace SpectMorph;

using std::vector;
using std::string;
using std::array;

class ScriptBlockSource : public LiveDecoderSource
{
  Audio                       my_audio;
  array<AudioBlock, 2>        my_audio_block;
  array<FormantCorrection, 2> formant_correction;
  array<double, 2>            block_volume_factor {};
  RTMemoryArea&               rt_memory_area;
  double                      morphing = 0;
  double                      time_ms = 0;
  string                      label;
  FILE                       *frames_file{};
public:
  ScriptBlockSource (float mix_freq, RTMemoryArea& rt_memory_area, FILE *frames_file) :
    rt_memory_area (rt_memory_area),
    frames_file (frames_file)
  {
    my_audio.frame_size_ms = 40;
    my_audio.frame_step_ms = 10;
    my_audio.attack_start_ms = 10;
    my_audio.attack_end_ms = 20;
    my_audio.zeropad = 4;
    my_audio.loop_type = Audio::LOOP_NONE;
    my_audio.mix_freq = mix_freq;
  }
  void retrigger (int channel, float freq, int midi_velocity)
  {
    printf ("retrigger\n");
    for (auto& fc : formant_correction)
      {
        fc.set_mode (FormantCorrection::MODE_HARMONIC_RESYNTHESIS);
        fc.set_max_partials (1000);
        fc.set_fuzzy_resynth (20);
        fc.retrigger();
      }
    my_audio.fundamental_freq = freq;
  }
  void
  advance (double time_delta_ms)
  {
    for (auto& fc : formant_correction)
      fc.advance (time_delta_ms);
    time_ms += time_delta_ms;
  }
  Audio *audio()
  {
    return &my_audio;
  }
  bool
  rt_audio_block (size_t index, RTAudioBlock& out_block)
  {
    fprintf (frames_file, "%s\n", /* avoid i18n using string_printf */
        string_printf ("%f\t%f\t%s", time_ms / 1000, time_ms / 1000, label.c_str()).c_str());

    if (block_volume_factor[0] == 0 && block_volume_factor[1] == 0)
      {
        /* silence */
        out_block.noise.set_capacity (my_audio_block[0].noise.size());
        for (size_t i = 0; i < my_audio_block[0].noise.size(); i++)
          out_block.noise.push_back (0);
      }
    else
      {
        RTAudioBlock block_a (&rt_memory_area);
        RTAudioBlock block_b (&rt_memory_area);

        formant_correction[0].process_block (my_audio_block[0], block_a);
        formant_correction[1].process_block (my_audio_block[1], block_b);
        morph (out_block, true, block_a, true, block_b, morphing, MorphUtils::MorphMode::DB_LINEAR);
      }
    return true;
  }
  void
  set_audio_block (size_t blk, const AudioBlock& in_block, double ratio, double volume_factor)
  {
    formant_correction[blk].set_ratio (ratio);
    block_volume_factor[blk] = volume_factor;

    /* scale volume of in_block * volume_factor */
    AudioBlock block = in_block;
    const int norm_delta_idb = sm_factor2delta_idb (volume_factor);

    vector<uint16_t>& mags = block.mags;
    for (size_t i = 0; i < mags.size(); i++)
      mags[i] = std::clamp (mags[i] + norm_delta_idb, 0, 65535);

    vector<uint16_t>& noise = block.noise;
    for (size_t i = 0; i < noise.size(); i++)
      noise[i] = std::clamp (noise[i] + norm_delta_idb, 0, 65535);

    vector<uint16_t>& env = block.env;
    for (size_t i = 0; i < env.size(); i++)
      env[i] = std::clamp (env[i] + norm_delta_idb, 0, 65535);
    my_audio_block[blk] = block;
  }
  void
  set_morphing (double morphing)
  {
    this->morphing = morphing;
  }
  void
  set_portamento_freq (float freq)
  {
    // ignore
  }
  void
  set_label (const string& s)
  {
    label = s;
  }
};


int
main (int argc, char **argv)
{
  Main main (&argc, &argv);

  if (argc != 4)
    {
      fprintf (stderr, "usage: smscript <script> <out_wav> <frames>\n");
      return 1;
    }

  MicroConf script_parser (argv[1]);
  if (!script_parser.open_ok())
    {
      fprintf (stderr, "error opening file %s\n", argv[1]);
      exit (1);
    }
  script_parser.set_number_format (MicroConf::NO_I18N);

  const int mix_freq = 48000;
  const int freq_slide_ms = 80;
  const double vibrato_attack = 0;
  const double vibrato_depth = 15;
  const double vibrato_frequency = 4;
  // Slow glides can otherwise turn into repeated pitch reversals at 4 Hz.
  ParamSmoother<SmootherType::linear> vibrato_depth_smoother { vibrato_depth };
  vibrato_depth_smoother.reset (mix_freq, 0.030);

  FILE *frames_file = fopen (argv[3], "w");
  if (!frames_file)
    {
      fprintf (stderr, "error opening file %s\n", argv[3]);
      exit (1);
    }

  SVF high_shelf;
  double hsh_freq = 312;
  ParamSmoother<SmootherType::linear> hsh_gain_smoother { 0 };
  high_shelf.reset (mix_freq);
  hsh_gain_smoother.reset (mix_freq, 0.001);

  RTMemoryArea rt_memory_area;
  ScriptBlockSource source (mix_freq, rt_memory_area, frames_file);
  LiveDecoder live_decoder (&source, mix_freq);

  double freq = 440; // will be overwritten from script
  double target_freq = 0;
  double freq_factor = 0;
  int    freq_steps = 0;

  live_decoder.set_vibrato (true, vibrato_depth, vibrato_frequency, vibrato_attack);
  live_decoder.retrigger (0, freq, 127);

  vector<std::unique_ptr<Audio>> audio_vector;

  vector<float> output;
  while (script_parser.next())
    {
      int i, blk;
      string s;
      double d, f, v;

      if (script_parser.command ("load", s))
        {
          printf ("loading %s as audio %zd\n", s.c_str(), audio_vector.size());

          std::unique_ptr<Audio> audio = std::make_unique<Audio>();
          Error error = audio->load (s);
          assert (!error);

          audio_vector.push_back (std::move (audio));
        }
      else if (script_parser.command ("process", i))
        {
          size_t offset = output.size();
          output.resize (output.size() + i);
          vector<float> freq_in (i);
          double block_vibrato_depth = vibrato_depth;
          for (auto &f : freq_in)
            {
              block_vibrato_depth = vibrato_depth_smoother.get_next();
              if (freq_steps)
                {
                  freq *= freq_factor;
                  freq_steps--;
                }
              f = freq;
            }
          live_decoder.set_vibrato (true, block_vibrato_depth, vibrato_frequency, vibrato_attack);
          live_decoder.process (rt_memory_area, i, freq_in.data(), output.data() + offset);
          for (size_t s = offset; s < offset + i; s++)
            {
              float dummy = 0;
              high_shelf.set_params (SVF::HSH, hsh_freq, /* Q_inv */ 1 / 0.34, hsh_gain_smoother.get_next());
              high_shelf.process_s<SVF::HSH> (&output[s], &dummy);
            }

          double time_ms = i / 48000. * 1000;
          source.advance (time_ms);
        }
      else if (script_parser.command ("freq-glissando", f))
        {
          vibrato_depth_smoother.set_target (0);
          if (target_freq == 0)
            freq = f;
          target_freq = f;
          freq_steps = mix_freq / 1000;
          freq_factor = pow (target_freq / freq, 1.0 / freq_steps);
        }
      else if (script_parser.command ("freq", f))
        {
          vibrato_depth_smoother.set_target (vibrato_depth);
          if (target_freq != f)
            {
              if (target_freq == 0) /* start of the audio file */
                {
                  target_freq = f;
                  freq = f;
                }
              else
                {
                  target_freq = f;
                  freq_steps = mix_freq / 1000. * freq_slide_ms;
                  freq_factor = pow (target_freq / freq, 1.0 / freq_steps);
                }
            }
        }
      else if (script_parser.command ("seek", blk, i, d, v))
        {
          assert (i >= 0 && size_t (i) < audio_vector.size());
          const auto& active_audio = audio_vector[i];

          int start = 0;
          int end = active_audio->contents.size() - 1;
          int index = std::clamp (sm_round_positive (d * end), start, end);

          source.set_audio_block (blk, active_audio->contents[index], freq / active_audio->fundamental_freq, v);
        }
      else if (script_parser.command ("label", s))
        {
          source.set_label (s);
        }
      else if (script_parser.command ("morphing", d))
        {
          source.set_morphing (d * 2 - 1);
        }
      else if (script_parser.command ("high-shelf-gain", d))
        {
          hsh_gain_smoother.set_target (d);
        }
      else
        {
          script_parser.die_if_unknown();
        }
    }
  WavData wav_data (output, 1, 48000, 24);
  if (!wav_data.save (argv[2]))
    {
      fprintf (stderr,"export to file %s failed: %s\n", argv[2], wav_data.error_blurb());
      return 1;
    }
  fclose (frames_file);
}
