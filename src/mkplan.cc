// Licensed GNU LGPL v2.1 or later: http://www.gnu.org/licenses/lgpl-2.1.html

#include <cstdio>

#include "spectmorph.hh"

using namespace SpectMorph;

int
main (int argc, char **argv)
{
  Main main (&argc, &argv);
  if (argc != 4)
    {
      fprintf (stderr, "usage: smscript <template> <flac> <plan>\n");
      return 1;
    }
  Project project;
  project.set_mix_freq (48000);

  Error error = project.load (argv[1]);
  if (error)
    {
      fprintf (stderr, "%s: can't open input file: %s: %s\n", argv[0], argv[1], error.message());
      return 1;
    }

  WavData wav_data;
  if (!wav_data.load_mono (argv[2]))
    {
      fprintf (stderr, "%s: error loading %s\n", argv[0], argv[1]);
      return 1;
    }

  const double sample_len_ms = wav_data.samples().size() / wav_data.mix_freq() * 1000.0;

  Instrument instrument;
  auto sample = instrument.add_sample (wav_data, argv[2]);
  sample->set_loop (Sample::Loop::FORWARD);
  sample->set_marker (MARKER_LOOP_START, 0);
  sample->set_marker (MARKER_LOOP_END, sample_len_ms);
  sample->set_midi_note (50); /* FIXME */

  auto tune = instrument.auto_tune();
  tune.method = tune.SMOOTH;
  tune.enabled = true;
  tune.partials = 3;
  instrument.set_auto_tune (tune);

  for (MorphOperator *op : project.morph_plan()->operators())
    {
      if (op->type_name() == "WavSource")
        {
          auto wav_source = dynamic_cast<MorphWavSource *> (op);
          wav_source->on_instrument_updated (wav_source->bank(), wav_source->instrument(), &instrument);
        }
    }

  project.save (argv[3]);
}
