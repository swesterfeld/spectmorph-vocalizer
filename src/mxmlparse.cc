#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <cassert>
#include <map>
#include <cmath>
#include "pugixml.hpp"

using std::vector;

struct DivToVel
{
  int division;
  int velocity;
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
  int start_divisions;
  int duration_divisions;

  vector<DivToVel> divisions_to_velocity;
  std::string lyric;     // attached lyric (if any)
  bool staccato = false;  // staccato?
  bool accent = false;  // accent?
};

// Map symbolic dynamics to MIDI velocity
int
mapDynamicToVelocity (const std::string& dyn)
{
  if (dyn == "pp") return 30;
  if (dyn == "p")  return 50;
  if (dyn == "mp") return 60;
  if (dyn == "mf") return 80;
  if (dyn == "f")  return 100;
  if (dyn == "ff") return 120;
  return 80; // default
}

int
next_velocity_level (int velocity, int direction)
{
  vector<int> vs = { 30, 50, 60, 80, 100, 120 }; // FIXME: add more levels
  for (size_t i = 0; i < vs.size(); i++)
    if (velocity == vs[i] && i + direction >= 0 && i + direction < vs.size())
      return vs[i + direction];
  return velocity;
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
  int current_time_divisions = 0; // playback position in divisions

  vector<DivToVel> division_to_velocity;
  struct DynWedge
  {
    enum { CRESCENDO, DIMINUENDO } type;
    int start_division = 0;
    int end_division = 0;
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

  std::vector<NoteEvent> events;
  std::map<std::string, NoteEvent> tiedNotes; // active ties keyed by pitch+octave

  bool first_measure = true;
  int  first_rest = 0;

  for (auto measure : doc.select_nodes("//measure"))
    {
      for (auto node : measure.node().children())
        {
          std::string nodeName = node.name();

          if (first_measure && nodeName == "attributes")
            {
              auto time_node = node.child ("time");
              if (time_node)
                {
                  auto beats_node = time_node.child ("beats");
                  auto beat_type = time_node.child ("beat-type");
                  if (beats_node && beat_type)
                    {
                      first_rest = divisions * 4 * atoi (beats_node.child_value()) / atoi (beat_type.child_value());
                    }
                }
            }

          if (nodeName == "sound")
            {
              printf ("TEMPO, position %d, tempo=%f\n", current_time_divisions, atof (node.attribute ("tempo").value()));
            }
          if (nodeName == "note")
            {
              auto noteNode = node;

              // Extract duration in seconds
              int durDivisions = std::stoi(noteNode.child("duration").child_value());

              // Skip rests but advance time
              if (noteNode.child("rest"))
                {
                  auto durNode = noteNode.child("duration");
                  if (durNode)
                    {
                      events.push_back({NoteEvent::REST, -1, current_time_divisions, durDivisions, {}, "", false});
                      current_time_divisions += std::stoi(durNode.child_value());
                    }
                  continue;
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

              // Handle ties
              bool tieStart = false, tieStop = false;
              for (auto tieNode : noteNode.children("tie"))
                {
                  std::string type = tieNode.attribute("type").value();
                  if (type == "start") tieStart = true;
                  if (type == "stop")  tieStop = true;
                }

              // Extract lyric if present
              std::string lyricText;
              auto lyricNode = noteNode.child("lyric");
              if (lyricNode)
                {
                  lyricText = lyricNode.child("text") ? lyricNode.child("text").child_value() : "";
                }
              printf ("note pitch %s, duration %d, lyricText %s\n", pitchKey.c_str(), durDivisions, lyricText.c_str());

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

              // Handle ties
              if (tieStart)
                {
                  if (tiedNotes.find(pitchKey) == tiedNotes.end()) {
                      tiedNotes[pitchKey] = {NoteEvent::NOTE, midi_note, current_time_divisions, durDivisions, {}, lyricText, staccato, accent};
                  } else {
                      tiedNotes[pitchKey].duration_divisions += durDivisions;
                      if (!lyricText.empty()) tiedNotes[pitchKey].lyric = lyricText;
                  }
                }
              else if (tieStop)
                {
                  if (tiedNotes.find(pitchKey) != tiedNotes.end()) {
                      auto e = tiedNotes[pitchKey];
                      e.duration_divisions += durDivisions;
                      if (!lyricText.empty()) e.lyric = lyricText;
                      events.push_back(e);
                      tiedNotes.erase(pitchKey);
                  } else {
                      events.push_back({NoteEvent::NOTE, midi_note, current_time_divisions, durDivisions, {}, lyricText, staccato, accent});
                  }
                }
              else
                {
                  events.push_back({NoteEvent::NOTE, midi_note, current_time_divisions, durDivisions, {}, lyricText, staccato, accent});
                }

              current_time_divisions += durDivisions;
            }
          if (nodeName == "direction")
            {
              for (auto dtype : node.children ("direction-type"))
                {
                  auto dynNode = dtype.child("dynamics");
                  if (dynNode)
                    {
                      printf ("direction dynamics");
                      for (auto d : dynNode.children())
                        {
                          division_to_velocity.push_back ({current_time_divisions, mapDynamicToVelocity(d.name())});
                          printf (" %s", d.name());
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
                          current_dwedge.type = DynWedge::CRESCENDO;
                          current_dwedge.start_division = current_time_divisions;
                        }
                      if (type == "diminuendo")
                        {
                          current_dwedge.type = DynWedge::DIMINUENDO;
                          current_dwedge.start_division = current_time_divisions;
                        }
                      if (type == "stop")
                        {
                          current_dwedge.end_division = current_time_divisions;
                          dynamic_wedges.push_back (current_dwedge);
                        }
                    }
                }
            }
          if (nodeName == "backup")
            {
              printf ("backup %d\n", std::stoi(node.child("duration").child_value()));
              current_time_divisions -= std::stoi(node.child("duration").child_value());
            }
          if (nodeName == "forward")
            {
              printf ("forward %d\n", std::stoi(node.child("duration").child_value()));
              current_time_divisions += std::stoi(node.child("duration").child_value());
            }
        }
      first_measure = false;
    }
  int current_velocity = 80;
  for (auto& wedge : dynamic_wedges)
    {
      int start_velocity = current_velocity, end_velocity = -1;
      for (auto d2v : division_to_velocity)
        {
          if (wedge.start_division >= d2v.division)
            start_velocity = d2v.velocity;
          if (wedge.end_division == d2v.division)
            end_velocity = d2v.velocity;
        }
      if (end_velocity == -1 && wedge.type == DynWedge::CRESCENDO)
        {
          end_velocity = next_velocity_level (start_velocity, 1);
          division_to_velocity.push_back ({ wedge.end_division, end_velocity });
        }
      if (end_velocity == -1 && wedge.type == DynWedge::DIMINUENDO)
        {
          end_velocity = next_velocity_level (start_velocity, -1);
          division_to_velocity.push_back ({ wedge.end_division, end_velocity });
        }
      current_velocity = end_velocity;
      wedge.start_velocity = start_velocity;
      wedge.end_velocity = end_velocity;
      printf ("%d..%d %d->%d\n", wedge.start_division, wedge.end_division, wedge.start_velocity, wedge.end_velocity);
    }
  for (auto d2v : division_to_velocity)
    {
      printf ("division %d -> vel %d\n", d2v.division, d2v.velocity);
    }
  for (auto& event : events)
    {
      printf ("candidate event: %.2f %d..%d - %s\n", event.midi_note, event.start_divisions, event.start_divisions + event.duration_divisions, event.lyric.c_str());
      for (auto d2v : division_to_velocity)
        {
          //printf ("current_time_divisions: %d\n", current_time_divisions);
          if (d2v.division <= event.start_divisions)
            {
              current_velocity = d2v.velocity;
            }
        }
      printf ("current velocity %d\n", current_velocity);
      int start_velocity = current_velocity;
      int end_velocity = -1;
      vector<DynWedge> inside_wedges;
      for (auto wedge : dynamic_wedges)
        {
          int tr_start = wedge.start_division - event.start_divisions;
          int tr_end = wedge.end_division - event.start_divisions;

          if (tr_start < 0 && tr_end > 0)
            {
              double frac = (event.start_divisions - wedge.start_division) / double (wedge.end_division - wedge.start_division);
              start_velocity = wedge.start_velocity * (1 - frac) + wedge.end_velocity * frac;
              if (tr_end < event.duration_divisions)
                {
                  DynWedge partial_wedge = wedge;
                  partial_wedge.start_division = event.start_divisions;
                  partial_wedge.start_velocity = start_velocity;
                  inside_wedges.push_back (partial_wedge);
                }
            }
          if (tr_start >= 0 && tr_end <= event.duration_divisions)
            {
              inside_wedges.push_back (wedge);
            }
          if (tr_start < event.duration_divisions && tr_end >= event.duration_divisions)
            {
              int end_divisions = event.start_divisions + event.duration_divisions;
              double frac = (end_divisions - wedge.start_division) / double (wedge.end_division - wedge.start_division);
              end_velocity = wedge.start_velocity * (1 - frac) + wedge.end_velocity * frac;

              if (inside_wedges.size() && inside_wedges.back().end_division < wedge.start_division)
                {
                  DynWedge partial_wedge = wedge;
                  partial_wedge.end_division = end_divisions;
                  partial_wedge.end_velocity = end_velocity;
                  inside_wedges.push_back (partial_wedge);
                }
            }
        }
      event.divisions_to_velocity.push_back ({0, start_velocity});
      for (auto& wedge : inside_wedges)
        {
          int tr_start = wedge.start_division - event.start_divisions;
          int tr_end = wedge.end_division - event.start_divisions;
          event.divisions_to_velocity.push_back ({ tr_start, wedge.start_velocity });
          event.divisions_to_velocity.push_back ({ tr_end, wedge.end_velocity });
        }
      if (end_velocity == -1)
        end_velocity = event.divisions_to_velocity.back().velocity;

      event.divisions_to_velocity.push_back ({event.duration_divisions, end_velocity});

      event.divisions_to_velocity.erase (
        std::unique (event.divisions_to_velocity.begin(), event.divisions_to_velocity.end(),
          [](const DivToVel& a, const DivToVel& b)
            {
              return a.velocity == b.velocity && a.division == b.division;
            }),
        event.divisions_to_velocity.end());
    }

  for (auto& event : events)
    {
      auto midi_to_factor = [] (float midi) { return (midi / 127) * (midi / 127); };
      auto factor_to_midi = [] (float factor) { return sqrt (factor) * 127; };

      if (event.accent)
        {
          for (auto& d2v : event.divisions_to_velocity)
            d2v.velocity = factor_to_midi (midi_to_factor (d2v.velocity) * 2);
        }
    }

  // Print events
  for (auto& e : events)
    {
      auto div_to_sec = [&] (int div) { return div / static_cast<double>(divisions) * (60.0 / tempo); };

      std::cout << "Note: " << e.midi_note
                << " Start: " << div_to_sec (e.start_divisions) << "s"
                << " Duration: " << div_to_sec (e.duration_divisions) << "s" << "  (";
      for (auto d2v : e.divisions_to_velocity)
        std::cout << "[" << div_to_sec (d2v.division) << "," << d2v.velocity << "] ";
      std::cout
                << ") Lyric: " << e.lyric << "\n";
    }
  if (argc == 3)
    {
      int offset = 0;
      FILE *f = fopen (argv[2], "w");
      assert (f);
      fprintf (f, "TEMPO\n");
      fprintf (f, " divisions: %d\n", divisions);
      fprintf (f, " bpm: %f\n", tempo);
      fprintf (f, "\n");

      fprintf (f, "REST\n");
      fprintf (f, " start: %d\n", 0);
      fprintf (f, " duration: %d\n", first_rest);
      fprintf (f, "\n");

      for (auto& e : events)
        {
          if (e.event_type == NoteEvent::REST)
            {
              // TODO: should we avoid this and insert rests automatically?
              fprintf (f, "REST\n");
              fprintf (f, " start: %d\n", e.start_divisions + first_rest);
              fprintf (f, " duration: %d\n", e.duration_divisions);
              fprintf (f, "\n");
            }
          else
            {
              if (e.start_divisions > offset)
                {
                  fprintf (f, "REST\n");
                  fprintf (f, " start: %d\n", offset + first_rest);
                  fprintf (f, " duration: %d\n", e.start_divisions - offset);
                  fprintf (f, "\n");
                  offset = e.start_divisions;
                }
              fprintf (f, "NOTE\n");
              if (e.lyric != "")
                fprintf (f, " lyric: %s\n", e.lyric.c_str());
              fprintf (f, " midi_note: %.2f\n", e.midi_note);
              fprintf (f, " start: %d\n", e.start_divisions + first_rest);
              fprintf (f, " duration: %d\n", e.duration_divisions);
              fprintf (f, " volume:");
              for (auto d2v : e.divisions_to_velocity)
                {
                  fprintf (f, " (%d, %d)", d2v.division, d2v.velocity);
                }
              fprintf (f, "\n");
              if (e.staccato)
                fprintf (f, " articulation: staccato\n");
              fprintf (f, "\n");
            }
          offset += e.duration_divisions;
        }
    }
  return 0;
}
