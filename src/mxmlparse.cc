#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <cassert>
#include <map>
#include <set>
#include <cmath>
#include <cstdlib>
#include <regex>
#include <cctype>
#include <sstream>
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

enum class TempoChange
{
  NONE,
  RIT,
  ACCEL
};

static TempoChange
parse_tempo_change (string text)
{
  struct Name
  {
    string primary;
    vector<string> abbreviations;
    TempoChange change;
  };
  static const vector<Name> names = {
    {"ritardando", {"rit", "ritard"}, TempoChange::RIT},
    {"rallentando", {"rall"}, TempoChange::RIT},
    {"allargando", {"allarg"}, TempoChange::RIT},
    {"callando", {}, TempoChange::RIT},
    {"lentando", {"lent"}, TempoChange::RIT},
    {"morendo", {}, TempoChange::RIT},
    {"smorzando", {"smorz"}, TempoChange::RIT},
    {"sostenuto", {"sost"}, TempoChange::RIT},
    {"ritenuto", {"riten"}, TempoChange::RIT},
    {"perdendosi", {"perd"}, TempoChange::RIT},
    {"accelerando", {"acc", "accel"}, TempoChange::ACCEL},
    {"precipitando", {}, TempoChange::ACCEL},
    {"stringendo", {"string"}, TempoChange::ACCEL}
  };

  std::istringstream words (text);
  string word;
  while (words >> word)
    {
      std::transform (word.begin(), word.end(), word.begin(),
                      [] (unsigned char c) { return std::tolower (c); });
      if (word.back() == '.')
        word.pop_back();
      for (const auto& name : names)
        if (word == name.primary ||
            std::find (name.abbreviations.begin(), name.abbreviations.end(), word) != name.abbreviations.end())
          return name.change;
    }
  return TempoChange::NONE;
}

// Numeric printed metronome marks use their own beat unit, whereas sound
// tempos are always quarter notes per minute.
static double
metronome_tempo (pugi::xml_node node)
{
  static const std::map<string, double> units = {
    {"maxima", 32}, {"long", 16}, {"breve", 8}, {"whole", 4},
    {"half", 2}, {"quarter", 1}, {"eighth", 0.5},
    {"16th", 0.25}, {"32nd", 0.125}, {"64th", 0.0625},
    {"128th", 0.03125}, {"256th", 0.015625}
  };
  auto unit = units.find (node.child ("beat-unit").child_value());
  const string text = node.child ("per-minute").child_value();
  static const std::regex numeric (R"(^\s*[0-9]+(?:\.[0-9]+)?\s*$)");
  if (unit == units.end() || !std::regex_match (text, numeric))
    return 0; // Ranges and metric modulations have no unambiguous BPM.
  double factor = 1, dot = 0.5;
  for (auto unused : node.children ("beat-unit-dot"))
    {
      (void) unused;
      factor += dot;
      dot *= 0.5;
    }
  return std::stod (text) * unit->second * factor;
}

