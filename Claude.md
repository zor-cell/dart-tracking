# Dart-Tracking-System

## Projektkontext
Als Bachelorarbeit entstanden. Ziel: automatisches Dart-Scoring per
Smartphone-Kamera statt teurer Multi-Kamera-Hardware.

## Architektur
Hybrid: Frontend (Browser, Frame-Differenz via Canvas API) erkennt Wurf-Events,
schickt nur bei Trigger ein JPEG-Standbild per WebSocket ans Backend.
Backend (FastAPI/Flask + OpenCV) macht Board-Kalibrierung (Homographie),
Pfeil-Erkennung und Scoring.

## Frontend-Konventionen
Angular, siehe @docs/guidelines/frontend-best-practices.md
PrimeNG für Styling, die Dokumentation siehe @docs/guidelines/primeng-documentation.md

## Backend-Konventionen
FastAPI, siehe @docs/guidelines/backend-best-practices.md

## Doku-Struktur
- `docs/guidelines/` — Konventionen für Frontend und Backend.
- Offene Arbeit und Planung stehen in den GitHub-Issues, nicht im Repo.
- Begründungen zu einer Änderung stehen im Issue oder in der Beschreibung des
  Pull Requests.

## Kommentar-Regeln
Diese Regeln gelten für **alle** Fließtext-Zeilen im Code: `#`, `//`, `<!-- -->`,
Python-Docstrings und TSDoc-Blöcke. Docstrings sind hier ausdrücklich keine
Ausnahme — dort sammelt sich der meiste überflüssige Text an.

**Harte Obergrenzen** (bei Überschreitung: kürzen oder ins Issue bzw. in den
Pull Request verschieben, nicht "begründen"):
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

Das alles gehört ins zugehörige GitHub-Issue oder in die Beschreibung des Pull
Requests. Wenn ein Kommentar länger werden will als die Grenze oben: ein Satz im
Code, der Rest dort.

**Sprache:** Kommentare immer auf Englisch.

**Bei Änderungen an bestehendem Code:** keine neuen Kommentare hinzufügen, nur
weil etwas geändert wurde. Ein Kommentar, der sich auf den Prompt oder den Diff
bezieht ("now also handles …", "changed so that …"), ist ohne diesen Kontext
unlesbar und daher verboten.

**Selbstprüfung vor dem Abschluss:** Maßgeblich sind die Zeilengrenzen oben —
die gelten immer. Zusätzlich als Geruchsprobe, aber nur bei Dateien ab ca. 100
Zeilen: über ~15 % Kommentaranteil ist es zu viel. Bei kleinen Dateien ist der
Prozentsatz aussagelos, weil ein einzelner Modul-Docstring schon 20 % ausmacht.

## Git
**Neu angelegte Dateien immer mit `git add` in den Index legen**, sobald sie
fertig sind — auch Migrationen, Doku und Testskripte.

**Nur `git add`.** Kein `git commit`, kein `git push`, kein Branch- oder
Stash-Kommando — wann und was committet wird, entscheide ich.

## Commands
- `npm run start` — Frontend starten
- `uv run uvicorn app.main:app --app-dir src --reload` — Backend starten