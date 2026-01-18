// Licensed GNU LGPL v2.1 or later: http://www.gnu.org/licenses/lgpl-2.1.html

#include "smlivedecoder.hh"
#include "smutils.hh"
#include "smmain.hh"
#include "smaudiotool.hh"
#include "smmicroconf.hh"
#include "smwavdata.hh"
#include "smformantcorrection.hh"

using namespace SpectMorph;

using std::vector;
using std::string;

class ScriptBlockSource : public LiveDecoderSource
{
  Audio             my_audio;
  AudioBlock        my_audio_block;
  FormantCorrection formant_correction;
public:
  ScriptBlockSource (const AudioBlock& block, float mix_freq)
    : my_audio_block (block)
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
    formant_correction.set_mode (FormantCorrection::MODE_HARMONIC_RESYNTHESIS);
    formant_correction.set_max_partials (1000);
    formant_correction.set_fuzzy_resynth (20);
    formant_correction.retrigger();
    my_audio.fundamental_freq = freq;
  }
  void
  advance (double time_ms)
  {
    formant_correction.advance (time_ms);
  }
  Audio *audio()
  {
    return &my_audio;
  }
  bool
  rt_audio_block (size_t index, RTAudioBlock& out_block)
  {
    formant_correction.process_block (my_audio_block, out_block);
    return true;
  }
  void
  set_audio_block (const AudioBlock& in_block, double ratio, double volume_factor)
  {
    formant_correction.set_ratio (ratio);

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
    my_audio_block = block;
  }
  void
  set_portamento_freq (float freq)
  {
    // ignore
  }
};


int
main (int argc, char **argv)
{
  Main main (&argc, &argv);

  if (argc != 3)
    {
      fprintf (stderr, "usage: smscript <plan> <voice_sm> <script> <out_wav>\n");
      return 1;
    }

  MicroConf script_parser (argv[1]);
  if (!script_parser.open_ok())
    {
      fprintf (stderr, "error opening file %s\n", argv[1]);
      exit (1);
    }
  script_parser.set_number_format (MicroConf::NO_I18N);

  AudioBlock audio_block;
  audio_block.noise.resize (32);

  const int mix_freq = 48000;
  const int freq_slide_ms = 20;
  const double vibrato_attack = 0;
  const double vibrato_depth = 15;
  const double vibrato_frequency = 4;

  ScriptBlockSource source (audio_block, mix_freq);
  LiveDecoder live_decoder (&source, mix_freq);
  RTMemoryArea rt_memory_area;

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
      int i;
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
          for (auto &f : freq_in)
            {
              if (freq_steps)
                {
                  freq *= freq_factor;
                  freq_steps--;
                }
              f = freq;
            }
          live_decoder.process (rt_memory_area, i, freq_in.data(), output.data() + offset);

          double time_ms = i / 48000. * 1000;
          source.advance (time_ms);
        }
      else if (script_parser.command ("seek", i, d, f, v))
        {
          assert (i >= 0 && size_t (i) < audio_vector.size());
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

          const auto& active_audio = audio_vector[i];

          int start = 0;
          int end = active_audio->contents.size() - 1;
          int index = std::clamp (sm_round_positive (d * end), start, end);

          source.set_audio_block (active_audio->contents[index], freq / active_audio->fundamental_freq, v);
        }
      else
        {
          script_parser.die_if_unknown();
        }
    }
  WavData wav_data (output, 1, 48000, 24);
  if (!wav_data.save (argv[2]))
    {
      fprintf (stderr,"export to file %s failed: %s\n", argv[4], wav_data.error_blurb());
      return 1;
    }
}
