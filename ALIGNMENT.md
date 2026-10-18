# Forced Alignment gesungener SAMPA-Items

`singing_align.py` ist ein **experimenteller Prototyp** für isoliert gesungene
Items. Er erzeugt Audacity-Punktlabels für Phoneme und Intervalllabels für Items. Die Qualität
auf echtem Gesang ist noch nicht gemessen; vor einer neun Stunden langen Aufnahme
zunächst etwa 5–20 repräsentative Items mit überprüfter Transkription verwenden.

## Installation

Python ab 3.10, empfohlen in einer separaten Umgebung mit passender PyTorch-Version:

```sh
python3 -m venv .venv-align
.venv-align/bin/python -m pip install --no-cache-dir 'torch>=2.6' --index-url https://download.pytorch.org/whl/cpu
.venv-align/bin/python -m pip install --no-cache-dir -r requirements-align.txt
```

Diese Reihenfolge installiert zunächst die CPU-Version von PyTorch, damit beim
anschließenden Installieren der Requirements keine großen CUDA-Pakete benötigt
werden. Für NVIDIA-Hardware stattdessen die passende Installation von
[PyTorch](https://pytorch.org/get-started/locally/) verwenden.

Bei `Quota überschritten` kann die persönliche Speicherquote erschöpft sein,
obwohl `df -h` noch freien Platz zeigt. Mit `python -m pip cache info` den
Downloadcache prüfen; `python -m pip cache purge` entfernt dessen erneut
herunterladbare Dateien, keine installierten Pakete. `--no-cache-dir` verhindert
weitere Cachekopien, ersetzt aber nicht den Platz für installierte Pakete und
das später heruntergeladene Akustikmodell.

Der erste Alignment-Lauf lädt das große vortrainierte Modell
[facebook/wav2vec2-xlsr-53-espeak-cv-ft](https://huggingface.co/facebook/wav2vec2-xlsr-53-espeak-cv-ft)
herunter und benötigt Internetzugang. Danach werden die Audiodaten lokal
verarbeitet. Das Modell wurde auf Sprache trainiert; seine Eignung für die
jeweilige Gesangsstimme muss geprüft werden. Für reine Pausenerkennung genügen
`numpy`, `scipy` und `soundfile`, ohne PyTorch oder Modelldownload.

## Transkription

UTF-8, ein Item pro Zeile, **Phoneme durch Leerzeichen getrennt**. Entweder nur
Phoneme, `Name<TAB>Phoneme` oder das im Projekt vorhandene Format `Name: Phoneme`:

```text
# Beispiel, tatsächliche Aussprache prüfen!
Wadenkrampf: v a d n= k r a m pf
Lippenstift: l I p m= S t I f t
```

Die Reihenfolge muss exakt der Aufnahme entsprechen. Wiederholte Namen sind
erlaubt. Kommentare beginnen mit `#`. Keine Überschriften oder Aufnahmehinweise
in die Liste übernehmen. Kompakte SAMPA-Zeichenfolgen werden nicht automatisch
zerlegt, Betonungs- und Silbentrennzeichen nicht automatisch entfernt.

Silbische Konsonanten explizit als `m=`, `n=`, `N=`, `l=`, `r=` usw. markieren.
Auch projekttypische Formen wie `m_m` werden als silbisch interpretiert. Ein
unmarkiertes `n` oder `m` hat die kurze Konsonanten-Solldauer. **Die vorhandenen
Projektlisten kennzeichnen Silbizität teilweise nicht; sie müssen dafür ergänzt
werden.** Nicht pauschal alle Vorkommen von `n` in einer globalen Mappingdatei
als silbisch erklären.

Vokale und Diphthonge gelten als Silbenkerne, unabhängig von einem phonologischen
Längenzeichen `:`. Unterstützt sind die gängigen deutschen SAMPA-Zeichen sowie
`ts`, `tS`, `dZ`, `pf`, `aI`/`a_I`, `aU`/`a_U`, `OY`/`O_Y`, unreleased stops
wie `t_}`. Nicht unterstützte Symbole führen zu einer Fehlermeldung.

Besondere Konventionen lassen sich mit `--mapping mapping.json` ergänzen:

```json
{
  "R": {"ipa": ["ʁ", "r"], "nucleus": false},
  "N=": {"ipa": ["ŋ"], "nucleus": true}
}
```

Die IPA-Liste enthält **alternative Modelltoken für dasselbe Phonem**, keine
aufeinanderfolgende Lautfolge. Mindestens eines muss im Modellvokabular stehen.
Standardmäßig gilt `r` als alveolares `r`, `R` als `ʁ`; bei abweichender Aussprache
anpassen. Längenvarianten von Vokalen werden akustisch gemeinsam zugelassen.
Silbische Konsonanten dürfen auch auf das unsilbische akustische Token zurückfallen,
behalten aber die lange Solldauer. Für `Y` wird mangels passendem Modelltoken
auch `y` als akustische Näherung zugelassen.

## Labelphasen

Zwischen je zwei Items wird `_` ausgegeben: in `*.phones.txt` als Punktmarkierung
am Beginn der Lücke, in `*.items.txt` als Intervall über die gesamte Lücke.
Bei direkt aneinandergrenzenden Items entsteht auch dort eine Punktmarkierung
`_`, ohne erfundene Pausendauer. Stille vor dem
ersten und nach dem letzten Item wird nicht zusätzlich markiert. Beim Einlesen
einer Itemspur mit `--segments` werden `_`-Zeilen übersprungen.

Plosive `p b t d k g ?` werden in Verschluss und Lösung zerlegt, beispielsweise
`.t`, `t` oder `.d`, `d`. Auch für einen ausdrücklich ungelösten Plosiv wie
`p_}` werden gemäß Labelkonvention **beide** Markierungen `.p` und `p_}` ausgegeben.
Die zweite Markierung ist dann eine geschätzte Phasengrenze, kein Nachweis eines
hörbaren Bursts; ein Energieanstieg wird dafür nicht vorausgesetzt. Affrikaten (`ts`, `tS`, `dZ`, `pf`) bleiben eigene
Phoneme; falls getrennte Plosiv- und Frikativlabels gewünscht sind, die
Transkription entsprechend als `t s`, `p f` usw. schreiben.

Diphthonge erhalten drei aufeinanderfolgende Phasen mit je einer Punktmarkierung am Anfang:

| Transkription | Silbischer Teil | Übergang | Unsilbischer Teil |
| --- | --- | --- | --- |
| `a_U` oder `aU` | `a` | `aU` | `U` |
| `a_I` oder `aI` | `a` | `aI` | `I` |
| `O_Y` oder `OY` | `O` | `OY` | `Y` |
| `e_6` | `e` | `e6` | `6` |

Auch andere Paare unterschiedlicher unterstützter Vokale werden so behandelt.
Die Eingabe weiterhin als **ein** Diphthongtoken schreiben, nicht als drei
Tokens. Die drei Phasen werden separat ausgerichtet, nicht nachträglich in
feste Zeitanteile aufgeteilt. Der erste Teil erhält die lange Kernsolldauer,
Übergang und unsilbischer Teil jeweils eine kurze Solldauer.

## Zuerst die Itemgrenzen prüfen

```sh
.venv-align/bin/python singing_align.py test.wav test.txt \
  --segments-only --output-prefix ergebnis/test
```

`ergebnis/test.candidates.txt` enthält nummerierte Intervalle. Die Schwelle beträgt
standardmäßig −45 dBFS, die Mindestpause 0,5 Sekunden. Je nach Hintergrundgeräusch,
Atemgeräuschen und leisen Konsonanten anpassen, zum Beispiel:

```sh
.venv-align/bin/python singing_align.py test.wav test.txt \
  --segments-only --threshold-db -50 --min-pause 0.8 \
  --output-prefix ergebnis/test
```

In Audacity die Audioaufnahme öffnen und die Textdatei als Labels importieren.
Intervalle prüfen, gegebenenfalls zusammenfassen oder teilen und unter einem
anderen Dateinamen exportieren, z. B. `gepruefte-items.txt`. Die Namen dieser Labels
sind für das Programm unerheblich; die zeitliche Reihenfolge zählt. Intervalle
dürfen sich nicht überlappen und sollten eng um das jeweilige Item liegen.

Bei unterschiedlicher Anzahl von Intervallen und Transkriptionszeilen stoppt das
Programm mit Fehlerstatus, schreibt aber die Kandidaten zum Korrigieren. **Gleiche
Anzahl beweist keine korrekte Zuordnung**: Ein zusätzliches Atemgeräusch und ein
übersehenes Item können einander ausgleichen. Gerade beim ersten Test manuell prüfen.

## Phoneme ausrichten

```sh
.venv-align/bin/python singing_align.py test.wav test.txt \
  --segments gepruefte-items.txt --output-prefix ergebnis/test
```

Ohne `--segments` wird die automatische Pausenerkennung genutzt. Optionen:

- `--nucleus-seconds 1.0`: Solldauer von Vokalen und silbischen Konsonanten.
- `--consonant-seconds 0.1`: Solldauer jedes übrigen Phonems, auch Affrikaten.
- `--closure-fraction 0.6`: Anteil der Verschlussphase an der Plosiv-Solldauer;
  standardmäßig 60 ms Verschluss und 40 ms Lösung, zusammen 100 ms.
- `--transition-seconds 0.1`: Solldauer des Diphthongübergangs.
- `--tail-seconds 0.1`: Solldauer des unsilbischen Diphthongteils. Ein Diphthong
  hat damit standardmäßig insgesamt 1,2 s Solldauer (1 s + 0,1 s + 0,1 s).
- `--duration-weight 3`: Gewicht der Dauervorgaben gegenüber akustischen Scores.
- `--device cuda`: GPU, falls die PyTorch-Installation CUDA unterstützt.
- `--max-item-seconds 30`: Schutz vor versehentlich zu großen Modellsegmenten;
  bei tatsächlich längeren Items bewusst erhöhen (höherer Speicherbedarf).

Ergebnisse:

- `*.phones.txt`: Punktlabels im Format `Startsekunde<TAB>Startsekunde<TAB>SAMPA`.
  Identische Start- und Endzeiten ergeben in Audacity Markierungen ohne Ausdehnung;
  das gilt auch für `_`, Verschlüsse und Diphthongphasen. Die berechneten
  Phasenintervalle bleiben intern und im JSON-Bericht erhalten.
- `*.items.txt`: Itemintervalle mit Namen aus der Transkriptionsliste.
- `*.report.json`: Parameter und Phonemdauern; `duration_warning` markiert Dauern
  außerhalb von 50–200 % der jeweiligen Phasen-Solldauer. `source_phone` und
  `phase` zeigen die ursprüngliche Transkription und Phasenart, `silences` die
  Zwischenräume. Die Warnung ist **kein Konfidenzwert**.

Das Textformat entspricht dem
[Audacity-Label-Format](https://manual.audacityteam.org/man/importing_and_exporting_labels.html).
Die Zeiten beziehen sich auf die übergebene Audiodatei; ein separat exportierter
Testausschnitt beginnt bei null. Ausgabedateien mit gleichem Präfix werden ersetzt.
Nach einem fehlgeschlagenen Lauf können Dateien eines früheren Laufs noch vorhanden
sein; Fehlerstatus beachten und für Versuche unterschiedliche Präfixe verwenden.

## Verfahren und Grenzen

Die Pausenerkennung liest Audio blockweise und speichert nur 10-ms-Energiepegel.
Das akustische Modell erhält jeweils ein Item, auf 16 kHz resampelt. Bei mehreren
Kanälen verwendet die Pausenerkennung den jeweils stärksten, das Modell den über
das Item energiereichsten Kanal; Sprach- und Begleitkanal gegebenenfalls vorher
separieren. Gedacht ist das Verfahren für eine einzelne, unbegleitete Stimme.

Ein Semi-Markov-Viterbi-Algorithmus sucht die beste zeitliche Aufteilung entlang
der **vorgegebenen** Phonemfolge. Er kombiniert akustische Scores mit weichen
Dauerprioren (Standard: 1 s / 0,1 s). Harte Grenzen sind 0,15–3 Solldauern für
Silbenkerne und 10 ms bis 6 Solldauern für Konsonanten, gerundet auf Modellframes.
Die Dauern werden nicht einfach proportional auf das Item verteilt.

Die Ausgabe des Sprachmodells ist CTC-basiert. CTC-Blank bedeutet kein neues
Token und ist nicht gleich Stille. Dieser Prototyp erlaubt Blank-Scores innerhalb
jedes Phonems; in akustisch uninformierten Abschnitten entscheiden daher wesentlich
die Dauervorgaben. Das ist eine experimentelle Score-Konstruktion, kein exakt
normalisierter CTC-Decoder. Sie garantiert keine zuverlässigen Lautgrenzen.

Das Modell besitzt keine getrennten Verschluss-/Plosionstoken. Für Verschlüsse
wird deshalb ein relativer Energieabfall ausgewertet, für Lösungen der
Phonemscore mit höherer Energie kombiniert. Dies ist kein trainierter
Burst-Detektor: stimmhafte Verschlüsse und schwache Lösungen können ungenau sein.
Am Itemanfang ist der Beginn eines stimmlosen Verschlusses häufig nicht von
der vorangehenden Pause unterscheidbar; die automatische Randzugabe beträgt nur
40 ms. Itemgrenzen bei Bedarf manuell erweitern. Die Markierung `.t` usw. ist
somit zunächst eine zu prüfende Schätzung.

Für Diphthongphasen dienen Einzelvokal- und Diphthongtoken als akustische
Näherungen. Fehlt ein eigenes Diphthongtoken, verwendet der Übergang alternativ
die beiden Vokalklassen. Auch hier können die Dauervorgaben dominieren;
Übergangsgrenzen müssen an der Aufnahme kontrolliert werden.

Pausen innerhalb eines Items, falsch gesungene oder fehlende Phoneme und lange
Atemgeräusche benötigen Kontrolle. Die ersten und letzten Phoneme übernehmen auch
die kleine Randzugabe der Itemsegmente. Benachbarte gleiche Phoneme haben eventuell
keine akustisch erkennbare Grenze. Die Frameauflösung liegt ungefähr bei 20 ms;
sechs Nachkommastellen im Export bedeuten keine Mikrosekundengenauigkeit.

Die neun Stunden werden nicht gleichzeitig ins Modell geladen. Laufzeit und
Ausrichtungsqualität sind aber erst nach dem Test abschätzbar. Für den Vergleich
mehrere manuell markierte Items verwenden und Grenzabweichungen insbesondere bei
Vokaleinsätzen, silbischen Konsonanten und Verschlusslauten prüfen.

## Tests

```sh
python3 -B -m unittest discover -s tests -p test_singing_align.py -v
```

Die synthetischen Tests prüfen Parser, Silbizität, variable Pausen, akustisch
bestimmte Grenzen, Dauerprioren, ungültige Intervalle und Audacity-Ausgabe. Sie
ersetzen keine Prüfung mit echter Gesangsaufnahme und geladenem Akustikmodell.
