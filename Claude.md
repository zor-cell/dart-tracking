# Dart-Tracking-System

## Projektkontext
Bachelorarbeit-Projekt. Ziel: automatisches Dart-Scoring per Smartphone-Kamera
statt teurer Multi-Kamera-Hardware. Details: @docs/konzept.md

## Architektur
Hybrid: Frontend (Browser, Frame-Differenz via Canvas API) erkennt Wurf-Events,
schickt nur bei Trigger ein JPEG-Standbild per WebSocket ans Backend.
Backend (FastAPI/Flask + OpenCV) macht Board-Kalibrierung (Homographie),
Pfeil-Erkennung und Scoring.

## Zeitplan / aktuelle Phase
Siehe @docs/zeitplan.md — aktuell in Phase X, Fokus auf Y.

## Frontend-Konventionen
Angular, siehe @docs/angular-best-practices.md — z. B. Signals statt
zustandsbehafteter Services, standalone Components, kein ngClass/ngStyle.

## Instruktionen
Kommentare in Code sollen immer auf Englisch verfasst werden

## Commands
- `npm run start` — Frontend starten
- `uv run uvicorn app.main:app --app-dir src --reload` — Backend starten
- `docker compose -f compose.yaml -f compose.dev.yaml up -d --build` — Stack lokal
  in Docker. Frontend auf 10020, das Dev-Overlay exposed zusätzlich das Backend
  auf 10021 (Swagger, curl). Ohne `-f`-Flags läuft die Produktions-Variante:
  Backend nur containerintern über den Nginx-Proxy erreichbar — so deployt auch
  die CI auf dem RPi.