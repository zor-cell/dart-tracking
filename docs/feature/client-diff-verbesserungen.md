# Client-Trigger: geplante Verbesserungen

Arbeitsplan für die client-seitige Frame-Differenz — den Schritt, der entscheidet,
ob überhaupt ein Bild zum Server geht. Gegenstück zu
[erkennung-verbesserungen.md](erkennung-verbesserungen.md), das die
*server*-seitige Detektionsqualität behandelt. Die beiden hängen zusammen, und
genau das ist der Ausgangsbefund dieses Dokuments.

Implementierung: `frontend/src/app/features/detection/models/throw-detector.ts`
(Zustandsautomat) und `services/frame-diff.service.ts` (Schleife, Debug-Anzeige).

---

## Ausgangslage: ein Vertrag, den keine Seite erfüllt

Der Trigger ist bewusst auf **Recall** ausgelegt. Sein eigener Kommentar sagt,
worauf sich das stützt:

> *„A false send is cheap — the backend re-checks every frame and rejects a
> non-dart — but a missed throw is unrecoverable."*

Das ist eine Arbeitsteilung: der Client feuert großzügig, der Server sortiert
aus. Beide Hälften fehlen.

**Beobachteter Fall.** Nach dem dritten Dart läuft der Spieler zum Board, um die
Pfeile zu ziehen. Das löst einen `detection_frame` aus, und der Server erkennt
darin einen „Pfeil", dessen Blob über das halbe Board reicht.

Die Trennschärfe wäre dabei nicht knapp: ein Pfeil ist laut
[erkennung.md](erkennung.md) „a few hundred pixels", eine Person vor dem Board
deckt Zehntausende ab. Drei Größenordnungen — das ist kein Schwellwertproblem,
sondern eine fehlende Prüfung.

---

## Status

