#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <cassert>
#include <map>
#include <cmath>
#include "pugixml.hpp"
#include "fraction.hh"

using std::vector;
using std::string;

struct BeatsToVel
{
  Fraction beats;
  int      velocity;
};

struct BeatsToTempo
{
  Fraction beats;
  double   tempo;
};

struct BeatsToMeasure
{
  Fraction beats;
  int      measure;
};

struct BeatsToSfz
{
  Fraction beats;
};

enum class SfzState
{
  NONE,
  START,
  CONTINUE
};

// Event representing a note ready for playback
struct NoteEvent
{
  enum EventType
  {
    NOTE,
    REST
  } event_type;

  double midi_note;
  Fraction start_beats;
  Fraction duration_beats;

  vector<BeatsToVel> beats_to_velocity;
  std::string lyric;      // attached lyric (if any)
  bool staccato = false;  // staccato?
  bool accent = false;    // accent?
  bool fermata = false;   // fermata?

  SfzState sfz = SfzState::NONE;
};

struct Dynamic
{
  std::string name;
  int level; // "midi"-like velocity (but allow values > 127)
};

static const std::vector<Dynamic> dynamics = {
  {"pppp", 15},
  {"ppp",  20},
  {"pp",   30},
  {"p",    45},
  {"mp",   60},
  {"mf",   80},
  {"f",    100},
  {"ff",   120},
  {"fff",  140},
  {"ffff", 150} // extended extreme
};

// Map symbolic dynamics to MIDI velocity
int
map_dynamic_to_velocity (const std::string& name)
{
  // levels exist for crescendo/diminuendo on ppp/fff but cannot be used alone
  if (name == "pppp" || name == "ffff")
    return 0;

  for (const auto& d : dynamics)
    if (d.name == name)
      return d.level;

  return 0; // error, unsupported dynamics
}

int
next_velocity_level (int level, int direction)
{
  // TODO: error handling on various cases

  int idx = -1;

  for (int i = 0; i < (int)dynamics.size(); i++)
    if (dynamics[i].level == level)
      idx = i;

  if (idx == -1)
      return level;

  int ni = idx + direction;

  if (ni < 0)
    ni = 0;

  if (ni >= (int)dynamics.size())
    ni = dynamics.size() - 1;

  return dynamics[ni].level;
}

int
step_to_semitone (const std::string& step)
{
  if (step == "C") return 0;
  if (step == "D") return 2;
  if (step == "E") return 4;
  if (step == "F") return 5;
  if (step == "G") return 7;
  if (step == "A") return 9;
  if (step == "B") return 11;
  assert (false); // not reached
  return 0; // fallback
}

double
pitch_to_midi (const std::string& step, int octave, double alter)
{
  int base = step_to_semitone (step);

  // MIDI: C4 = 60 → formula uses octave + 1
  double midi = 12.0 * (octave + 1) + base + alter;

  return midi;
}

std::vector<NoteEvent>
split_note_on_changes (const NoteEvent& note, const auto& split_beats)
{
  std::vector<NoteEvent> result;

  Fraction start = note.start_beats;
  Fraction end   = note.start_beats + note.duration_beats;

  Fraction segment_start = start;

  for (auto s : split_beats)
    {
      Fraction t_beats = s.beats;

      // skip changes before note
      if (t_beats <= start) continue;

      // stop if beyond note
      if (t_beats >= end) break;

      // split point inside note
      NoteEvent part = note;
      part.start_beats = segment_start;
      part.duration_beats = t_beats - segment_start;

      result.push_back (part);

      segment_start = t_beats;
    }

  // final segment
  NoteEvent last = note;
  last.start_beats = segment_start;
  last.duration_beats = end - segment_start;

  result.push_back (last);

  /* remove lyrics on splitted parts to force melisma */
  for (size_t i = 0; i < result.size(); i++)
    if (i)
      result[i].lyric = "";

  /* properly set sfz state */
  auto first_sfz = result[0].sfz;
  for (size_t i = 1; i < result.size(); i++)
    if (first_sfz != SfzState::NONE)
      result[i].sfz = SfzState::CONTINUE;

  return result;
}

