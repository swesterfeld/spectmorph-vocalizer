// Licensed GNU LGPL v2.1 or later: http://www.gnu.org/licenses/lgpl-2.1.html

#include <cstdio>

#include <sys/resource.h>

#include "spectmorph.hh"

using namespace SpectMorph;

using std::vector;

void
print_memory_usage (const std::string& where)
{
  printf ("=== memory usage (%s): ===\n", where.c_str());

  // Get Peak RSS from getrusage
  struct rusage usage;
  if (getrusage (RUSAGE_SELF, &usage) == 0)
    {
      printf (" - Peak RSS: %.2f MB\n", usage.ru_maxrss / 1024.0);
    }
  else
    {
      perror ("getrusage failed");
    }

  // Get Virtual Memory and Current RSS from /proc/self/statm
  FILE *fp = fopen ("/proc/self/statm", "r");
  if (!fp)
    {
      perror ("Failed to open /proc/self/statm");
      return;
    }

  long page_size = sysconf (_SC_PAGESIZE); // Get page size in bytes
  long vm_size, rss;
  if (fscanf (fp, "%ld %ld", &vm_size, &rss) != 2)
    {
      perror("Failed to read memory usage");
      fclose (fp);
      return;
    }
  fclose (fp);

  printf (" - Current RSS: %.2f MB\n", (rss * page_size) / (1024.0 * 1024.0));
  printf (" - Virtual Memory: %.2f MB\n", (vm_size * page_size) / (1024.0 * 1024.0));
}

int
main (int argc, char **argv)
{
  Main main (&argc, &argv);
  if (argc != 5)
    {
      fprintf (stderr, "usage: mkplan <template> <flac> <plan> <volumes>\n");
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

  bool first = true;
  FILE *vol_file = fopen (argv[4], "w");
  if (!vol_file)
    {
      fprintf (stderr, "%s: can't open input file: %s\n", argv[0], argv[4]);
      return 1;
    }
  for (MorphOperator *op : project.morph_plan()->operators())
    {
      if (op->type_name() == "WavSource")
        {
          auto wav_source = dynamic_cast<MorphWavSource *> (op);
          wav_source->on_instrument_updated (wav_source->bank(), wav_source->instrument(), &instrument);
          while (project.rebuild_active (wav_source->object_id()))
             usleep (10 * 1000);
          project.try_update_synth();
          if (first)
            {
              int object_id = wav_source->object_id();
              auto wav_set = project.get_wav_set (object_id);
              for (vector<WavSetWave>::iterator wi = wav_set->waves.begin(); wi != wav_set->waves.end(); wi++)
                {
                  Audio *audio = wi->audio;
                  AudioTool::Block2Energy b2e (48000);

                  if (audio)
                    {
                      for (size_t i = 0; i < audio->contents.size(); i++)
                        {
                          const double energy = b2e.energy (audio->contents[i]);
                          const double target_energy = 0.05;
                          const double relative_volume = sqrt (energy / target_energy);

                          auto str = string_printf ("%f", relative_volume); // avoid i18n
                          fprintf (vol_file, "%s\n", str.c_str());
                        }
                    }
                }
              first = false;
            }
        }
    }
  fclose (vol_file);

  project.save (argv[3]);
  print_memory_usage ("mkplan memory final");
}
