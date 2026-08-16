# Dart-Tracking-System

## Projektkontext
Bachelorarbeit-Projekt. Ziel: automatisches Dart-Scoring per Smartphone-Kamera
statt teurer Multi-Kamera-Hardware. Details: @docs/konzept.md

## Architektur
Hybrid: Frontend (Browser, Frame-Differenz via Canvas API) erkennt Wurf-Events,
schickt nur bei Trigger ein JPEG-Standbild per WebSocket ans Backend.
Backend (FastAPI/Flask + OpenCV) macht Board-Kalibrierung (Homographie),
Pfeil-Erkennung und Scoring.

Die Kalibrierungs-Pipeline ist im Detail dokumentiert (Algorithmen, Parameter,
verworfene Ansätze): @docs/feature/kalibrierung.md

Die Erkennungs-Pipeline ist im Detail dokumentiert (Algorithmen, Parameter,
verworfene Ansätze): @docs/feature/erkennung.md

## Zeitplan / aktuelle Phase
Siehe @docs/zeitplan.md — aktuell in Phase X, Fokus auf Y.

## Frontend-Konventionen
Angular, siehe @docs/guidelines/frontend-best-practices.md
PrimeNG für Styling, die Dokumentation siehe @docs/guidelines/primeng-documentation.md

## Backend-Konventionen
FastAPI, siehe @docs/guidelines/backend-best-practices.md

## Kommentar-Regeln
Diese Regeln gelten für **alle** Fließtext-Zeilen im Code: `#`, `//`, `<!-- -->`,
Python-Docstrings und TSDoc-Blöcke. Docstrings sind hier ausdrücklich keine
Ausnahme — dort sammelt sich der meiste überflüssige Text an.

**Harte Obergrenzen** (bei Überschreitung: kürzen oder nach `docs/feature/`
verschieben, nicht "begründen"):
- Modul-Docstring / Datei-Kopf: max. **3 Zeilen**
- Funktions- oder Methoden-Docstring: max. **3 Zeilen**
- Inline-Kommentar über einer Konstante, einem Feld oder einem Statement:
  max. **2 Zeilen**
- Kommentar im HTML-Template: max. **1 Zeile**, und nur wenn das Markup die
  Absicht wirklich nicht zeigt

**Inhalt:** Ein Kommentar sagt, *was* die Sache tut oder welche Einheit ein Wert
hat. Er sagt nicht:
- warum das früher anders war ("the old trigger keyed on the pixel count …")
- welcher Bug dazu geführt hat
- welche Alternative verworfen wurde
- was gemessen wurde
- wie andere Teile des Systems reagieren, wenn man es ändert

Das alles gehört nach `docs/feature/<feature>.md`. Diese Dateien existieren genau
dafür. Wenn ein Kommentar länger werden will als die Grenze oben: ein Satz im
Code, der Rest als Absatz in `docs/feature/`.

**Sprache:** Kommentare immer auf Englisch.

**Bei Änderungen an bestehendem Code:** keine neuen Kommentare hinzufügen, nur
weil etwas geändert wurde. Ein Kommentar, der sich auf den Prompt oder den Diff
bezieht ("now also handles …", "changed so that …"), ist ohne diesen Kontext
unlesbar und daher verboten.

**Selbstprüfung vor dem Abschluss:** Maßgeblich sind die Zeilengrenzen oben —
die gelten immer. Zusätzlich als Geruchsprobe, aber nur bei Dateien ab ca. 100
Zeilen: über ~15 % Kommentaranteil ist es zu viel. Bei kleinen Dateien ist der
Prozentsatz aussagelos, weil ein einzelner Modul-Docstring schon 20 % ausmacht.

## Commands
- `npm run start` — Frontend starten
- `uv run uvicorn app.main:app --app-dir src --reload` — Backend starten