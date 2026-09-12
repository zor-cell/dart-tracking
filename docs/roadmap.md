# Feature-Roadmap

Lebendes Dokument zur Feature- und Ablaufplanung des Dart-Tracking-Systems.
Ergänzt [konzept.md](konzept.md) (das *Was* und *Warum*) und
[zeitplan.md](zeitplan.md) (die *Termine*) um das *Wie* auf Feature-Ebene.
Für einzelne Teilsysteme gibt es eigene Detaildokumente —
[kalibrierung.md](feature/done/kalibrierung.md) beschreibt die Board-Kalibrierung auf
Algorithmus-Ebene.

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
| `/game/new`  | Setup-Formular: Spieler, Variante und Modus ([spielmodi.md](feature/done/spielmodi.md)) | neu                               |
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

- [x] Routen-Rework (`/capture` in `/game` auflösen, `/game/new` anlegen)
- [x] Game-Session-State (server-seitig; Client-Cache via Signals — Spieler,
      Modus, aktueller Werfer, Würfe pro Runde, Restpunkte)
- [x] Spiel-Setup-View (Spieler + Modus)
- [ ] Game-View: Kamera-Layout oben, Scoreboard unten (Scoreboard ✓, Kamera offen)
- [ ] Board-Kalibrierung als expliziter Schritt (Button „Board erkennen" →
      Frame ans Backend → Homographie-Matrix zurück). Backend-Pipeline steht,
      siehe [kalibrierung.md](feature/done/kalibrierung.md); offen ist die Anbindung der
      Game-View
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

## 4. HTTP & WebSocket-Protokoll

**Aufteilung:** Der **Spielstand liegt server-seitig** (Entscheidung, siehe §7).
HTTP führt nur noch den Session-Lebenszyklus; alles, was ein Spiel *ändert*,
läuft über den WebSocket — zusammen mit der Vision-Pipeline. Grund ist das
geteilte Spiel: eine Änderung muss auf **einem** Weg jedes Gerät im Raum
erreichen (siehe [multi-device.md](feature/done/multi-device.md)).

**HTTP (REST) — Session-Lebenszyklus**

| Methode & Pfad         | Zweck                                                        |
|------------------------|--------------------------------------------------------------|
| `POST /api/games`      | Spiel anlegen (`mode`, `playerNames`) → Zustand              |
| `GET  /api/games/{id}` | Zustand holen (Initial-Load, Refresh, Prüfung eines Join-Links) |

**WebSocket (`/api/ws/games/{id}`) — Vision-Pipeline, Kommandos & State-Push**

Typisierte JSON-Nachrichten in beide Richtungen:

| Richtung        | Typ                  | Nutzlast                                    |
|-----------------|----------------------|---------------------------------------------|
| Client → Server | `calibration_frame`  | JPEG-Standbild zur Board-Erkennung          |
| Server → Client | `calibration_result` | Homographie-Matrix, Erfolg/Fehler           |
| Client → Server | `detection_frame`    | JPEG-Standbild nach Trigger                 |
| Server → Client | `detection_result`   | Board-Koordinate, Segment, Punktwert        |
| Client → Server | `register_dart`      | Dart buchen (manuell oder als Korrektur)    |
| Client → Server | `undo`               | letzte Aktion zurücknehmen                  |
| Client → Server | `next_player`        | Runde beenden, nächster Spieler             |
| Server → Client | `game_state`         | autoritativer Spielstand, an **alle** Geräte |

Die Frame-Antworten gehen nur an ihren Absender (ihre Overlays liegen im
Pixelraster genau dieser Kamera), `game_state` an den ganzen Raum.

Kein kontinuierlicher Video-Stream: der Client sendet getriggerte Standbilder
(Frame-Diff) plus Kalibrierungs-Frames, nicht laufendes Video — das hält die
Latenz niedrig (siehe konzept.md §3.1).

**Reconnect nach Refresh:** `gameId` in `localStorage`; nach Reload
`GET /api/games/{id}` + WS neu verbinden. Kein Spielstand im Browser nötig.

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

Die Parameter der **Board-Kalibrierung** (HSV-Grenzen, RANSAC-Iterationen,
Band-Toleranzen) liegen separat in `board_detector.py` und sind in
[kalibrierung.md](feature/done/kalibrierung.md) samt Begründung dokumentiert. Ob sie
ebenfalls in die Settings-View gehören, ist offen — sie werden einmalig beim
Kalibrieren gebraucht, nicht pro Wurf.

---

## 6. Wissenschaftliche Grundlagen / zu recherchierende Literatur