static void
resolve_tempo_ramps (vector<BeatsToTempo>& tempos,
                     const std::map<Fraction, double>& printed,
                     const std::map<Fraction, TempoChange>& ramps,
                     const std::map<Fraction, Fraction>& dash_ends,
                     const std::set<Fraction>& equivalences,
                     const std::set<Fraction>& tempo_returns)
{
  std::map<Fraction, double> exported;
  for (auto point : tempos)
    exported[point.beats] = point.tempo;
  auto resolved = exported;
  for (auto [beat, bpm] : printed)
    resolved[beat] = bpm;

  for (auto [start, change] : ramps)
    {
      auto target = printed.upper_bound (start);
      // Written tempo changes and later ramp instructions bound the range.
      auto next_ramp = ramps.upper_bound (start);
      auto tempo_return = tempo_returns.upper_bound (start);
      Fraction limit = target != printed.end() ? target->first : resolved.rbegin()->first;
      if (target == printed.end())
        if (auto dash = dash_ends.find (start); dash != dash_ends.end())
          limit = std::max (limit, dash->second);
      if (next_ramp != ramps.end() && next_ramp->first < limit)
        limit = next_ramp->first;
      if (tempo_return != tempo_returns.end())
        limit = std::min (limit > start ? limit : *tempo_return, *tempo_return);
      Fraction end = limit;
      bool range_known = target != printed.end() || tempo_return != tempo_returns.end();
      if (auto dash = dash_ends.find (start); dash != dash_ends.end())
        {
          end = std::min (dash->second, limit);
          range_known = true;
        }
      else
        {
          // Dorico exports a regularly sampled monotonic tempo sequence,
          // including its endpoint. A gap, plateau or reversal ends the run.
          auto point = exported.upper_bound (start);
          if (point != exported.end() && point->first <= limit && point != exported.begin())
            {
              double previous = std::prev (point)->second;
              const Fraction step = point->first - start;
              Fraction last = start;
              for (; point != exported.end() && point->first <= limit; ++point)
                {
                  if (point->first - last != step ||
                      (change == TempoChange::ACCEL ? point->second <= previous : point->second >= previous))
                    break;
                  last = point->first;
                  previous = point->second;
                }
              if (last > start)
                {
                  end = last;
                  range_known = true;
                }
            }
        }
      if (!range_known || end <= start)
        continue;
      auto initial = resolved.upper_bound (start);
      if (initial == resolved.begin())
        continue;
      const double start_tempo = std::prev (initial)->second;
      const auto written_end = printed.find (end);
      double end_tempo = start_tempo * (change == TempoChange::ACCEL ? 1.25 : 0.75);
      if (written_end != printed.end())
        end_tempo = written_end->second;
      else if (target != printed.end() && equivalences.contains (target->first) &&
               (next_ramp == ramps.end() || next_ramp->first >= target->first) &&
               (tempo_return == tempo_returns.end() || *tempo_return > target->first))
        {
          // An equivalence following the final ramp sample supplies the
          // destination tempo, rather than a separate jump after the ramp.
          end_tempo = target->second;
        }
      resolved[start] = start_tempo;
      // Retain the exporter's sampling positions. If it supplied no ramp,
      // generate sixteenth-note steps for the existing fragment pipeline.
      const auto first_sample = resolved.upper_bound (start);
      if (first_sample == resolved.end() || first_sample->first >= end)
        for (Fraction beat = start + Fraction (1, 4); beat < end; beat += Fraction (1, 4))
          resolved[beat] = start_tempo;
      resolved[end] = end_tempo;
      for (auto point = resolved.upper_bound (start); point != resolved.end() && point->first <= end; ++point)
        {
          const double fraction = ((point->first - start) / (end - start)).to_double();
          point->second = start_tempo + fraction * (end_tempo - start_tempo);
        }
      // Exported values after the ramp must not restore its old endpoint.
      Fraction hold_until = target != printed.end() ? target->first : resolved.rbegin()->first;
      if (next_ramp != ramps.end())
        hold_until = std::min (hold_until, next_ramp->first);
      if (tempo_return != tempo_returns.end())
        hold_until = std::min (hold_until, *tempo_return);
      for (auto point = resolved.upper_bound (end); point != resolved.end() && point->first <= hold_until; ++point)
        if (!printed.contains (point->first) && !ramps.contains (point->first) &&
            !tempo_returns.contains (point->first))
          point->second = end_tempo;
      if (tempo_return != tempo_returns.end() &&
          (next_ramp == ramps.end() || *tempo_return <= next_ramp->first) &&
          (target == printed.end() || *tempo_return < target->first))
        {
          // A tempo is a return after the ramp, never its destination BPM.
          auto playback = exported.find (*tempo_return);
          resolved[*tempo_return] = playback != exported.end() ? playback->second : start_tempo;
        }
    }
  tempos.clear();
  for (auto [beat, bpm] : resolved)
    tempos.push_back ({beat, bpm});
}

struct BeatsToMeasure
{
  Fraction beats;
  int      measure;
};

struct BeatsToSfz
{
  Fraction beats;
  bool sffz = false;
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
  bool sffz = false;
  int note_id = -1;       // original MusicXML note, preserved when splitting
  vector<int> glissando_starts;
  vector<int> glissando_stops;
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

