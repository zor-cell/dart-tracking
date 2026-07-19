# Feature-Roadmap

Lebendes Dokument zur Feature- und Ablaufplanung des Dart-Tracking-Systems.
Ergänzt [konzept.md](konzept.md) (das *Was* und *Warum*) und
[zeitplan.md](zeitplan.md) (die *Termine*) um das *Wie* auf Feature-Ebene.

> Status: Entwurf. Wird laufend verfeinert — insbesondere der Abschnitt
> [Wissenschaftliche Grundlagen](#wissenschaftliche-grundlagen--zu-recherchierende-literatur)
> ist als Sammelstelle beim Lesen gedacht.

---

## 1. Nutzerfluss als Zustandsautomat

Die App ist kein Satz gleichberechtigter Tabs, sondern ein linearer Ablauf
innerhalb einer **Spiel-Session** mit klaren Phasen:

```
  Setup              Kalibrierung           Tracking                 Ende
┌─────────┐        ┌──────────────┐       ┌──────────────┐       ┌──────────┐
│ Spieler │        │ Kamera an,   │       │ Frame-Diff   │       │ Auswer-  │
│ + Modus │ ─────▶ │ Board per    │ ────▶ │ triggert →   │ ────▶ │ tung,    │
│ wählen  │        │ Homographie  │       │ Standbild →  │       │ später   │
│         │        │ erkennen     │       │ Backend →    │       │ speichern│
│         │        │              │       │ Scoring      │       │          │
└─────────┘        └──────────────┘       └──────────────┘       └──────────┘
```

Kernentscheidung: **Kamera und Scores sind eine gemeinsame Spielansicht**, kein
separater Tab. Während des Spiels ist die Kamera oben durchgehend sichtbar,
darunter das Scoreboard. Board-Kalibrierung und Tracking sind Sub-Zustände
*innerhalb* dieser Ansicht, keine eigenen Seiten.

---

## 2. Navigation & Routen

Die aktuelle Struktur (`/start`, `/game`, `/capture`, `/settings`) ist
redundant: `/capture` ist konzeptionell Teil von `/game`. Geplante
Überarbeitung:

| Route        | Zweck                                                                 | Änderung                          |
|--------------|-----------------------------------------------------------------------|-----------------------------------|
| `/start`     | Landing: „Neues Spiel"; später letzte Spiele / Statistiken            | bleibt                            |
| `/game/new`  | Setup-Formular: Spieler + Spielmodus (501, …)                         | neu                               |
| `/game`      | Aktive Session: Kamera oben + Scoreboard unten; Sub-States Kalibrierung → Tracking | verschmilzt `/game` + `/capture` |
| `/settings`  | Technische Erkennungs-Parameter (Thresholds); global **und** als Schnellzugriff im Spiel | bleibt, geschärft                 |

Konsequenzen:

- `/capture` als eigener Tab entfällt; die Bottom-Nav schrumpft auf
  **Start · Spiel · Einstellungen**.
- Zwei getrennte „Settings"-Begriffe sauber unterscheiden:
  - **Spiel-Setup** — pro Spiel: Spieler, Modus (`/game/new`).
  - **Detection-Settings** — technisch: Thresholds fürs Testen (`/settings`).

---

## 3. Feature-Roadmap nach Phasen

Angelehnt an die Phasen in [zeitplan.md](zeitplan.md).

### Phase 2 — MVP-Kern

- [ ] Routen-Rework (`/capture` in `/game` auflösen, `/game/new` anlegen)
- [ ] Game-Session-State via Signals (Spieler, Modus, aktueller Werfer,
      Würfe pro Runde, Restpunkte)
- [ ] Spiel-Setup-View (Spieler + Modus)
- [ ] Game-View: Kamera-Layout oben, Scoreboard unten
- [ ] Board-Kalibrierung als expliziter Schritt (Button „Board erkennen" →
      Frame ans Backend → Homographie-Matrix zurück)
- [ ] WebSocket-Protokoll erweitern (siehe [Abschnitt 4](#4-websocket-protokoll))
- [ ] Threshold-Settings real an den `ThrowDetector` verdrahten

### Phase 3 — Robustheit

- [ ] Beleuchtungsvarianz / Schattenbildung (motiviert die einstellbaren Thresholds)
- [ ] Pfeil-Verdeckung bei mehreren Darts
- [ ] Reconnect: WebSocket **und** Session-State nach Seiten-Refresh
      wiederherstellen (echtes „bestehen bleiben" geht bei hartem Reload nicht —
      Ziel ist Auto-Reconnect + Wiederherstellung über eine Session-/Game-ID)

### Phase 4 — Evaluation

- [ ] Auswertung gegen das Test-Set (Trigger-Fehlerrate, Segment-Trefferquote,
      End-to-End-Latenz)

### Später (erweiterte Features, siehe konzept.md §5)

- [ ] Postgres: Spiele persistent speichern
- [ ] Statistik-Dashboard (3-Dart-Average, Checkout-Quoten, Doppel-Trefferquote)
- [ ] Heatmap-Generierung
- [ ] Trainingsmodus mit Schwachstellenanalyse

---

## 4. WebSocket-Protokoll

**Ist-Zustand:** Das Backend (`/api/ws/darts`) akzeptiert Frames und antwortet
nur mit der empfangenen Byte-Anzahl — reiner Echo-Stub.

**Soll-Zustand:** Typisierte JSON-Nachrichten in beide Richtungen. Erste
Skizze (Contract wird beim Bau festgezurrt):

| Richtung          | Typ                  | Nutzlast (Skizze)                                  |
|-------------------|----------------------|----------------------------------------------------|
| Client → Server   | `calibration_frame`  | JPEG-Standbild zur Board-Erkennung                 |
| Server → Client   | `calibration_result` | Homographie-Matrix, Erfolg/Fehler                  |
| Client → Server   | `throw_frame`        | JPEG-Standbild nach Trigger                        |
| Server → Client   | `dart_detected`      | Board-Koordinate, Segment, Punktwert               |
| Server → Client   | `game_state`         | aktueller Spielstand (falls Scoring serverseitig)  |

Offene Frage: Wird der Spielstand im Client oder im Backend geführt? Für die
spätere Postgres-Persistenz spricht einiges für serverseitigen Game-State.

---

## 5. Detection-Parameter (für die Settings-View)

Aktuell hartcodiert; sollen zum Testen unter wechselnden Lichtverhältnissen
einstellbar werden. Quelle: `throw-detector.ts` und `throw-capture.service.ts`.

| Parameter                | Aktueller Wert | Bedeutung                                         |
|--------------------------|----------------|---------------------------------------------------|
| `MOTION_THRESHOLD`       | 12             | Ab welcher mittleren Pixeldifferenz „Bewegung"    |
| `SETTLE_THRESHOLD`       | 4              | Unter welcher Differenz „beruhigt"                |
| `SETTLE_FRAMES_REQUIRED` | 5              | Wie viele ruhige Frames bis Trigger               |
| Diff-Auflösung           | 160 × 90       | Herunterskalierung für die Differenzberechnung    |
| `PROCESS_INTERVAL_MS`    | 100            | Verarbeitungsintervall (≈10 fps Analyse)          |
| `JPEG_QUALITY`           | 0.85           | Qualität des gesendeten Standbilds                 |

---

## 6. Wissenschaftliche Grundlagen / zu recherchierende Literatur

Sammelstelle für die Related-Work- und Methodik-Teile der Arbeit. **Zitationen
hier noch nicht verifiziert — vor Übernahme in die Arbeit selbst prüfen.**

### 6.1 Board-Erkennung & Kalibrierung
- Techniken: Hough-Kreis-/Ellipsen-Detektion, Konturverfolgung, Homographie-
  Schätzung aus der genormten Board-Geometrie (20 Sektoren, feste Radien).
- Suchbegriffe: *automatic dartboard calibration homography*,
  *dartboard detection opencv*, *ellipse detection dartboard*.
- Quellen: _(hier sammeln)_

### 6.2 Pfeil-Lokalisierung & Verdeckung
- Techniken: Hough-Linien / Konturanalyse zur Pfeilspitze; Umgang mit partieller
  Verdeckung bei mehreren Darts.
- Suchbegriffe: *dart tip detection*, *dart pose estimation*, *occlusion*.
- Quellen: _(hier sammeln)_

### 6.3 Ereigniserkennung (Frame-Differenz)
- Techniken: Frame-Differencing, Background-Subtraction, Bewegungs-/Stabilitäts-
  Detektion.
- Suchbegriffe: *frame differencing motion detection*, *background subtraction*.
- Quellen: _(hier sammeln)_

### 6.4 Vergleichs-/End-to-End-Ansätze
- Lead: **„DeepDarts"** — Single-Image-Dart-Scoring per Deep Learning; taugt gut
  als Related-Work-Anker für den kamerabasierten Ansatz. Autor/Jahr/Venue vor
  Zitation verifizieren.
- Quellen: _(hier sammeln)_

---

## 7. Offene Entscheidungen

- Spielstand client- oder serverseitig führen? (Kopplung an Postgres-Frage)
- Board-Kalibrierung einmalig pro Session oder nachjustierbar?
- Settings global vs. als Overlay-Panel im laufenden Spiel (fürs schnelle Testen)?
