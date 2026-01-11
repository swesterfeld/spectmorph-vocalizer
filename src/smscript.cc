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
  set_audio_block (const AudioBlock& block, double ratio)
  {
    formant_correction.set_ratio (ratio);
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
  ScriptBlockSource source (audio_block, mix_freq);
  LiveDecoder live_decoder (&source, mix_freq);
  RTMemoryArea rt_memory_area;

  double freq = 440; // will be overwritten from script
  live_decoder.retrigger (0, freq, 127);

  vector<std::unique_ptr<Audio>> audio_vector;

  vector<float> output;
  while (script_parser.next())
    {
#if 0
      if (script_parser.command ("volume", i, d))
        {
          assert (i >= 0 && i < int (wav_sources.size()));
          if (volume_factor[i] != d)
            {
              wav_sources[i]->set_volume_factor (d);
              volume_factor[i] = d;
              project.try_update_synth();
            }
        }
#endif
      int i;
      string s;
      double d, f;

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
          vector<float> freq_in (i, freq);
          live_decoder.process (rt_memory_area, i, freq_in.data(), output.data() + offset);

          double time_ms = i / 48000. * 1000;
          source.advance (time_ms);
        }
      else if (script_parser.command ("seek", i, d, f))
        {
          assert (i >= 0 && size_t (i) < audio_vector.size());
          freq = f;

          const auto& active_audio = audio_vector[i];

          int start = 0;
          int end = active_audio->contents.size() - 1;
          int index = std::clamp (sm_round_positive (d * end), start, end);

          source.set_audio_block (active_audio->contents[index], freq / active_audio->fundamental_freq);
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
