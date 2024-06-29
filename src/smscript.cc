// Licensed GNU LGPL v2.1 or later: http://www.gnu.org/licenses/lgpl-2.1.html

#include "smmidisynth.hh"
#include "smmain.hh"
#include "smproject.hh"
#include "smsynthinterface.hh"
#include "smmorphwavsource.hh"
#include "smmicroconf.hh"

#include <unistd.h>

using namespace SpectMorph;

using std::vector;

int
main (int argc, char **argv)
{
  Main main (&argc, &argv);
  if (argc != 4)
    {
      fprintf (stderr, "usage: smscript <plan> <script> <out_wav>\n");
      return 1;
    }

  Project project;
  project.set_mix_freq (48000);

  Error error = project.load (argv[1]);
  assert (!error);

  for (MorphOperator *op : project.morph_plan()->operators())
    {
      if (op->type_name() == "WavSource")
        {
          auto wav_source = dynamic_cast<MorphWavSource *> (op);
          while (project.rebuild_active (wav_source->object_id()))
             usleep (10 * 1000);
        }
    }
  project.try_update_synth();

  MidiSynth& midi_synth = *project.midi_synth();

  MicroConf script_parser (argv[2]);
  if (!script_parser.open_ok())
    {
      fprintf (stderr, "error opening file %s\n", argv[2]);
      exit (1);
    }
  script_parser.set_number_format (MicroConf::NO_I18N);
  vector<float> output;
  while (script_parser.next())
    {
      int i, j, ch;
      double d;

      if (script_parser.command ("note_on", ch, i, j))
        {
          unsigned char note_on[3] = { uint8 (0x90 + ch), uint8 (i), uint8 (j) };
          midi_synth.add_midi_event (0, note_on);
        }
      else if (script_parser.command ("note_off", ch, i, j))
        {
          unsigned char note_off[3] = { uint8 (0x80 + ch), uint8 (i), uint8 (j) };
          midi_synth.add_midi_event (0, note_off);
        }
      else if (script_parser.command ("process", i))
        {
          size_t offset = output.size();
          output.resize (output.size() + i);
          midi_synth.process (output.data() + offset, i);
        }
      else if (script_parser.command ("control", i, d))
        {
          midi_synth.set_control_input (i, d);
        }
      else if (script_parser.command ("pitch_expression", ch, i, d))
        {
          midi_synth.add_pitch_expression_event (0, d, ch, i);
        }
      else
        {
          script_parser.die_if_unknown();
        }
    }
  WavData wav_data (output, 1, 48000, 24);
  if (!wav_data.save (argv[3]))
    {
      fprintf (stderr,"export to file %s failed: %s\n", argv[3], wav_data.error_blurb());
      return 1;
    }
}
