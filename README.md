# Dart-Tracking-System

Automatisches Dart-Scoring mit einer handelsüblichen Smartphone-Kamera statt
teurer Multi-Kamera-Hardware. Bachelorarbeit an der TU Wien (Philippe Zorman,
Matrikelnummer 12225143).

Ein Handy wird auf das Dartboard gerichtet, weitere Geräte können als
Scoreboard demselben Spiel beitreten. Das System erkennt geworfene Pfeile,
berechnet die Punkte und führt ein 501-Spiel ohne manuelles Mitzählen.

## Wie es funktioniert

Hybrid-Architektur, um kontinuierliches Video-Streaming zu vermeiden:

1. **Kalibrierung (Server).** Aus einem Standbild wird das Board erkannt — rote
   und grüne Segmente in HSV, Ellipsen-Fit auf den Doppelring, Sektordrähte über
   Farbwechsel — und daraus eine Homographie von Bildpixeln nach
   Board-Millimetern berechnet.
2. **Wurf-Erkennung (Client).** Der Browser rechnet per Canvas API eine
   Frame-Differenz und erkennt, wann ein neuer Pfeil im Bild zur Ruhe kommt.
   Erst dann geht ein einzelnes JPEG über den WebSocket ans Backend.
3. **Pfeil-Lokalisierung und Scoring (Server).** Der Frame wird auf den
   Referenz-Frame registriert, die Differenz zu einem Pfeil zusammengesetzt, die
   Spitze bestimmt und über die Homographie in ein Board-Segment übersetzt.
4. **Spielstand (Server).** Der Punktestand ist server-autoritativ und wird per
   WebSocket an alle Geräte im Raum gepusht.

**Stack:** Angular 21 + PrimeNG 21 (Frontend), FastAPI + OpenCV + NumPy
(Backend), Docker Compose, nginx als Reverse Proxy.

## Dokumentation