  /* Lyrics and glissando endpoints belong to the original note's onset. */
  for (size_t i = 0; i < result.size(); i++)
    if (i)
      {
        result[i].lyric = "";
        result[i].glissando_starts.clear();
        result[i].glissando_stops.clear();
      }

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
  std::map<Fraction, double> printed_tempos;
  std::set<Fraction> tempo_equivalences;
  std::set<Fraction> tempo_returns;
  std::map<Fraction, TempoChange> tempo_ramps;
  std::map<Fraction, Fraction> tempo_dash_ends;
  std::map<int, Fraction> open_tempo_dashes;
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
  std::map<Fraction, double> cents_at_beat;
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

          if (nodeName == "sound" || nodeName == "direction")
            {
              auto sound = nodeName == "sound" ? node : node.child ("sound");
              if (sound.attribute ("tempo"))
                {
                  double bpm = sound.attribute ("tempo").as_double();
                  auto offset_node = sound.child ("offset");
                  if (!offset_node && nodeName == "direction")
                    offset_node = node.child ("offset");
                  Fraction offset (offset_node.text().as_int(), divisions);
                  if (bpm > 0)
                    beats_to_tempo.push_back ({current_time_beats + offset, bpm});
                }
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

              // Skip extension-only entries: an exporter may put the new
              // syllable in a second lyric element. Only one verse is supported.
              std::string lyricText;
              for (auto lyricNode : noteNode.children ("lyric"))
                {
                  lyricText = lyricNode.child ("text").child_value();
                  if (!lyricText.empty ())
                    break;
                }
              printf ("note pitch %s, duration %s, lyricText %s\n", pitchKey.c_str(), duration_beats.to_string().c_str(), lyricText.c_str());

              bool staccato = false;
              bool accent = false;
              vector<int> glissando_starts, glissando_stops;
              for (auto notations_node : noteNode.children ("notations"))
                {
                  auto articulations_node = notations_node.child ("articulations");
                  if (articulations_node)
                    {
                      if (articulations_node.child ("staccato"))
                        staccato = true;
                      if (articulations_node.child ("accent"))
                        accent = true;
                    }
                  for (auto notation : notations_node.children())
                    {
                      const std::string name = notation.name();
                      if (name != "slide" && name != "glissando")
                        continue;
                      const std::string type = notation.attribute ("type").value();
                      const int number = notation.attribute ("number").as_int (1);
                      if (type == "start")
                        glissando_starts.push_back (number);
                      else if (type == "stop")
                        glissando_stops.push_back (number);
                      else
                        die (current_time_beats, "unsupported glissando type: " + type);
                    }
                }

              const int note_id = events.size();
              events.push_back({NoteEvent::NOTE, midi_note, current_time_beats, duration_beats, {}, lyricText, staccato, accent, fermata});
              events.back().note_id = note_id;
              events.back().glissando_starts = glissando_starts;
              events.back().glissando_stops = glissando_stops;

              current_time_beats += duration_beats;
            }
          if (nodeName == "direction")
            {
              Fraction direction_beat = current_time_beats + Fraction (node.child ("offset").text().as_int(), divisions);
              // Associate dash starts with the text in this direction, not
              // with unrelated instructions at the same musical position.
              TempoChange direction_tempo = TempoChange::NONE;
              for (auto dtype : node.children ("direction-type"))
                for (auto words : dtype.children ("words"))
                  if (auto change = parse_tempo_change (words.child_value()); change != TempoChange::NONE)
                    direction_tempo = change;
              if (direction_tempo != TempoChange::NONE)
                tempo_ramps[direction_beat] = direction_tempo;
              for (auto dtype : node.children ("direction-type"))
                {
                  for (auto dash : dtype.children ("dashes"))
                    {
                      const int number = dash.attribute ("number").as_int (1);
                      const string type = dash.attribute ("type").value();
                      if (type == "start")
                        {
                          if (direction_tempo != TempoChange::NONE)
                            open_tempo_dashes[number] = direction_beat;
                          else
                            open_tempo_dashes.erase (number);
                        }
                      else if (type == "stop")
                        {
                          auto start = open_tempo_dashes.find (number);
                          if (start != open_tempo_dashes.end())
                            {
                              tempo_dash_ends[start->second] = direction_beat;
                              open_tempo_dashes.erase (start);
                            }
                        }
                    }
                  auto metronome = dtype.child ("metronome");
                  if (double bpm = metronome_tempo (metronome); bpm > 0)
                    printed_tempos[direction_beat] = bpm;
                  else if (metronome.child ("beat-unit").next_sibling ("beat-unit") ||
                           metronome.child ("metronome-relation"))
                    tempo_equivalences.insert (direction_beat);
                  // System text applies to the note at this position, even
                  // when the exporter writes it after the note using backup.
                  for (auto words : dtype.children ("words"))
                    {
                      static const std::regex cents_pattern (R"(^\s*([+-][0-9]+(?:\.[0-9]+)?)ct\s*$)");
                      std::smatch match;
                      const std::string text = words.child_value();
                      static const std::regex a_tempo_pattern (R"(^\s*a\s+tempo\.?\s*$)", std::regex::icase);
                      if (std::regex_match (text, a_tempo_pattern))
                        tempo_returns.insert (direction_beat);
                      if (std::regex_match (text, match, cents_pattern))
                        {
                          Fraction offset = 0;
                          if (auto offset_node = node.child ("offset"))
                            offset = Fraction (std::stoi (offset_node.child_value()), divisions);
                          const double cents = std::strtod (match[1].str().c_str(), nullptr);
                          if (cents < -2400 || cents > 2400)
                            die (current_time_beats + offset, "cent alteration outside -2400..2400ct range: " + text);
                          cents_at_beat[current_time_beats + offset] = cents;
                        }
                    }
                  auto dynNode = dtype.child("dynamics");
                  if (dynNode)
                    {
                      for (auto d : dynNode.children())
                        {
                          printf ("direction dynamics %s\n", d.name());
                          static std::set<string> sfz_alternatives { "sfz", "sf", "fz", "sffz", "rfz", "fp" };
                          if (sfz_alternatives.contains (d.name()))
                            {
                              beats_to_sfz.push_back ({current_time_beats, string (d.name()) == "sffz"});
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

  // Add cents to the pitch (including MusicXML alter) before splitting notes,
  // so all tempo/dynamics fragments retain the same adjusted frequency.
  for (auto& event : events)
    if (event.event_type == NoteEvent::NOTE)
      {
        auto cents = cents_at_beat.find (event.start_beats);
        if (cents != cents_at_beat.end())
          event.midi_note += cents->second / 100.0;
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
              event.sffz = sfz.sffz;
            }
        }
    }

  // Equivalences (e.g. quarter = half) have no numeric per-minute value.
  // Use their exported playback BPM at the same position. Resolve after
  // parsing so standalone sound elements may appear before or after the mark.
  for (auto point : beats_to_tempo)
    if (tempo_equivalences.contains (point.beats))
      printed_tempos[point.beats] = point.tempo;

  resolve_tempo_ramps (beats_to_tempo, printed_tempos, tempo_ramps, tempo_dash_ends, tempo_equivalences, tempo_returns);
  if (!beats_to_tempo.empty() && beats_to_tempo.front().beats == Fraction (0))
    tempo = beats_to_tempo.front().tempo;

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
              fprintf (f, " note_id: %d\n", e.note_id);
              if (e.lyric != "")
                fprintf (f, " lyric: %s\n", e.lyric.c_str());
              fprintf (f, " midi_note: %.6f\n", e.midi_note);
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
              auto print_glissando = [&] (const char *key, const vector<int>& numbers)
                {
                  if (numbers.empty())
                    return;
                  fprintf (f, " %s:", key);
                  for (int number : numbers)
                    fprintf (f, " %d", number);
                  fprintf (f, "\n");
                };
              print_glissando ("glissando_start", e.glissando_starts);
              print_glissando ("glissando_stop", e.glissando_stops);
              if (e.sffz)
                fprintf (f, " sffz: True\n");
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
