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
verworfene Ansätze): @docs/kalibrierung.md

Die Erkennungs-Pipeline ist im Detail dokumentiert (Algorithmen, Parameter,
verworfene Ansätze): @docs/erkennung.md

## Zeitplan / aktuelle Phase
Siehe @docs/zeitplan.md — aktuell in Phase X, Fokus auf Y.

## Frontend-Konventionen
Angular, siehe @docs/guidelines/frontend-best-practices.md
PrimeNG für Styling, die Dokumentation siehe @docs/guidelines/primeng-documentation.md

## Backend-Konventionen
FastAPI, siehe @docs/guidelines/backend-best-practices.md

## Instruktionen
- Kommentare in Code sollen immer auf Englisch verfasst werden
- Vermeide unnötige Kommentare, damit sind vor allem Kommentare gemeint, die sich speziell auf ein Prompt beziehen,
wenn dieser Kontext verloren ist, sind sie unlesbar
- Halte Kommentare kurz und prägnant

## Commands
- `npm run start` — Frontend starten
- `uv run uvicorn app.main:app --app-dir src --reload` — Backend starten