Sammelstelle für die Related-Work- und Methodik-Teile der Arbeit. **Zitationen
hier noch nicht verifiziert — vor Übernahme in die Arbeit selbst prüfen.**

### 6.1 Board-Erkennung & Kalibrierung

> **Implementiert.** Der eigene Ansatz — HSV-Segmentierung, Zwei-Ring-RANSAC
> über Komponenten-Schwerpunkte, Ellipsen-Fit, Farbübergänge als
> Punktkorrespondenzen — ist in [kalibrierung.md](feature/done/kalibrierung.md) beschrieben,
> inklusive der verworfenen Alternativen (u. a. `HoughCircles`, dessen
> Kreisannahme bei schräger Perspektive nicht trägt).

- Techniken: Hough-Kreis-/Ellipsen-Detektion, Konturverfolgung, Homographie-
  Schätzung aus der genormten Board-Geometrie (20 Sektoren, feste Radien).
- Suchbegriffe: *automatic dartboard calibration homography*,
  *dartboard detection opencv*, *ellipse detection dartboard*.
- Quellen (Stand 07/2026, Zitierbarkeit noch prüfen):

  *Dart-spezifisch:*
  - **DeepDarts** (McNally et al., CVPR-Workshop 2021) — *peer-reviewed, Kernanker.*
    Ein Netz findet Dart-Positionen **und vier Board-Kalibrierungspunkte** →
    Homographie in die Board-Ebene. Konzeptionell exakt unser
    Kalibrierungs-Schritt (nur per Deep Learning statt Hough/Kontur).
    [arXiv](https://arxiv.org/abs/2105.09880) ·
    [Volltext-PDF (CVF)](https://openaccess.thecvf.com/content/CVPR2021W/CVSports/papers/McNally_DeepDarts_Modeling_Keypoints_as_Objects_for_Automatic_Scorekeeping_in_Darts_CVPRW_2021_paper.pdf) ·
    [IEEE](https://ieeexplore.ieee.org/document/9522909/)

  *Open-Source-Projekte (Methoden-Referenz, nicht als Paper zitieren):*
  - **opencv-steel-darts** (Höttinger) — klassische OpenCV-Pipeline (kein DL) auf
    Raspberry Pi; am nächsten an unserem Hough/Kontur-Ansatz und Deploy-Target.
    [GitHub](https://github.com/hanneshoettinger/opencv-steel-darts)
  - **dart-sense** (bnww) — YOLOv8, Smartphone-Video, automatische Board-
    Kalibrierung; die moderne Variante unserer Zielkonfiguration.
    [GitHub](https://github.com/bnww/dart-sense)

  *Klassische CV-Grundlagen (Board projiziert schräg → Ellipse):*
  - [Fast Ellipse Detection Using Hough Transform](https://www.researchgate.net/publication/221367058_Fast_Ellipse_Detection_Algorithm_Using_Hough_Transform_on_the_GPU)
  - [Robust Detection of Non-overlapping Ellipses (arXiv 2011.13849)](https://arxiv.org/pdf/2011.13849)
    — Ellipsen-Extraktion für Kalibrierungs-Targets, übertragbar auf die Board-Ringe.
  - Fundamente: **Hough-Transform** (Duda & Hart, 1972), **RANSAC** (Fischler &
    Bolles, 1981), **Hartley & Zisserman „Multiple View Geometry"** (Homographie).

  *Patente (nur Prior-Art/Motivation „teure Multi-Kamera-Systeme"):*
  - [US20170307341A1](https://patents.google.com/patent/US20170307341A1/en) ·
    [US20220341716](https://patents.justia.com/patent/20220341716)

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
- **DeepDarts** als Related-Work-Anker für den Single-Camera-Ansatz — volle
  Angabe unter [6.1](#61-board-erkennung--kalibrierung).
- **PEELA** (STLabs) — erweitert DeepDarts auf Dual-Kamera + YOLOv4, adressiert
  dessen Schwächen bei schrägen Winkeln. Projekt/Report — Peer-Review prüfen.
  [Link](https://stlabs.is/project3)
- Quellen: _(weiter sammeln)_

---

## 7. Offene Entscheidungen

- ~~Spielstand client- oder serverseitig führen?~~ **Entschieden: serverseitig.**
  Die Scores entstehen ohnehin in der server-seitigen CV-Pipeline, also ist der
  Server die Source of Truth. In-Memory-Store für jetzt, Postgres später; der
  Client hält nur einen synchronisierten Cache (Signals).
- Board-Kalibrierung einmalig pro Session oder nachjustierbar?
- Settings global vs. als Overlay-Panel im laufenden Spiel (fürs schnelle Testen)?