Konventionen für Beiträge stehen in [Claude.md](Claude.md) und
[docs/guidelines/](docs/guidelines/). Offene Arbeit und Planung stehen in den
[Issues](https://github.com/zor-cell/dart-tracking/issues).

## Lokale Entwicklung

**Voraussetzungen:** Node.js 22, Python 3.12, [uv](https://docs.astral.sh/uv/),
Docker (optional).

Backend, aus `backend/` (läuft auf `:8000`):

```bash
uv run uvicorn app.main:app --app-dir src --reload
```

Frontend, aus `frontend/` (läuft auf `:4200`):

```bash
npm run start
```

Das Backend erlaubt CORS nur für `localhost:4200` und `127.0.0.1:4200` — im
Dev-Setup greift das Frontend also direkt zu, in Produktion ist alles
gleichursprünglich hinter nginx und CORS spielt keine Rolle.

**Kamerazugriff braucht einen sicheren Kontext.** `getUserMedia` funktioniert nur
über HTTPS oder auf `localhost`. Ein Handy im LAN, das auf die Dev-Maschine
zeigt, bekommt daher kein Kamerabild — dafür die deployte Instanz benutzen.

### CV-Pipelines gegen Testdaten laufen lassen

Die Runner spielen Fotos aus `backend/testdata/` durch dieselbe Pipeline wie der
Live-Betrieb und schreiben annotierte Kopien plus einen Genauigkeitsbericht
zurück (Zielordner über `--out`). Ebenfalls aus `backend/`:

```bash
uv run python scripts/calibration/run_all.py
```

```bash
uv run python scripts/detection/run_all.py
```

`run_debug.py` in beiden Ordnern macht dasselbe für ein einzelnes Bild.

## Deployment

Deployt wird auf einen **Raspberry Pi 5** im Heimnetz. Von außen erreichbar ist
er über einen **Cloudflare Tunnel**, nicht über Portfreigaben im Router.

**Produktion:** [https://darts.zorphy.net/](https://darts.zorphy.net/)

### Ablauf

```
git push (main)
   → GitHub Actions, Workflow "Deploy"
   → self-hosted Runner mit Label "rpi5" (läuft auf dem Pi)
   → docker compose up -d --build
   → frontend-Container (nginx) auf Host-Port 10020
   → cloudflared auf dem Pi → öffentliche Domain
```

Definiert in [deploy.yaml](.github/workflows/deploy.yaml). Der Job läuft nur auf
`main`, bei jedem Push oder von Hand über „Run workflow“. Es gibt keinen
Build-Artefakt-Transfer: der Runner steht auf derselben Maschine wie Docker,
gebaut wird direkt dort.

Compose liest seine Werte aus der Umgebung des Jobs. Im Repository müssen dafür
unter Settings → Secrets and variables → Actions angelegt sein:

| Art | Name |
|---|---|
| Variable | `POSTGRES_USER`, `POSTGRES_DB`, `SMTP_HOST`, `MAIL_FROM` |
| Variable (optional) | `SMTP_PORT` (Standard `587`), `SMTP_SECURITY` (`starttls`, `tls` oder `none`), `SMTP_USERNAME` |
| Secret | `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `SMTP_PASSWORD` |

### Was Docker Compose aufsetzt

[compose.yaml](compose.yaml) startet zwei Container, beide mit
`restart: unless-stopped`:

| Container | Image | Ports |
|---|---|---|
| `backend_container` | `python:3.12-slim` + uv, uvicorn auf `:8000` | keine Host-Freigabe |
| `frontend_container` | `nginxinc/nginx-unprivileged:1.30-alpine` mit dem gebauten Angular-Bundle | `10020:8080` |

Das Backend ist **bewusst nicht nach außen freigegeben**. Erreichbar ist nur
nginx, der laut [frontend/nginx/default.conf](frontend/nginx/default.conf) `/api/` an
`backend:8000` weiterreicht. Nur `/api/ws/` bekommt die `Upgrade`/`Connection`-Header
und 3600 s Timeouts, damit eine ruhende Verbindung während eines Spiels nicht
abgeräumt wird. Die Security-Header stehen in
[frontend/nginx/snippets/security-headers.conf](frontend/nginx/snippets/security-headers.conf).

Weil Frontend und API damit dieselbe Origin teilen, leitet das Frontend seine
URLs zur Laufzeit ab ([environment.ts](frontend/src/environments/environment.ts)):
`/api` für HTTP, `wss://<host>/api/ws` für den Socket. Der Tunnel muss also nur
einen einzigen Port veröffentlichen, und es ist keine Domain im Build hartkodiert.

### Aufgezeichnete Wurfserien

In einem Testlauf legt das Backend jede Runde als Wurfserie unter
`/app/testdata/evaluation` ab. Der
Host-Pfad dahinter kommt aus `TESTDATA_DIR`, das der Deploy-Job in
[deploy.yaml](.github/workflows/deploy.yaml) auf `/srv/dart-tracking/testdata` setzt. Er
**muss auf dem Pi außerhalb des Runner-Build-Verzeichnisses liegen**: der Runner räumt das Verzeichnis bei jedem Checkout mit `git clean -ffdx`
auf, und das schließt ignorierte Pfade wie `backend/testdata/` ein. Lag der Mount
dort, hat der Container die Dateien als `root` angelegt, worauf der Checkout mit
`failed to remove ...: Permission denied` abbrach — und wären die Rechte gepasst,
hätte stattdessen jedes Deployment die Aufzeichnungen gelöscht.

Für lokales Testen des Prod-Builds legt [compose.dev.yaml](compose.dev.yaml) das
Backend zusätzlich auf `10021` offen:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

Dazu startet [Mailpit](https://mailpit.axllent.org/), das jede ausgehende Mail
abfängt statt sie zuzustellen. Das Postfach liegt unter http://localhost:10025,
SMTP auf `10024`, wohin auch ein lokal gestartetes Backend ohne weitere
Konfiguration sendet.

### Cloudflare Tunnel

Der Tunnel läuft als `cloudflared`-Dienst **auf dem Pi und ist nicht Teil dieses
Repos** — er wird einmalig eingerichtet und überlebt Deployments, weil er nur auf
`localhost:10020` zeigt und die Container darunter ausgetauscht werden.

Er erfüllt hier zwei Zwecke über die Erreichbarkeit hinaus:

- **HTTPS ohne eigenes Zertifikat.** Cloudflare terminiert TLS. Ohne das gäbe es
  keinen Kamerazugriff, weil `getUserMedia` einen sicheren Kontext verlangt.
- **Keine offenen Ports.** Der Pi baut die Verbindung ausgehend auf; im Router
  muss nichts weitergeleitet werden.

Ändert sich der Host-Port in `compose.yaml`, muss die Tunnel-Konfiguration auf
dem Pi mitgezogen werden — der Zusammenhang ist an keiner Stelle automatisiert.

### Zeiterfassung

[backend/scripts/wiki_timelogs.py](backend/scripts/wiki_timelogs.py) erzeugt eine
`Zeiterfassung.md` aus den Timelogs des Projekts im GitLab der TU. Das Skript wird
von Hand gestartet und braucht dafür `TIMETRACKING_TOKEN` mit dem Scope `read_api`.