void
split_events (vector<NoteEvent>& events, const auto& split_beats)
{
  vector<NoteEvent> split_events;
  for (auto& event : events)
    {
      auto split_notes = split_note_on_changes (event, split_beats);
      split_events.insert (split_events.end(), split_notes.begin(), split_notes.end());
    }
  events = split_events;
}

vector<BeatsToMeasure> beats_to_measure;

std::pair<int, int>
lookup_measure (Fraction time_beats)
{
  // TODO: beats are currently quarter notes, should depend on time signature
  Fraction beat = 0;
  int measure = 0;
  for (auto b2m : beats_to_measure)
    {
      if (b2m.beats <= time_beats)
        {
          measure = b2m.measure;
          beat = time_beats - b2m.beats + 1;
        }
    }
  return std::make_pair (measure, int (floor (beat.to_double())));
}

void
die (Fraction current_time_beats, const string& msg)
{
  auto [ measure, bar ] = lookup_measure (current_time_beats);
  fprintf (stderr, "*** ERROR: %s at measure %d, beat %d\n", msg.c_str(), measure, bar);
  exit (1);
}

int main(int argc, char **argv)
{
  pugi::xml_document doc;
  if (!doc.load_file(argv[1]))
    {
      std::cerr << "Failed to load MusicXML\n";
      return 1;
    }

  double tempo = 120.0;      // default BPM
  int divisions = 1;          // default
  Fraction current_time_beats = 0; // playback position in beats

  vector<BeatsToVel> beats_to_velocity;
  vector<BeatsToSfz> beats_to_sfz;
  vector<BeatsToTempo> beats_to_tempo;
  struct DynWedge
  {
    enum { CRESCENDO, DIMINUENDO } type;
    Fraction start_beats = 0;
    Fraction end_beats = 0;
    int start_velocity = 0;
    int end_velocity = 0;
  };
  vector<DynWedge> dynamic_wedges;
  DynWedge current_dwedge;

  // Parse divisions and tempo (first occurrence)
  auto attributesNode = doc.select_node("//attributes").node();
  if (attributesNode)
    {
      auto divNode = attributesNode.child("divisions");
      if (divNode) divisions = std::stoi(divNode.child_value());
    }

  auto soundNode = doc.select_node("//sound[@tempo]").node();
  if (soundNode) tempo = std::stod(soundNode.attribute("tempo").value());
  beats_to_tempo.push_back ({0, tempo});

  std::vector<NoteEvent> events;
  std::map<std::string, NoteEvent> tiedNotes; // active ties keyed by pitch+octave

  bool first_measure = true;
  Fraction first_rest = 0;

  for (auto measure : doc.select_nodes("//measure"))
    {
      int bar = std::stoi (measure.node().attribute ("number").value());
      beats_to_measure.push_back ({ current_time_beats, bar });

      for (auto node : measure.node().children())
        {
          std::string nodeName = node.name();

          if (nodeName == "attributes")
            {
              if (first_measure)
                {
                  auto time_node = node.child ("time");
                  if (time_node)
                    {
                      auto beats_node = time_node.child ("beats");
                      auto beat_type = time_node.child ("beat-type");
                      if (beats_node && beat_type)
                        {
                          first_rest = Fraction (4 * atoi (beats_node.child_value()), atoi (beat_type.child_value()));
                        }
                    }
                }
              auto divisions_node = node.child ("divisions");
              if (divisions_node)
                divisions = atoi (divisions_node.child_value());
            }

          if (nodeName == "sound")
            {
              double tempo = atof (node.attribute ("tempo").value());
              Fraction offset = 0;
              if (auto offset_node = node.child ("offset"))
                offset = atoi (offset_node.child_value());
              offset *= Fraction (1, divisions);
              printf ("TEMPO, position %s, tempo=%f\n", (current_time_beats + offset).to_string().c_str(), atof (node.attribute ("tempo").value()));
              beats_to_tempo.push_back ({current_time_beats + offset, tempo});
            }
          if (nodeName == "note")
            {
              auto noteNode = node;

              // Extract duration in seconds
              Fraction duration_beats = std::stoi (noteNode.child("duration").child_value());
              duration_beats *= Fraction (1, divisions);

              bool fermata = noteNode.child ("notations").child ("fermata");

              // Skip rests but advance time
              if (noteNode.child("rest"))
                {
                  auto durNode = noteNode.child ("duration");
                  if (durNode)
                    {
                      events.push_back({NoteEvent::REST, -1, current_time_beats, duration_beats, {}, "", false, false, fermata});
                      current_time_beats += duration_beats;
                    }
                  continue;
                }

              if (noteNode.child ("chord"))
                {
                  fprintf (stderr, "chord unsupported, bar %d\n", bar);
                  exit (1);
                }

              // Extract pitch
              std::string step = noteNode.child("pitch").child("step").child_value();
              int octave = std::stoi(noteNode.child("pitch").child("octave").child_value());
              double alter = 0;
              auto alter_node = noteNode.child ("pitch").child("alter");
              if (alter_node)
                alter = atof (alter_node.child_value());
              std::string pitchKey = step + std::to_string(octave);
              double midi_note = pitch_to_midi (step, octave, alter);

              // Extract lyric if present
              std::string lyricText;
              auto lyricNode = noteNode.child("lyric");
              if (lyricNode)
                {
                  lyricText = lyricNode.child("text") ? lyricNode.child("text").child_value() : "";
                }
              printf ("note pitch %s, duration %s, lyricText %s\n", pitchKey.c_str(), duration_beats.to_string().c_str(), lyricText.c_str());

              bool staccato = false;
              bool accent = false;
              auto notations_node = noteNode.child ("notations");
              if (notations_node)
                {
                  auto articulations_node = notations_node.child ("articulations");
                  if (articulations_node)
                    {
                      if (articulations_node.child ("staccato"))
                        staccato = true;
                      if (articulations_node.child ("accent"))
                        accent = true;
                    }
                  auto slide_node = notations_node.child ("slide");
                  if (slide_node)
                    {
                      std::string type = slide_node.attribute("type").value();
                      printf ("slide type %s (glissando)\n", type.c_str()); // TODO
                    }
                }

              events.push_back({NoteEvent::NOTE, midi_note, current_time_beats, duration_beats, {}, lyricText, staccato, accent, fermata});

              current_time_beats += duration_beats;
            }
          if (nodeName == "direction")
            {
              for (auto dtype : node.children ("direction-type"))
                {
                  auto dynNode = dtype.child("dynamics");
                  if (dynNode)
                    {
                      for (auto d : dynNode.children())
                        {
                          printf ("direction dynamics %s\n", d.name());
                          if (string (d.name()) == "sfz")
                            {
                              beats_to_sfz.push_back ({current_time_beats});
                            }
                          else
                            {
                              int velocity = map_dynamic_to_velocity(d.name());
                              if (!velocity)
                                die (current_time_beats, string ("unsupported dynamics ") + d.name());

                              beats_to_velocity.push_back ({current_time_beats, velocity});
                            }
                        }
                      printf ("\n");
                    }
                  auto wedge = dtype.child("wedge");
                  if (wedge)
                    {
                      std::string type = wedge.attribute("type").value();
                      printf ("wedge type %s\n", type.c_str());
                      if (type == "crescendo")
                        {
                          current_dwedge = {};
                          current_dwedge.type = DynWedge::CRESCENDO;
                          current_dwedge.start_beats = current_time_beats;
                        }
                      if (type == "diminuendo")
                        {
                          current_dwedge = {};
                          current_dwedge.type = DynWedge::DIMINUENDO;
                          current_dwedge.start_beats = current_time_beats;
                        }
                      if (type == "stop")
                        {
                          current_dwedge.end_beats = current_time_beats;
                          dynamic_wedges.push_back (current_dwedge);
                        }
                    }
                }
            }
          if (nodeName == "backup")
            {
              Fraction time (std::stoi(node.child("duration").child_value()), divisions);
              printf ("backup %s\n", time.to_string().c_str());
              current_time_beats -= time;
            }
          if (nodeName == "forward")
            {
              Fraction time (std::stoi(node.child("duration").child_value()), divisions);
              printf ("forward %s\n", time.to_string().c_str());
              current_time_beats += time;
            }
        }
      first_measure = false;
    }

  // split notes on sfz (TODO: do we need this at all?)
  split_events (events, beats_to_sfz);

  for (auto& event: events)
    {
      for (auto& sfz: beats_to_sfz)
        {
          if (event.start_beats == sfz.beats)
            {
              event.sfz = SfzState::START;
            }
        }
    }

  // split notes on tempo changes (in order to have divisions map properly to ms later)
  split_events (events, beats_to_tempo);

  // split notes on volume changes (in order to get beat-aligned volume jumps later)
  split_events (events, beats_to_velocity);

  // loop over crescendo / diminuendo, resolve start and end velocity
  int current_velocity = 80;
  for (auto& wedge : dynamic_wedges)
    {
      int start_velocity = current_velocity, end_velocity = -1;

      auto resort_beats_to_velocity = [&] ()
        {
          std::sort (beats_to_velocity.begin(), beats_to_velocity.end(),
                     [](const BeatsToVel& a, const BeatsToVel& b)
                       {
                         return a.beats < b.beats;
                       });
        };
      for (auto b2v : beats_to_velocity)
        {
          if (wedge.start_beats >= b2v.beats)
            start_velocity = b2v.velocity;
          if (wedge.end_beats == b2v.beats)
            end_velocity = b2v.velocity;
        }
      if (end_velocity == -1 && wedge.type == DynWedge::CRESCENDO)
        {
          end_velocity = next_velocity_level (start_velocity, 1);
          beats_to_velocity.push_back ({ wedge.end_beats, end_velocity });
          resort_beats_to_velocity();
        }
      if (end_velocity == -1 && wedge.type == DynWedge::DIMINUENDO)
        {
          end_velocity = next_velocity_level (start_velocity, -1);
          beats_to_velocity.push_back ({ wedge.end_beats, end_velocity });
          resort_beats_to_velocity();
        }
      current_velocity = end_velocity;
      wedge.start_velocity = start_velocity;
      wedge.end_velocity = end_velocity;
      printf ("%s..%s %d->%d\n", wedge.start_beats.to_string().c_str(), wedge.end_beats.to_string().c_str(), wedge.start_velocity, wedge.end_velocity);
    }
  for (auto b2v : beats_to_velocity)
    {
      printf ("beats %s -> vel %d\n", b2v.beats.to_string().c_str(), b2v.velocity);
    }

  // apply crescendo / diminuendo to notes
  for (auto& event : events)
    {
      printf ("candidate event: %.2f %s..%s - %s\n", event.midi_note, event.start_beats.to_string().c_str(), (event.start_beats + event.duration_beats).to_string().c_str(), event.lyric.c_str());
      for (auto b2v : beats_to_velocity)
        {
          //printf ("current_time_beats: %d\n", current_time_beats);
          if (b2v.beats <= event.start_beats)
            {
              current_velocity = b2v.velocity;
            }
        }
      printf ("current velocity %d\n", current_velocity);
      int start_velocity = current_velocity;
      int end_velocity = -1;
      vector<DynWedge> inside_wedges;
      for (auto wedge : dynamic_wedges)
        {
          Fraction tr_start = wedge.start_beats - event.start_beats;
          Fraction tr_end = wedge.end_beats - event.start_beats;

          if (tr_start < 0 && tr_end > 0)
            {
              double frac = ((event.start_beats - wedge.start_beats) / (wedge.end_beats - wedge.start_beats)).to_double();
              start_velocity = wedge.start_velocity * (1 - frac) + wedge.end_velocity * frac;
              if (tr_end < event.duration_beats)
                {
                  DynWedge partial_wedge = wedge;
                  partial_wedge.start_beats = event.start_beats;
                  partial_wedge.start_velocity = start_velocity;
                  inside_wedges.push_back (partial_wedge);
                }
            }
          if (tr_start >= 0 && tr_end <= event.duration_beats)
            {
              inside_wedges.push_back (wedge);
            }
          if (tr_start < event.duration_beats && tr_end >= event.duration_beats)
            {
              Fraction end_beats = event.start_beats + event.duration_beats;
              double frac = ((end_beats - wedge.start_beats) / (wedge.end_beats - wedge.start_beats)).to_double();
              end_velocity = wedge.start_velocity * (1 - frac) + wedge.end_velocity * frac;

              if (inside_wedges.size() && inside_wedges.back().end_beats < wedge.start_beats)
                {
                  DynWedge partial_wedge = wedge;
                  partial_wedge.end_beats = end_beats;
                  partial_wedge.end_velocity = end_velocity;
                  inside_wedges.push_back (partial_wedge);
                }
            }
        }
      event.beats_to_velocity.push_back ({0, start_velocity});
      for (auto& wedge : inside_wedges)
        {
          Fraction tr_start = wedge.start_beats - event.start_beats;
          Fraction tr_end = wedge.end_beats - event.start_beats;
          event.beats_to_velocity.push_back ({ tr_start, wedge.start_velocity });
          event.beats_to_velocity.push_back ({ tr_end, wedge.end_velocity });
        }
      if (end_velocity == -1)
        end_velocity = event.beats_to_velocity.back().velocity;

      event.beats_to_velocity.push_back ({event.duration_beats, end_velocity});

      event.beats_to_velocity.erase (
        std::unique (event.beats_to_velocity.begin(), event.beats_to_velocity.end(),
          [](const BeatsToVel& a, const BeatsToVel& b)
            {
              return a.velocity == b.velocity && a.beats == b.beats;
            }),
        event.beats_to_velocity.end());
    }

  if (argc == 3)
    {
      Fraction offset = 0;
      FILE *f = fopen (argv[2], "w");
      assert (f);
      fprintf (f, "TEMPO\n");
      fprintf (f, " bpm: %f\n", tempo);
      fprintf (f, "\n");

      fprintf (f, "REST\n");
      fprintf (f, " start: %d\n", 0);
      fprintf (f, " duration: %s\n", first_rest.to_decimal_string().c_str());
      fprintf (f, "\n");

      auto print_tempo_change_at = [&] (Fraction pos)
        {
          for (auto d2t : beats_to_tempo)
            {
              if (d2t.beats == pos)
                {
                  fprintf (f, "TEMPO\n");
                  fprintf (f, " bpm: %f\n", d2t.tempo);
                  fprintf (f, "\n");
                }
            }
        };

      for (auto& e : events)
        {
          if (e.event_type == NoteEvent::REST)
            {
              print_tempo_change_at (e.start_beats);

              // TODO: should we avoid this and insert rests automatically?
              fprintf (f, "REST\n");
              fprintf (f, " start: %s\n", (e.start_beats + first_rest).to_decimal_string().c_str());
              fprintf (f, " duration: %s\n", e.duration_beats.to_decimal_string().c_str());
              if (e.fermata)
                fprintf (f, " fermata: True\n");
              fprintf (f, "\n");
            }
          else
            {
              if (e.start_beats > offset)
                {
                  print_tempo_change_at (offset);

                  // TODO: could cause problems if a tempo change is inside this rest
                  fprintf (f, "REST\n");
                  fprintf (f, " start: %s\n", (offset + first_rest).to_decimal_string().c_str());
                  fprintf (f, " duration: %s\n", (e.start_beats - offset).to_decimal_string().c_str());
                  fprintf (f, "\n");
                  offset = e.start_beats;
                }
              print_tempo_change_at (e.start_beats);
              auto [ measure, beat ] = lookup_measure (e.start_beats);
              fprintf (f, "NOTE\n");
              if (e.lyric != "")
                fprintf (f, " lyric: %s\n", e.lyric.c_str());
              fprintf (f, " midi_note: %.2f\n", e.midi_note);
              fprintf (f, " start: %s\n", (e.start_beats + first_rest).to_decimal_string().c_str());
              fprintf (f, " duration: %s\n", e.duration_beats.to_decimal_string().c_str());
              fprintf (f, " measure: %d\n", measure);
              fprintf (f, " beat: %d\n", beat);
              fprintf (f, " volume:");
              for (auto b2v : e.beats_to_velocity)
                {
                  fprintf (f, " (%s, %d)", b2v.beats.to_decimal_string().c_str(), b2v.velocity);
                }
              fprintf (f, "\n");
              if (e.staccato)
                fprintf (f, " staccato: True\n");
              if (e.fermata)
                fprintf (f, " fermata: True\n");
              if (e.accent)
                fprintf (f, " accent: True\n");
              switch (e.sfz)
              {
                case SfzState::NONE:     fprintf (f, " sfz: None\n");
                                         break;
                case SfzState::START:    fprintf (f, " sfz: Start\n");
                                         break;
                case SfzState::CONTINUE: fprintf (f, " sfz: Continue\n");
                                         break;
              }

              fprintf (f, "\n");
            }
          offset += e.duration_beats;
        }
    }
  return 0;
}
