# Testlauf 2: Befunde

Auswertung der Testspiele vom 18.09. (Export
`testdata/evaluation/_exports/export_20260918-081501`, Report in
`testdata/evaluation/_report_prod/accuracy-081501.md`) und der dabei
untersuchten Frage, ob die Kalibrierung über die Zeit schlechter geworden ist.
Fortsetzung von [testrun1.md](testrun1.md); das Messinstrument selbst steht in
[auswertung.md](../feature/auswertung.md).

---

## Datengrundlage

- 4 Spiele (501, double out), alle beendet, 28 Minuten am Stück
  (07:39 – 08:07 UTC). 70 Visits, 190 geworfene Pfeile, 263 Bilder, 69 leer
  zurückgekommene Detektionen.
- Kopfzahl: **167 / 190 korrekt (87.9 %)**, 68.6 % der Visits ohne Korrektur.
- Neues Stativ, Kamera näher am Board: **1.46 – 1.56 px/mm** im Median gegen
  1.3 – 1.4 in den steilen Setups aus Testlauf 1.
- Erster Lauf mit vollständigen Serien: alle 70 Visits haben ein
  `throwN_frames.txt`, der Checkout-Visit fehlt nicht mehr
  ([testrun1 §8a](testrun1.md#8-testserien-vollständig-und-treu-schreiben), `f0f9542`).
  Von 193 Dart-Frames sind 188 `booked` und 5 `absorbed`; `unbooked` kommt
  nicht vor.

### Der Sprung kommt nicht aus dem Code

Zwischen den beiden Läufen hat sich an der Bildverarbeitung **nichts** geändert:

```
git log --since=2026-09-15 -- backend/src/app/api/features/detection/   → 1 Commit (Rematch-Rollen)
git log --since=2026-09-15 -- backend/src/app/api/features/calibration/ → keiner
```

Die Commits seit Testlauf 1 betreffen Rematch, Dart-Entfernen, Socket-Reconnect
und die Aufzeichnung — keinen der Schritte 1–7 aus testrun1. Die 77.1 % → 87.9 %
sind also vollständig dem Aufnahme-Setup zuzuschreiben, nicht einer Verbesserung
am Algorithmus. Erschwerend kommt hinzu, dass dieser Lauf die Checkout-Visits
erstmals mitzählt, also gerade die Doppel-Würfe, die vorher fehlten.

| | Testlauf 1 | Testlauf 2 |
|---|---|---|
| Spiele / Pfeile | 15 / 620 | 4 / 190 |
| Korrekt | 77.1 % | **87.9 %** |
| Visits ohne Korrektur | 38.7 % | **68.6 %** |
| Leere Detektionen je Pfeil | 2.8 | **0.36** |
| Phantome | 7.2 % | **1.0 %** |
| Verpasst | 7.3 % | **2.1 %** |
| Median-Abweichung | 8.7 mm | **2.2 mm** |

Die leeren Detektionen fallen um das Achtfache. Das stützt die Entscheidung aus
[testrun1 §11](testrun1.md#11-client-trigger-schritt-2-und-4-zurückstellen), die
Fehlauslöser nicht im Client-Trigger zu bekämpfen: sie kamen zum größten Teil
von der wackeligen Kameraführung, nicht von der Trigger-Logik.

---

## Status

| # | Befund | Bezug | Status |
|---|---|---|---|
| 1 | [Kalibrierung: keine Regression, aber keine Qualitätsprüfung](#1-kalibrierung-keine-regression-aber-keine-qualitätsprüfung) | neu | offen |
| 2 | [Ring-Innenkanten sind der dominante Fehler](#2-ring-innenkanten-sind-der-dominante-fehler) | [testrun1 §3](testrun1.md#3-ring-innenkanten-nachmessen) | bestätigt, offen |
| 3 | [Kameraversatz tritt weiter auf](#3-kameraversatz-tritt-weiter-auf) | [testrun1 §7](testrun1.md#7-rekalibrierung-bei-kameraversatz) | bestätigt, offen |
| 4 | [Was dieser Lauf nicht mehr zeigt](#4-was-dieser-lauf-nicht-mehr-zeigt) | testrun1 §1, §2, §4, §5 | nicht mehr beobachtbar |

---

## 1. Kalibrierung: keine Regression, aber keine Qualitätsprüfung

**Anlass.** Beim Spielen war das Board-Overlay wiederholt sichtbar falsch, aus
manchen Winkeln war gar keine brauchbare Kalibrierung zu bekommen. Verdacht: die
Kalibrierung ist über die letzten Stände schlechter geworden.

**Der Verdacht bestätigt sich nicht.** Fünf historische Stände von
`board_detector.py` über denselben Bilderstapel (18 Fotos aus
`testdata/calibration` plus 16 Base-Frames aus diesem Export):

| Commit | gut (≥ 80 %) | Mittel |
|---|---|---|
| HEAD | 29 / 34 | 88.1 % |
| `df9af9c` | 29 / 34 | 88.1 % |
| `9fbfa6d` (Low-Angle-Fix) | 29 / 34 | 88.1 % |
| `710d2ea` | 29 / 34 | 88.1 % |
| `3122943` | 29 / 34 | 88.1 % |
| `d35a139` (RANSAC-Auswahl) | 29 / 34 | 88.1 % |
| `d1bafc8` (davor) | 24 / 34 | 79.1 % |

Seit `d35a139` identisch, der einzige Sprung ging nach oben. Was sich geändert
hat, ist die Häufigkeit: seit die Rekalibrierung an jedem Rundenwechsel hängt,
läuft sie ein Vielfaches so oft, und mit dem näheren, steileren Stativ trifft sie
den Fehlerfall entsprechend öfter.

**Was fehlt, ist die Messung.** `run_all.py` misst, *ob* eine Homographie
herauskam, nicht ob sie stimmt — genau die Lücke, die der Eindruck beschreibt.
Für diese Untersuchung ad hoc gebaut (nicht im Repo): Doppel- und Triple-Band aus
dem Board-Modell über die Homographie zurück ins Bild projizieren und dort die
tatsächliche Farbe prüfen, 20 Sektoren × 7 Winkel × 2 Radien = 280 Proben. In den
Fit gehen nur 20 Punkte auf der Außenkante ein, das Triple-Band und die
Rot/Grün-Alternation sind damit ungesehene Daten.

Ergebnis: **2 von 31 kalibrierten Bildern sind unbrauchbar** —
`cc_setup/center_mid` (49 %) und der Base-Frame von `01a0b375` throw0 (53 %).
Der Rest liegt bei 96 – 100 %. Kein weicher Übergang, zwei Ausreißer.

**Das Residuum zeigt es bereits an.** `cv2.findHomography` bekommt 20 exakte
Korrespondenzen; deren Rückprojektionsfehler trennt die beiden Gruppen sauber:

| | Residuum (Mittel über die 20 Punkte) |
|---|---|
| 29 gute Kalibrierungen | 0.22 – **1.36 mm** |
| 2 kaputte | **8.12** – 8.55 mm (max 25 – 28 mm) |

Faktor 6 Lücke, keine Überschneidung. 8 mm ist die Breite eines ganzen
Triple-Rings: die Drahtkorrespondenzen sind auf diesen Bildern untereinander
unverträglich. Die Mittelpunkt-Iteration findet folglich keinen Fixpunkt,
oszilliert über alle sechs Pässe und gibt am Ende den *letzten* zurück, egal wie
schlecht er ist.

**Zwei Sackgassen, damit sie nicht nochmal probiert werden:**

- *Dämpfung der Mittelpunkt-Iteration* (Faktor 0.5): konvergiert zwar auf
  < 0.5 px, aber auf einen falschen Fixpunkt — `cc_setup/center_mid` landet bei
  53 %.
- *Besten statt letzten Pass wählen*: bei sechs Pässen 52.5 % → 54.3 %. Über
  20 Pässe taucht bei `01a0b375` throw0 zwar ein 86 %-Pass auf, aber innerhalb
  eines schlechten Laufs korreliert das Residuum **nicht** mit der Qualität. Es
  taugt als Detektor, nicht als Selektor.
- *Die Pass-Zahl ist kein Indikator.* Auch gute Frames laufen regelmäßig in den
  Sechser-Deckel (`01a0b383` throw0: 6 Pässe bei 0.33 mm Residuum).

**Spur in den Spieldaten.** `01a0b375` ist das Spiel mit dem kaputten
Base-Frame — und zugleich das einzige mit beiden Phantomen des ganzen Laufs
(throw0/dart1 als T11, throw1/dart1 als MISS) sowie 6 Alignment-Versätzen über
10 px (bis 113 px). Ab throw4 sitzt die Kalibrierung dort und das Spiel kommt auf
88 %. Das ist konsistent mit „erst schief kalibriert, dann Stativ gerückt und neu
kalibriert", aber aus den Logs nicht beweisbar, solange
[testrun1 §9](testrun1.md#9-kalibrierungen-ins-event-log) offen ist — wann
kalibriert wurde, steht nicht im Event-Log.

**Möglicher Fix.** Residuum berechnen (die Daten liegen vor, kostet nichts) und
oberhalb einer Schwelle eine eigene `CalibrationFailure` melden statt ein
verzogenes Board zurückzugeben. 3 mm liegt mittig in der Lücke. Das behebt die
Ursache nicht, macht sie aber sichtbar, statt eine Runde lang falsch zu werten.
Die Ursache selbst — warum die Drahtkorrespondenzen bei steilem Winkel bzw.
kleinem Board im Bild auseinanderlaufen — bleibt offen und gehört zu
[kalibrierung.md §7](../feature/done/kalibrierung.md#7-offene-punkte).

---

## 2. Ring-Innenkanten sind der dominante Fehler

**Befund.** 13 der 25 Mismatches liegen unter 5 mm von der erwarteten Fläche.
Von den 19 `wrong` sind **9 Ringverwechslungen im selben Sektor**. Die Radien
aus `game_events.csv` (`pos_x`/`pos_y` in Board-Millimetern):

| Fall | gebucht | Truth | Radius | Modellkante |
|---|---|---|---|---|
| `01a0b37c` t0/d1 | S20 | T20 | 96.8 | Triple innen 99.0 |
| `01a0b37c` t4/d2 | S20 | T20 | 97.0 | " |
| `01a0b37c` t4/d1 | S1 | T1 | 97.5 | " |
| `01a0b388` t0/d2 | S18 | T18 | 96.8 | " |
| `01a0b383` t9/d3 | S5 | T5 | 98.1 | " |
| `01a0b37c` t21/d2 | S1 | D1 | 159.4 | Double innen 162.0 |
| `01a0b388` t6/d1 | T1 | S1 | 100.0 | Triple innen 99.0 |
| `01a0b375` t6/d2 | T5 | S5 | 106.8 | Triple außen 107.0 |
| `01a0b375` t7/d2 | S5 | T5 | 110.5 | " |

Sechs Fälle sitzen **innerhalb** der Modell-Innenkante, und die fünf am Triple
bilden ein enges Bündel bei 96.8 – 98.1 mm, also 0.9 – 2.2 mm zu weit innen. Das
ist dieselbe Richtung und dieselbe Größenordnung wie die Kantenmessung in
[testrun1 §3](testrun1.md#3-ring-innenkanten-nachmessen) (Triple innen −3.1 mm,
Double innen −3.6 mm), diesmal aus einer unabhängigen Quelle: dort aus den
Farbkanten der Basisbilder, hier aus den gebuchten Pfeilpositionen gegen die
Spielerkorrektur.

**Gegenbeispiele.** Zwei Fälle laufen andersherum: `01a0b388` t6/d1 (T1 bei
100.0, Truth S1) und `01a0b375` t7/d2 (S5 bei 110.5, Truth T5) verlangen eine
Triple-Kante *weiter außen*. Der zweite widerspricht dabei direkt `01a0b375`
t6/d2 (106.8). Es ist also nicht nur ein Kantenversatz, sondern zusätzlich
Streuung in der Spitzenschätzung — ein reiner Konstanten-Fix hebt die Quote
nicht vollständig.

**Größenordnung.** Die 9 Ringverwechslungen sind 4.7 % aller Pfeile. Säße die
Triple-Innenkante 2 mm weiter innen, gingen fünf davon in die richtige Fläche,
eines (T1 bei 100.0) zusätzlich daneben. Das deckt sich mit der kontrafaktischen
Rechnung aus testrun1 (+14 / −4 bei 2.5 mm) und bleibt wie dort ein Hinweis auf
die Größenordnung, nicht mehr — bestimmt auf denselben Daten, aus denen der
Befund stammt.

**Nachgemessen (20.09.):** Double und Triple messen am Board je 10.0 mm von Apex
zu Apex, nicht 8.0 mm — die Konstanten passten tatsächlich nicht zu diesem Board.
Sie erklären aber nur 2.0 der gemessenen 3.1 – 3.6 mm; der Rest ist der radiale
Bias. Es war also beides, Aufschlüsselung in
[testrun1 §3](testrun1.md#ergebnis-der-lineal-messung-2009).

---

## 3. Kameraversatz tritt weiter auf

`alignment_shift_px` liegt im Median bei 0.06 – 0.16 px, aber:

| Spiel | Fits | Versatz > 10 px | größter |
|---|---|---|---|
| `01a0b375` | 76 | 6 | 113 px |
| `01a0b37c` | 81 | 0 | 0.50 px |
| `01a0b383` | 44 | 3 | 2252 px |
| `01a0b388` | 56 | 0 | 0.59 px |

Seltener als in Testlauf 1 (17 Fälle in sechs Spielen), aber nicht weg, und in
`01a0b375` genau in dem Spiel, dessen Kalibrierung auch nach §1 auffällig ist.
Der Wert von 2252 px in `01a0b383` ist kein Versatz, sondern ein
fehlgeschlagenes Alignment, das trotzdem gebucht hat.
[testrun1 §7](testrun1.md#7-rekalibrierung-bei-kameraversatz) bleibt damit
unverändert gültig: über einer Schwelle Rekalibrierung anfordern und den Frame
nicht buchen.

---

## 4. Was dieser Lauf nicht mehr zeigt

Mehrere Befunde aus Testlauf 1 sind in diesen Daten nicht mehr messbar. Die
zugehörigen Schritte sind **nicht umgesetzt**; sie sind lediglich nicht mehr
beobachtbar, was sie nicht erledigt macht:

- **§1 Rekalibrierung auf vollem Board:** kein MISS-Phantom über 3000 mm² in
  diesem Lauf, insgesamt nur 2 Phantome. Bei 4 Spielen gegen 15 ist das kein
  Freispruch.
- **§2 Gezogene Pfeile vor der Größenprüfung:** 5 `implausible_shape` gegen 83,
  keine Serie wie in `0a49c`.
- **§4 Orientierung bei steiler Kamera:** keine MISS-Buchung über 280 mm. Das
  Setup war flacher als die drei Spiele, in denen der Befund entstand.
- **§5 Mindestfläche für punktende Pfeile:** keine punktende Buchung unter
  250 mm².

Die kleine Stichprobe ist hier die Einschränkung: 190 Pfeile gegen 620. Für
Phase 4 braucht es entweder mehr Spiele im neuen Setup oder die Aussage, dass die
Zahlen für ein Setup und nicht für das System gelten.

---

## Reproduktion

- Report: `uv run python scripts/evaluation/report.py --out _report_prod/...`
  gegen die vier Spiel-IDs.
- Kalibrierungsqualität: die Base-Frames aus dem Export durch
  `scripts/calibration/run_all.py` schicken; die Farbprobe und der
  Residuum-Vergleich aus §1 sind ad hoc gemessen und liegen nicht im Repo.
- Historische Stände: `git archive <commit> backend/src` in ein temporäres
  Verzeichnis und `sys.path` darauf zeigen lassen — der Arbeitsbaum bleibt
  unberührt.