| # | Schritt | Ort | Aufwand | Status |
|---|---|---|---|---|
| 1 | [Plausibilitätsgrenze auf dem Blob](#1-plausibilitätsgrenze-auf-dem-blob-server) | Server | S | **erledigt** — 218/285 unverändert, ein Fehl-Blob abgefangen |
| 2 | [Episoden-Höchstwert bricht die Erfassung ab](#2-episoden-höchstwert-bricht-die-erfassung-ab-client) | Client | S | offen, braucht Feldmessung |
| 3 | [Auto-Advance vom Kameramodus entkoppeln](#3-auto-advance-vom-kameramodus-entkoppeln) | Frontend | S | offen |
| 4 | [Ausdehnung und Dauer statt Zellenzahl](#4-ausdehnung-und-dauer-statt-zellenzahl-client) | Client | M | offen |
| 5 | [Diff auf die Board-Region beschränken](#5-diff-auf-die-board-region-beschränken-client) | Client | M | offen |
| 6 | [Der abgefallene Pfeil ist eine Null](#6-der-abgefallene-pfeil-ist-eine-null) | beide | L | offen, ungelöst |
| 7 | [Darts jenseits des dritten verwerfen](#7-darts-jenseits-des-dritten-verwerfen-verworfen) | Server | – | **verworfen** — existiert bereits und hilft nicht |
| 8 | [Kein Frame, solange die Runde keinen Dart annimmt](#8-kein-frame-solange-die-runde-keinen-dart-annimmt-client) | Client | S | **erledigt** — vierte Wurflinie im Bestätigungsmodus |
| 9 | [Kleine MISS-Blobs verwerfen](#9-kleine-miss-blobs-verwerfen-server) | Server | S | **erledigt** — 38 von 52 Live-Phantomen, 2 echte Fehlwürfe auf dem Testsatz |

**Messdisziplin.** Schritt 1 wird wie die Server-Schritte mit
`scripts/detection/run_all.py` gegen den Testsatz belegt: die Grenze darf keinen
echten Pfeil kosten. Die Client-Schritte brauchen eine andere Zahl, weil es dafür
keinen Offline-Satz gibt — siehe [Was gemessen werden muss](#was-gemessen-werden-muss).

---

## 1. Plausibilitätsgrenze auf dem Blob *(Server)*

**Befund.** `dart_detector.py` kennt eine Unter-, aber keine Obergrenze:

- `_MIN_DART_AREA_MM2 = 20.0` ist ein Boden.
- `_MAX_DART_LENGTH_MM = 90.0` begrenzt nur, welche Fragmente **fusioniert**
  werden („fragments further apart belong to different objects"). Eine einzelne
  zusammenhängende Komponente, die länger ist, wird davon nicht berührt.
- `_fuse_dart_fragments` ankert auf dem **breitesten** Fragment, weil das beim
  Pfeil der Flight ist. Bei einer Person ist es die Person.
- `_tip_and_far_end` legt anschließend brav eine PCA-Hauptachse durch sie und
  liefert eine „Spitze".

Es gibt also keinen Punkt in der Pipeline, an dem ein Objekt wegen seiner Größe
abgelehnt wird — obwohl der Client genau darauf baut.

**Fix.** Ein neuer `DetectionFailure`, etwa `IMPLAUSIBLE_SHAPE`, wenn der
fusionierte Blob eines von drei Kriterien reißt:

| Maß | Grenze | Warum |
|---|---|---|
| Länge entlang der Hauptachse | `_MAX_DART_LENGTH_MM` | die Konstante *definiert* bereits „gehört nicht mehr zu einem Pfeil"; sie gilt nur noch nicht für die Komponente selbst |
| Fläche in mm² | Obergrenze aus dem Testsatz zu bestimmen | die direkte Formulierung von „zu groß für einen Pfeil" |
| Schlankheit (Länge/Breite) | Boden | ein Pfeil ist dünn, eine Person ist klumpig; unabhängig von der absoluten Größe |

Alle drei sind aus Größen ableitbar, die `_tip_and_far_end` ohnehin schon
berechnet (Projektionen auf die Hauptachse, Breitenprofil).

**Warum zuerst.** Zwei Gründe:

1. Es stoppt den eigentlichen Schaden an der Wurzel — siehe unten.
2. Es ist **offline messbar**. `scripts/detection/run_all.py` fährt die 285 Paare
   des Testsatzes; die Grenze ist erst dann richtig gewählt, wenn die Accuracy
   unverändert bleibt. Kein anderer Schritt hier hat diesen Luxus.

**Der eigentliche Schaden ist nicht die Punktzahl.**
[`core/socket.py`](../../backend/src/app/api/core/socket/socket.py) rollt den
Referenz-Frame bei **jeder** erfolgreichen Erkennung weiter — vor der
Scoring-Kamera-Prüfung und unabhängig davon, ob das Spiel den Dart angenommen
hat:

```python
if dart_detector.trace.aligned is not None:
    detection_store.set(game_id, client_id, dart_detector.trace.aligned)
```

Ein Frame mit einer Person darin wird damit zur Referenz, gegen die jeder
folgende Wurf differenziert wird. Da das Weiterrollen nur bei Erfolg passiert,
verhindert eine Ablehnung in Schritt 1 das automatisch mit.

Im Bestätigungsmodus begrenzt die Rundenwechsel-Rekalibrierung
([multi-device.md §5c](done/multi-device.md#5c-rekalibrierung-anfordern)) das Fenster
auf eine Runde. Bei Auto-Advance nicht — siehe Schritt 3.

**Erwartung.** Der beobachtete Fall verschwindet vollständig, unabhängig davon,
was der Client sendet. Auf dem Testsatz: keine Änderung (das ist das Kriterium).

### Ergebnis (erledigt)

**Die Vormessung hat den Plan oben widerlegt.** Über alle 285 Paare wurden Länge,
Breite und Fläche des fusionierten Blobs aufgezeichnet (`trace.dart_length_mm`
etc.), getrennt nach korrekt und falsch erkannt:

| | n | Median | p95 | Max |
|---|---|---|---|---|
| Länge korrekt | 214 | 102.8 mm | 146.4 | **177.0** |
| Länge falsch | 67 | 97.7 mm | 143.2 | 361.6 |
| Fläche korrekt | 214 | 1088 mm² | 2151 | **3726** |
| Fläche falsch | 67 | 904 mm² | 2509 | 3913 |
| Schlankheit korrekt | 214 | 3.4 | 8.2 | 16.5 (min **1.4**) |
| Schlankheit falsch | 67 | 3.2 | 9.1 | 12.4 (min 1.5) |

Drei Korrekturen daraus:

1. **`_MAX_DART_LENGTH_MM` (90 mm) als Grenze wäre eine Katastrophe gewesen** —
   sie hätte **151 von 214 korrekten** Pfeilen gekostet. Die Konstante misst
   Schwerpunkt-zu-Schwerpunkt zwischen *Wählern*; der fusionierte Blob reicht
   mit den Ausdehnungen seiner Fragmente weit darüber hinaus. Ein echter Pfeil
   wird routinemäßig 100–177 mm lang. Der Kommentar an der Konstante sagt das
   jetzt ausdrücklich.
2. **Schlankheit ist gestrichen.** Sie trennt nichts (Minimum 1.4 bei korrekten
   gegen 1.5 bei falschen) — ein echter Pfeil ist oft klobig, weil der Flight
   breit ist. Eine Grenze darauf wäre reines Risiko ohne Nutzen.
3. **Die Fläche trennt auf diesem Testsatz ebenfalls nicht** (3726 gegen 3913).
   Sie bleibt trotzdem drin, aber aus einem anderen Grund: die Fehlerfälle des
   Testsatzes sind alle *dünne* Fehlfits entlang einer Linie, kein flächiges
   Objekt. Ein Mensch ist flächig, und dafür ist sie die direkte Aussage.

Was eine Längengrenze kostet und bringt:

| Grenze | korrekte verloren | falsche abgefangen |
|---|---|---|
| 90 mm | 151 | 42 |
| 130 mm | 24 | 7 |
| 175 mm | 2 | 1 |
| **200–250 mm** | **0** | **1** |

**Gewählt: `_MAX_BLOB_LENGTH_MM = 250.0`, `_MAX_BLOB_AREA_MM2 = 8000.0`.** Das
1.4-fache des längsten und das 2.1-fache des größten je korrekt erkannten
Pfeils, und weit unter dem, was ein Objekt vor dem Board erzeugt — die
Änderungsmaske ist auf eine Scheibe von 315 mm Radius (≈312 000 mm²) beschnitten.

**Gemessen: 218/285 = 76.5 % vorher wie nachher, `281 → 280 darts located`.**
Genau ein Blob abgelehnt, `pz-light_setup2/throw5/dart1` mit 362 × 105 mm — ein
Fehlfit, der sich an den weißen Board-Zahlen festgemacht und quer über das Board
gelegt hatte, gemeldet als `MISS` statt `D20`. Er war vorher falsch und ist es
weiterhin, nur jetzt aus dem richtigen Grund. Die Debug-Beschriftung in
`07_components.jpg` nennt die Maße und den Ablehnungsgrund.

Am Rande, aber aufschlussreich: **dasselbe Foto in voller Auflösung** — direkt
über den Socket geschickt statt durch `as_client_would_send` — wird korrekt als
`D20` erkannt. Der 362-mm-Blob ist also ein Artefakt der Herunterskalierung, kein
Eigenschaft des Motivs. `run_all.py` ist damit die richtige Messgrundlage: es
bildet ab, was das Handy tatsächlich sendet.

**Was der Testsatz nicht beweisen kann.** Er enthält keine Bilder mit einer
Person vor dem Board. Er belegt also nur die eine Hälfte — dass die Grenze
keinen echten Pfeil kostet. Dass sie den beobachteten Fall fängt, folgt aus der
Geometrie (ein Mensch überdeckt ein Vielfaches von 8000 mm²) und ist erst
belegt, wenn solche Aufnahmen im Satz liegen. Das gehört zur Testdaten-Erhebung
in [todo.md](../todo.md).

---

## 2. Episoden-Höchstwert bricht die Erfassung ab *(Client)*

**Befund.** Der Personen-Filter existiert bereits, mit genau dieser Begründung im
Kommentar — *„a dart lights one or two cells; a person or a whole-board wobble
lights many"* — als `MAX_THROW_BLOCKS = 48` (ein Drittel des 16×9-Rasters). Er
wird aber **nur in `stepIdle`** ausgewertet:

```ts
const localizedThrow = excess >= ARM_BLOCK_EXCESS && this.activeBlocks <= MAX_THROW_BLOCKS;
```

Sobald der Zustand `motion` ist, prüft ihn niemand mehr. `stepMotion` und
`stepSettling` schauen ausschließlich auf `isStill()`.

Damit ergibt sich beim Reinlaufen zwingend:

1. Die Person betritt den Bildrand und belegt dort **wenige** Zellen.
   `excess >= 1`, `activeBlocks <= 48` → **scharf**.
2. Sie läuft vors Board, 100+ Zellen. Der Filter ist zu diesem Zeitpunkt bereits
   aus dem Spiel.
3. Sie bleibt zum Ziehen stehen → aufeinanderfolgende Frames werden gleich →
   `isStill()` → `settling` → nach `SETTLE_FRAMES_REQUIRED = 3` **Erfassung**.

Und bleibt sie *nicht* stehen, greift `MAX_MOTION_FRAMES = 25` (bei
`PROCESS_INTERVAL_MS = 60` etwa 1,5 s) und erfasst als „recall safety net"
**trotzdem**. Es gibt derzeit keinen Pfad, auf dem ein Reinlaufen keinen Frame
erzeugt: die Person wird auf ihrer kleinen Vorderkante eingefangen, und danach
führt jeder Ausgang zur Erfassung.

**Fix.** Der Höchstwert der Episode, nicht der Momentanwert, entscheidet:

- Pro Episode das Maximum von `activeBlocks` mitführen (undekayed — der
  `peakBlocks` in `frame-diff.service.ts` ist mit `PEAK_DECAY = 0.9` geglättet
  und nur für die Anzeige gedacht).
- War es je über `MAX_THROW_BLOCKS`, wird beim Erfassen **verworfen** statt
  gesendet, in die Baseline gefaltet und ein Cooldown gesetzt.
- Derselbe Test muss den `MAX_MOTION_FRAMES`-Ausgang decken, sonst bleibt er das
  Schlupfloch.
- Der Cooldown ist nicht optional: sonst armiert die **Hinterkante** der
  hinausgehenden Person sofort neu — wieder eine kleine, lokalisierte Änderung.
  `COOLDOWN_FRAMES` existiert, wird aber bislang nur bei einer Erfassung gesetzt.

**Warum das den Recall nicht kostet — und wo das Risiko liegt.** Ein Pfeil
belegt ein bis zwei Zellen; 48 sind das Vierundzwanzigfache. Die Regel „was je
global war, war kein Pfeil" kann einen echten Wurf nur dann unterdrücken, wenn
er *während* einer globalen Störung stattfindet — und ein Wurf, während jemand
vor dem Board steht, ist ohnehin nicht wertbar.

Das zu prüfende Risiko: **greift der Wurfarm bei diesem Aufbau ins Bild?** Dann
kann ein echter Wurf die Grenze reißen. Die Antwort steht in der Peak-Verteilung
(siehe unten) und muss vor der Wahl des Schwellwerts vorliegen.

---

## 3. Auto-Advance vom Kameramodus entkoppeln

**Befund.** Der Docstring von `Game.register_dart` hat diesen Fall wörtlich
vorhergesagt:

> *„manual entry advances on its own once the visit is full, while camera
> tracking waits for a confirm tap — otherwise a player walking up to pull their
> darts would be tracked as the next player's visit."*

Die Entwurfsentscheidung ist also längst getroffen. Der Fehler ist, dass
`settings.confirmThrowEnabled()` eine **globale Einstellung** ist statt an den
Modus gekoppelt. Steht sie aus, feuert `maybeAutoAdvance` (`game.service.ts`)
`next_player` sofort nach dem dritten Dart; die Runde ist leer, und der
Personen-Blob wird als **Dart 1 des nächsten Spielers** regulär gebucht.

Derselbe Schalter entscheidet über die Korrektheit der
Rundenwechsel-Rekalibrierung: die verlässt sich darauf, dass der Wechsel *nach*
dem Ziehen der Pfeile kommt ([multi-device.md §5c](done/multi-device.md#5c-rekalibrierung-anfordern)).
Bei Auto-Advance kalibriert sie gegen ein volles Board.

**Fix.** Wenn das Gerät filmt — oder allgemeiner: solange das Spiel eine
Scoring-Kamera hat — ist der Bestätigungs-Tap nicht abwählbar. Ein Tap pro Runde
ist der Preis; er ist zugleich die einzige verlässliche Aussage „das Board ist
jetzt leer", die das System hat.

**Erwartung.** Der Zweig „wird als Dart des nächsten Spielers gebucht" entfällt
ganz, und die Rekalibrierung sieht garantiert ein leeres Board.

---

## 4. Ausdehnung und Dauer statt Zellenzahl *(Client)*

**Befund.** `activeBlocks` ist eine **Anzahl**. Sie unterscheidet nicht zwischen
zwei benachbarten Zellen und zwei Zellen an gegenüberliegenden Bildrändern. Die
eigentlich trennenden Größen sind andere:

| | Pfeil | Person |
|---|---|---|
| räumliche Ausdehnung | 1–2 benachbarte Zellen | zusammenhängende Säule über das halbe Bild |
| Dauer der Episode | 1–2 Frames (Transient) | Sekunden |

Die Dauer wird bereits gemessen — `motionFrames` — aber **genau falsch herum
verwendet**: statt eine lange Episode als unpfeilartig zu werten, garantiert
`MAX_MOTION_FRAMES` bei ihr die Erfassung.

**Fix.** Zwei Merkmale ergänzen, beide billig auf dem bestehenden Blockraster:

- **Bounding-Box der aktiven Zellen** statt nur ihrer Anzahl. Robuster als der
  Zähler, weil er auch den Fall „viele verstreute Zellen durch Lichtwechsel"
  von „ein kompakter neuer Cluster" trennt.
- **Episodendauer** als Merkmal statt als Sicherheitsnetz.

Das ersetzt Schritt 2 nicht, es verfeinert ihn: Schritt 2 ist die grobe,
sichere Ablehnung, dieser Schritt macht die Grenze weniger empfindlich gegen den
gewählten Zahlenwert.

---

## 5. Diff auf die Board-Region beschränken *(Client)*

**Befund.** Die Frame-Differenz läuft über das **ganze** Bild, inklusive Wand,
Umgebung und allem, was seitlich am Board vorbeigeht.

**Fix.** Der Client kennt die Board-Umrisse bereits: `calibration.overlay` liefert
sie als Polylines in normalisierten Koordinaten — dasselbe Mapping, das die
Diff-Canvas und die Debug-Maske ohnehin verwenden. Die Auswertung auf deren
Bounding-Box (mit Rand für den Flight-Überstand) zu beschränken, ist damit fast
gratis.

**Warum trotzdem hinten.** Gegen den beobachteten Fall hilft es **nicht**: wer
die Pfeile zieht, verdeckt das Board selbst. Es beseitigt eine andere Klasse —
„läuft seitlich vorbei", „jemand bewegt sich im Hintergrund" — die konzept.md §4
als „Bewegung neben dem Board" ausdrücklich nennt.

---

## 6. Der abgefallene Pfeil ist eine Null

**Befund.** Prallt ein Pfeil ab oder fällt heraus, gab es Bewegung, aber das Bild
ist danach unverändert. Der Server meldet `NO_CHANGE`, und das ist **punktemäßig
eine Null** — der Wurf hat stattgefunden und zählt.

Genau diese Buchung darf aber nicht automatisch passieren, und
[erkennung.md §3](erkennung.md#no_change-ist-punktemäßig-ein-miss) begründet
warum: `NO_CHANGE` bedeutet auch „es gab gar keinen Wurf", was bei einem
Recall-first-Trigger der häufigere Fall ist. Ein blind gebuchter Nullwurf wäre
dann ein Phantom-Pfeil, der eine Aufnahme des Spielers verbraucht.

Der Detektor kann die beiden **prinzipiell nicht** unterscheiden: beide Male ist
das Bild vor und nach dem Ereignis gleich. Die Information liegt ausschließlich
im *Verlauf* — und den sieht nur der Client.

**Ansatz.** Der Unterschied steht in der Bewegungssignatur, nicht im Standbild:

- Ein **abgeprallter Pfeil** ist ein schneller, kleiner, lokalisierter Transient,
  der über das Board zieht und dann verschwindet — dieselbe Signatur wie ein
  steckenbleibender Wurf, nur ohne bleibende Differenz.
- Ein **Fehlauslöser** ohne Wurf (Lichtwechsel, Wackeln, jemand im Hintergrund)
  hat sie nicht.

Der Client müsste also mitschicken, *was für eine* Bewegung den Trigger
ausgelöst hat — etwa den Spitzenwert und die räumliche Ausdehnung der Episode
(dieselben Größen wie in Schritt 2 und 4). Der Server könnte `NO_CHANGE` dann
qualifizieren: „Bewegung sah nach Wurf aus, nichts steckt" → Null buchen,
gegenüber „nichts deutete auf einen Wurf hin" → verwerfen.

**Warum L und warum hinten.** Es braucht die Merkmale aus Schritt 2 und 4, eine
Protokoll-Erweiterung (`detection_frame` bekommt die Trigger-Metrik), eine
Server-Regel und einen Testsatz, den es noch nicht gibt: Aufnahmen von
Abprallern, mit Wahrheit. Erst danach lässt sich die Regel überhaupt belegen.

Solange das offen ist, bleibt der Abpraller ein Fall für die manuelle Korrektur
am Scoreboard — was ausdrücklich einer der Gründe für dessen Eingabefeld ist
([multi-device.md §1](done/multi-device.md#1-ziel)).

---

## 7. Darts jenseits des dritten verwerfen *(verworfen)*

**Idee.** Der Server verwirft Darts, die über die drei bereits registrierten
hinausgehen.

**Warum verworfen: das gibt es schon.** `Game.register_dart`:

```python
if self.winner is not None or self.darts_remaining <= 0:
    return
```

Der Docstring nennt den Zweck wörtlich — *„which also absorbs an over-eager
camera trigger"*. Es ist also nichts zu bauen, und es hilft trotzdem nicht:

- Bei **Auto-Advance** ist die Runde nach dem dritten Dart sofort leer, der Blob
  wird also regulär gebucht statt geschluckt (→ Schritt 3).
- Im **Bestätigungsmodus** wird er zwar geschluckt, aber der Referenz-Frame rollt
  trotzdem auf das Personenbild weiter (→ Schritt 1). Der Schaden entsteht
  unterhalb der Spielregeln.
- Ein Fehlauslöser **innerhalb** einer Runde — jemand greift nach dem ersten
  Dart ins Bild — wird von der Regel gar nicht erfasst.

Die Regel behandelt ein Symptom auf der Ebene der Spielregeln, während die
Ursache eine Ebene tiefer liegt.

Den zweiten dieser Einwände hat inzwischen Schritt 8 erledigt — allerdings von
der anderen Seite: nicht indem der Server den Dart verwirft, sondern indem der
Client den Frame gar nicht erst schickt.

---

## 8. Kein Frame, solange die Runde keinen Dart annimmt *(Client)*

**Befund.** Im Bestätigungsmodus bleibt die Schleife nach dem dritten Dart voll
aktiv. Der Spieler geht zum Board, der Trigger feuert, der Server erkennt einen
„Pfeil" — und über den drei echten erscheint eine **vierte** Wurflinie.

Die dafür vorgesehene Selbstheilung greift nicht. `_handle_throw_frame` pusht den
`game_state` bewusst auch dann, wenn das Spiel den Dart geschluckt hat, damit
*„the camera trims its drawn outlines against this state"*. Nur erhöht
`register_dart` beim vierten Dart die `revision` nicht — der Client verwirft den
Push in `GameService.setState` als veraltet, der `reconcileRound`-Effect läuft
nie, und die vierte Linie bleibt stehen.

**Fix.** Zwei Stellen, beide im Client:

1. `DetectionService.acceptsThrows` spiegelt die Vorbedingung des Servers
   (`winner is None and darts_remaining > 0`). Die Schleife in
   `frame-diff.service.ts` sendet nur, solange sie wahr ist. Der Zustandsautomat
   läuft weiter, damit er im Takt des Bildes bleibt — zurückgehalten wird nur
   der Frame.
2. `appendDart` zeichnet nichts, wenn die Runde keinen Dart mehr annimmt. Das
   fängt den Frame ab, der beim Schließen des Tors schon unterwegs war:
   Kodierung, Netz und Detektion dauern länger als das 60-ms-Raster der
   Schleife.

Weil das Tor aus dem Spielstand abgeleitet ist, öffnet **Zurück** es von selbst
wieder — der Undo hebt `darts_remaining` zurück auf 1. Ein Bust schließt es
ebenso, weil `darts_remaining` dort 0 ist; auch das deckt sich mit dem Server.

**Verhältnis zu Schritt 7.** Dort ging es darum, dass der *Server* überzählige
Darts verwirft — das tut er längst. Einer der Einwände war, dass der
Referenz-Frame trotzdem auf das Personenbild weiterrollt: `_handle_throw_frame`
setzt ihn, bevor überhaupt gebucht wird. Genau das behebt das Tor, ein nie
gesendeter Frame kann den Referenz-Frame nicht verschieben. Die beiden anderen
Einwände bleiben und gehören woanders hin: bei **Auto-Advance** ist die Runde
sofort wieder leer und das Tor damit offen (→ Schritt 3), und ein Fehlauslöser
**innerhalb** einer Runde wird davon gar nicht berührt (→ Schritte 2, 4, 5).

**Nebeneffekt.** Die Badge zeigt „Tracking pausiert" statt „Bereit", solange
nichts gesendet wird. Ohne das sieht ein bewusst ignorierter Wurf aus wie ein
übersehener.

---

## 9. Kleine MISS-Blobs verwerfen *(Server)*

**Befund.** Zwei Testspiele im Betrieb (08.09., ein Setup, 0.95 px/mm,
Wolfram-Pfeile), `game_events` über Visit-Replay und `judge` ausgewertet: 135
gebuchte Darts, davon **65 korrekt, 18 falsch, 52 Phantome**. Das Reinlaufen ist
dabei kein Thema mehr — `implausible_shape` fing es neunmal ab, das Tor aus
Schritt 8 hält. Die Phantome sind eine andere Klasse:

- **42 von 52 haben unter 500 mm² Fläche**, ein echter Pfeil hier 900–2000 mm².
- Fast alle werden als `MISS` gebucht, Spitze bei r ≈ 180–230 mm.
- 4–5 Fragmente, das größte hält nur 30–50 % des Blobs: die Fusion fädelt Krümel
  zu einer 100 mm langen Linie.
- Sie kehren **Visit für Visit an derselben Stelle** wieder, etwa (−8, 213) mm
  über der 20. Die Kamera hat sich dabei nicht bewegt (`alignment_shift_px`
  0.2–0.5): es sind lokale Registrierungs-Reste an den aufgedruckten Zahlen
  (erkennung.md §5.11, §5.13), kein globaler Versatz, den eine bessere
  Ausrichtung beheben würde.
- Die Hälfte fällt in die ersten 5 s nach dem Rundenwechsel.

Nebenbei schickt der Client rund **15 Frames pro Minute, die `no_change`
ergeben** — jeder davon eine Gelegenheit für so einen Rest.

Die übrigen 8 Phantome sind normal große Blobs: derselbe echte Pfeil, nach
einem Undo ein zweites Mal gebucht (identische Position und Fläche). Die
Ursache ist offen; der Undo fasst den Referenz-Frame nicht an.

**Warum keine reine Flächengrenze.** Über die 285 Testpaare kostet sie zu viel,
weil die schwarzen Pfeile und die fernen Setups dort deutlich kleinere Blobs
liefern:

| Regel | Testsatz: korrekte verloren | Live: Phantome abgefangen | Live: korrekte verloren |
|---|---|---|---|
| Fläche < 400 | 11 | 41 / 52 | 1 |
| Fläche < 600 | 34 | 42 / 52 | 2 |
| Fläche < 400 und größtes Fragment < 60 % | 2 | 28 / 52 | 1 |
| **Fläche < 400 und Spitze > 170 mm** | **2** | **38 / 52** | **1** |
| Fläche < 600 und Spitze > 170 mm | 6 | 39 / 52 | 1 |

**Gewählt: `MISS` und Fläche < 400 mm² → `NO_CHANGE`.** Die Bedingung auf den
`MISS` macht die Regel punktneutral: sie kann nur eine Null verwerfen, nie einen
Treffer. Die zwei verlorenen Testpaare sind echte Fehlwürfe im Surround, der eine
verlorene Live-Dart ebenso. Der Detektor meldet `NO_CHANGE` und nicht
`IMPLAUSIBLE_SHAPE`, weil es inhaltlich dasselbe ist wie ein zu kleiner Blob; die
Metriken (`dart_area_mm2 > 0`) unterscheiden die beiden Fälle weiterhin.

**Gemessen:** 226 → **224 / 285**, `281 → 274 darts located`. Weggefallen sind
die zwei Fehlwürfe und fünf Fehlfits, die ohnehin falsch waren.

**Nachtrag: die Referenz rollt trotzdem weiter.** Im ersten Testlauf mit der
Regel (12.09.) zeigte sich eine Nebenwirkung. Ein verworfener Blob ließ den
Referenz-Frame stehen, also blieb die Änderung für immer in der Differenz: ein
Fehlwurf im Surround wurde in Visit 11 elfmal hintereinander mit derselben
Fläche (~300 mm²) wiedergefunden und schließlich, etwas größer angekommen, doch
noch als `MISS` gebucht — nachdem die 0 schon von Hand eingetragen war. Seitdem
setzt `socket.py` bei `trace.rejected_miss` den ausgerichteten Frame als neue
Referenz, bucht aber nichts. Das ist so punktneutral wie die Regel selbst, und
es ist das, was `run_all.py` offline ohnehin tut (dort rollt jeder
ausgerichtete Frame weiter). In der aufgezeichneten Wurfserie fehlt ein solcher
Frame, weil deren Ground Truth gegen die gebuchten Darts ausgerichtet wird; die
Offline-Kette weicht dort also um einen Rest ab, der keinen Punkt wert ist.

**Was bleibt.** 14 Phantome übersteht die Regel: die 8 doppelt gebuchten Pfeile
und einige größere Blobs mit Kameraversatz über 1 px. Der Trigger selbst ist
unverändert — die Rate der Fehlsendungen senkt das nicht, es macht sie nur
folgenlos.

---

## Was gemessen werden muss

Für die Client-Schritte gibt es keinen Offline-Testsatz wie bei der Detektion.
Die Zahl muss im Betrieb entstehen, und das Instrument existiert bereits: das
Debug-Panel zeigt **Peak Blöcke** und das Ereignis-Log jeden Versand mit der
Antwort des Servers (`frame-diff.service.ts`, `detection.service.ts`).

Aufzunehmen:

1. **Zwei Verteilungen von `peakBlocks`** — echter Wurf gegen Reinlaufen, je
   einige Dutzend Episoden. Sie beantworten, ob 48 der richtige Schnitt ist und
   ob der Wurfarm ins Bild greift. **Vor** Schritt 2.
2. **Fehlauslöserrate** vorher/nachher: Anteil der gesendeten Frames, die keinem
   Wurf entsprechen. Das ist die Zahl, die konzept.md §4 unter
   „Trigger-Zuverlässigkeit" verlangt und zeitplan.md Phase 4 auswertet.
3. **Recall**: Anteil der echten Würfe, die einen Frame erzeugt haben. Muss bei
   100 % bleiben — das ist die Bedingung, unter der die ganze Auslegung steht.

Punkt 2 und 3 zusammen sind ein eigenständiges Ergebnis für die Arbeit: sie
zeigen den Zielkonflikt des Triggers als Zahlenpaar, nicht als Behauptung.
