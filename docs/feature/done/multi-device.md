# Geteilte Spiel-Session (Multi-Device)

Plan für das Teilen einer laufenden Session mit weiteren Geräten: ein zweites
Handy tritt bei, zeigt den Spielstand und kann Würfe buchen — während das
Kamera-Handy unberührt bleibt (jede Berührung verwackelt die Kalibrierung).
Ergänzt [roadmap.md §4](../../roadmap.md#4-http--websocket-protokoll) um das
Verbindungsmodell.

> **Stand:** Schritte 1–5 aus §7 sind umgesetzt: Room-Registry mit Broadcast,
> `revision` auf dem Snapshot, alle Mutationen als Socket-Kommandos, der Socket
> hängt am Spiel statt an der Kamera, und Join-Route plus Teilen-Dialog sind da.
> Beim Beitreten wird die Rolle gewählt; ein Gerät ohne Kamera bekommt die
> virtuelle Scheibe (§4a). Geräte haben eine serverseitige `client_id`, an der
> die Rolle hängt (§5). Offen ist der Reconnect (§7.7).
>
> **Mehrere Kameras** trägt das Backend seit §5a: Kalibrierungs- und
> Detection-Store hängen an `(game_id, client_id)`, und genau eine Kamera pro
> Spiel bucht. Im Join-Screen ist „Mit Kamera" weiterhin deaktiviert — das ist
> nur noch ein Frontend-Schritt. Die Fusion zweier Ansichten zu *einer*
> Schätzung ist hergeleitet, aber nicht gebaut (§5b).
>
> **Rekalibrierung** kann seit §5c jedes Gerät im Raum anstoßen — auch eines
> ohne Kamera — und der Rundenwechsel tut es von selbst.

---

## 1. Ziel

Zwei Rollen an einer Session:

- **Kamera** — das Gerät, das das Board filmt. Läuft wie heute: Kalibrierung,
  Frame-Differenz, getriggerte Standbilder.
- **Scoreboard** — jedes weitere Gerät. Zeigt den Spielstand und eine gezeichnete
  Dartscheibe mit den erkannten Treffern (§4a), und kann Würfe manuell buchen,
  undo und Rundenwechsel auslösen. Sendet keine Frames.

Die Rolle beschränkt **nicht**, was ein Gerät am Spiel ändern darf: Das
Scoreboard ist ausdrücklich auch der manuelle Korrekturweg bei Fehlerkennungen.
Sie steuert nur, ob das Gerät die Kamera-Pipeline startet.

Sie ist eine Eigenschaft des **Geräts**, nicht des Spiels: das Handy in der
Halterung filmt über Spiele hinweg, das auf dem Tisch zählt. Entsprechend liegt
sie serverseitig am Gerät (§5) und nicht am Spiel. Gesetzt wird sie ausschließlich
auf dem Weg in ein Spiel — beim Anlegen (Kamera) oder beim Beitreten (gewählt) —
und danach nicht mehr: die Rolle wählt die Ansicht für das ganze Spiel und kann
so nicht unter einer laufenden Kamera wegbrechen.

Mehrere Geräte können die Kamera-Rolle haben. Serverseitig läuft die Erkennung
dann aus mehreren Perspektiven, gebucht wird aber nur eine davon (§5a); wie
daraus eine gemeinsame Schätzung würde, skizziert §5b.

---

## 2. Ausgangslage

Der WebSocket ist bereits pro Spiel adressiert (`/api/ws/games/{game_id}`) — die
Room-Struktur existiert also schon, wird aber nicht genutzt: Jede Verbindung
wird isoliert behandelt, jede Antwort geht per `websocket.send_text()` an genau
den Sender zurück. Es fehlt die Registry `game_id → Verbindungen`.

Zweitens hängt der Socket im Frontend an der Kamera: `GameSessionService`
verbindet ihn in `startCamera()`. Ein Gerät ohne Kamera hätte damit gar keine
Verbindung. Das ist die strukturelle Änderung auf Client-Seite.

---

## 3. Protokoll: was über den Socket läuft

Alle **Mutationen** wandern auf den Socket, der **Lebenszyklus** bleibt HTTP.

| bleibt HTTP | wird WS-Command |
|---|---|
| `POST /api/games` — vor dem Spiel gibt es keine `gameId`, an die ein Socket andocken könnte | `register_dart` (ersetzt `POST /{id}/darts`) |
| `GET /api/games/{id}` — Join-Validierung und Restore nach Reload, mit sauberem 404 bei totem Link | `undo` (ersetzt `POST /{id}/undo`) |
| | `next_player` (ersetzt `POST /{id}/next-player`) |

Begründung für die Verschiebung: Bei HTTP bekäme der mutierende Client seine
Antwort, alle anderen brauchen trotzdem den Broadcast — es gäbe **zwei** Wege,
auf denen State ankommt, mit unterschiedlicher Latenz. Bucht Gerät A einen Dart
während Gerät B undo drückt, kann eine HTTP-Response mit älterem Snapshot einen
neueren Push überschreiben. Ein Schreibpfad plus Broadcast löst das strukturell.

Zusätzlich bekommt `GameStateDto` eine monoton steigende `revision` pro Spiel;
der Client verwirft jeden Snapshot, der älter ist als der bereits gecachte. Das
macht verbleibende Races gutartig, unabhängig vom Transportweg.

Die Revision entscheidet außerdem, ob überhaupt gesendet wird: ein Kommando, das
nichts ändert, löst keinen Broadcast aus. Das betrifft den vierten Dart einer
Runde, ein `undo` ohne Ziel — und den Fall, dass zwei Geräte dieselbe Runde
gleichzeitig beenden. Damit das zweite `next_player` folgenlos bleibt, ist der
Rundenwechsel im Domänenmodell an eine nicht-leere Runde gebunden: eine Runde,
in der niemand geworfen hat, lässt sich nicht beenden.

### Benennung der beiden Richtungen

Die Unions heißen `ClientMessage` und `ServerMessage` — benannt nach dem
**Absender**, nicht nach dem Betrachter. „Incoming" und „outgoing" wären in
Frontend und Backend genau gegenläufig: Was der Server empfängt, sendet der
Client. Mit der Benennung nach Absender bedeutet `ClientMessage` auf beiden
Seiten dasselbe.

Das `type`-Literal steht am einzelnen DTO, die Union sagt nur, wer dazugehört.
Auf der eingehenden Seite ist das Literal Pflichtfeld (es ist der Diskriminator,
gegen den validiert wird), auf der ausgehenden ein Default — der Server weiß
immer, was er sendet.

Es gibt keine Message-Wrapper um DTOs: `GameStateDto` trägt sein `type` selbst
und ist damit zugleich HTTP-Antwort und Socket-Nachricht. Ein Gerät sieht den
Spielstand also in derselben Form, egal auf welchem Weg er ankam.

### Adressierung der Server → Client-Nachrichten

| Nachricht | Empfänger | Warum |
|---|---|---|
| `game_state` | alle im Room | der geteilte Spielstand |
| `client_state` | nur der Sender | wer *dieses* Gerät ist: `clientId` und Rolle (§5) |
| `calibration_result` | nur der Sender | gehört zu *dessen* Kamerabild |
| `calibration_status` | nur das Gerät, das die Rekalibrierung angefordert hat | es wartet auf die Antwort, und niemand darf zu einem Versuch zwei Nachrichten bekommen (§5c) |
| `calibration_requested` | alle **Kameras** im Room | nur wer ein Bild hat, kann die Aufforderung beantworten (§5c) |
| `detection_result` | nur der Sender | Overlay-Polylines liegen im Pixelraster dieser Kamera |
| `presence` | alle im Room | wie viele Geräte, welche Rollen (optional) |

Damit gibt es vier Zustellwege statt zwei: `send` an das Gerät, dessen Nachricht
gerade beantwortet wird, `send_to_client` an ein *anderes*, namentlich genanntes,
`broadcast` an den Raum und `broadcast(role=…)` an alle, die eine Aufgabe teilen.

---

## 4. Umsetzung

### Backend

1. **`core/services/game_hub.py`** (neu) — Registry `game_id → set[Connection]`,
   wobei `Connection` den WebSocket, die `client_id` und die Rolle hält.
   Methoden: `join`, `leave`, `send`, `broadcast`.
2. **`core/socket.py`** — Dispatcher wächst um die drei Command-Typen. Die
   if/elif-Kette weicht einem Dict `type → handler`. Jeder Handler, der das
   Spiel verändert, endet mit einem `broadcast` des `game_state`; das gilt auch
   für den bestehenden Detection-Pfad, der den State heute selbst sendet.
   Domain-Logik bleibt unverändert in der `Game`-Entity.
3. **`features/game/games.py`** — schrumpft auf `create` und `get`.

### Frontend

4. **Socket-Lebenszyklus von der Kamera lösen.** Der Socket hängt künftig an
   „es gibt ein aktives Spiel", nicht an „die Kamera läuft": `GameService`
   verbindet in `createGame()` und `ensureRestored()`, `GameSessionService`
   nutzt die bestehende Verbindung nur noch.
5. **Join-Route** `/game/join/:gameId` — `GET /api/games/{id}`, bei Erfolg
   `gameId` persistieren und nach `/game` navigieren, bei 404 Hinweis, dass das
   Spiel nicht mehr existiert.
6. **Teilen-Dialog** ersetzt den Platzhalter in `GameTopBarComponent.share()`:
   QR-Code, Link und Copy-Button. Der QR ist nicht Kosmetik — eine LAN-IP-URL
   auf einem zweiten Handy abzutippen ist der Punkt, an dem das Feature sonst
   ungenutzt bleibt. `navigator.share()` wird genutzt, wo verfügbar.
7. **Rolle** wird auf dem Join-Screen gewählt — nicht im Link kodiert. Der Link
   sagt *welches Spiel*, das Gerät weiß, *wo es gleich liegt*; und wer den Link
   verschickt, weiß nicht, was der Empfänger damit vorhat. Sie liegt
   serverseitig am Gerät (§5) und entscheidet, ob das Gerät die Kamera-Kachel
   oder die virtuelle Scheibe zeigt.

   Der Join-Screen bietet beide Optionen nebeneinander an, „Mit Kamera" ist
   deaktiviert (§5a). Das Anlegen eines Spiels setzt die Kamera-Rolle, weil das
   Gerät aus dem vorigen Spiel noch Scoreboard sein kann — und weil es sonst
   keinen Weg zurück zur Kamera gäbe.

   Der Join-Screen lädt das Spiel zunächst nur (`GameService.load`) und tritt
   dem Room erst nach der Wahl bei (`connect`) — ein Gerät, das umkehrt, war nie
   drin. Die Rolle folgt unmittelbar als `set_role`-Kommando.

---

## 4a. Virtuelle Dartscheibe

Das Scoreboard zeigt an der Stelle, wo das Kamera-Gerät sein Videobild hat, eine
gezeichnete Scheibe mit den erkannten Einschlägen: die aktuelle Runde groß und
in Wurfreihenfolge nummeriert, alles davor als blasse Punkte.

Der Grund ist die Perspektive. Die Kamera steht seitlich im Winkel — ihr Bild
beantwortet „wurde etwas erkannt", aber nicht „wo genau". Die gezeichnete Scheibe
zeigt denselben Wurf frontal und ist damit die eigentliche Kontrolle: sitzt der
Punkt im Triple-Feld, das gebucht wurde?

Dafür reist die Trefferposition auf dem Spielstand mit:

- `game/domain/dart.py` bekommt ein `position: tuple[float, float] | None` in
  Board-Millimetern. Der Socket füllt es beim erkannten Wurf aus `tip_board`.
- Manuell gebuchte Darts haben `None` — das Feld ist bekannt, der Punkt darin
  nicht. Die Ansicht sagt das ausdrücklich, statt den Wurf stumm wegzulassen.

Das ist bewusst der **Spielstand** und nicht `detection_result`: Letzteres geht
nur an die sendende Kamera und liegt in deren Pixelraster (§3). Board-Millimeter
sind dagegen kameraunabhängig — jedes Gerät im Room kann sie zeichnen, und mit
einer zweiten Kamera ändert sich daran nichts.

Und zwar **ausschließlich** dort. `detection_result` trug die Position anfangs
zusätzlich als `tipBoard` mit, ungelesen; das ist entfernt. Damit spricht jede
Nachricht genau ein Koordinatensystem:

| | Raum | Frage | wer zeichnet |
|---|---|---|---|
| `detection_result.overlay` | 0..1 der Bildgröße | wo im Bild *dieser* Kamera | Overlay übers Video |
| `DartDto.position` | Board-Millimeter ab Bull | wo auf dem physischen Board | virtuelle Scheibe, jedes Gerät |

Die naheliegende Vereinheitlichung — auch die Board-Position auf 0..1 — wäre
schlechter. Millimeter ist die Einheit, in der die Zahl etwas bedeutet: die
Radien in `board_geometry.py` sind mm, und die geplante Heatmap-Auswertung
(konzept.md §5) ist eine mm-Auswertung. Vor allem aber hieße `[0.5, 0.5]` dann
im einen Fall „Bildmitte" und im anderen „Bullseye" — zwei Werte, die aussehen
als wären sie austauschbar, obwohl sie es nie sind. Die virtuelle Scheibe
verbraucht die mm ohnehin direkt: `toSvg` ist nur ein y-Flip, und die `viewBox`
ist in denselben Einheiten aufgespannt.

Die Geometrie (Radien, Sektorreihenfolge, Farbwechsel) ist im Frontend
gespiegelt, weil gezeichnet wird, nicht gerechnet — gewertet wird weiterhin
ausschließlich serverseitig.

### Würfe, die neben dem Board gelandet sind

Die Detektion sucht bis 225 mm hinaus, damit ein Pfeil im Surround überhaupt
*gefunden* wird ([erkennung.md §2.1](../erkennung.md)) — die gezeichnete Scheibe
reicht aber nur bis 200 mm. Ein Punkt darüber hinaus lag deshalb am Rand oder
ganz außerhalb: teils angeschnitten, teils gar nicht sichtbar.

Statt ihn zu verwerfen oder auf den Rand zu klemmen, zeigt die Ansicht für einen
Treffer jenseits der Scheibe einen **Pfeil auf einem Randring** (Radius 202),
gedreht in die Richtung, in die der Wurf gegangen ist, mit derselben Ziffer und
Farbe wie ein normaler Marker. Über die 20 geworfen heißt also: kleiner Pfeil
über der 20, nach oben zeigend. Die Richtung ist das, was von so einem Wurf
übrig bleibt und noch etwas aussagt; der genaue Abstand nicht.

Damit dieser Ring und die Beschriftungen am Rand nicht angeschnitten werden, ist
die `viewBox` von der Scheibe entkoppelt: die Scheibe bleibt bei Radius 200, die
`viewBox` spannt ±216. Das ist auch der Grund, warum die Randmarkierungen
mittig auf ihrem Punkt sitzen statt wie die inneren an einer Ecke zu hängen — an
einer Textgrundlinie aufgehängt ragen sie über den Rand hinaus.

---

## 5. Geräte-Identität (`client_id`)

Der Server kennt jedes Gerät unter einer `client_id` und hängt daran, was zum
Gerät gehört — heute die Rolle, später Kamera-Zustand und Statistiken. Ein
`Client` ist ein **Gerät**, keine Person: Kalibrierung und Referenzbild gehören
zu einer Kamera in einer Position, zwei Handys derselben Person sind also zwei
Clients. Kommen später Accounts, tritt eine `user_id` **neben** die `client_id`,
sie ersetzt sie nicht.

**Woher sie kommt.** Der Server vergibt sie, ohne eigenen Endpoint: der erste
Connect eines Geräts läuft ohne `clientId`, der Server legt einen Client an und
antwortet mit `client_state`, das die Id trägt. Ab dann schickt der Client sie
als Query-Parameter mit. Damit ist der Server der Aussteller — was er bleiben
muss, sobald die Id eine DB-Row ist.

Eine Id, die der Store nicht kennt, wird **übernommen statt ersetzt**. Das ist
der Fall nach jedem Server-Neustart, im Dev-Betrieb also ständig; ein Gerät, das
dort seine Identität verliert, verliert alles, was daran hängt. Die Rolle ist
danach zwar wieder der Default — aber mit dem Store ist auch das Spiel weg, die
Session also ohnehin zu Ende.

**Die `clientId` ist der ganze Handshake.** Nichts sonst steht in der URL, und
das ist die Regel, nicht der Zufallsstand: alles, was der Server über das Gerät
weiß, hängt an dieser Id, also hat es keinen Grund, im Query-String noch einmal
aufzutauchen. Sonst wächst der Handshake mit jeder Geräte-Eigenschaft mit.

**Geändert wird die Rolle per Kommando** (`set_role`), nicht beim Verbinden. Ein
Connect *beantwortet* nur, was das Gerät ist. Die Alternative — sie aus der
Verbindung ableiten, etwa „wer zuerst im Raum ist, ist Kamera" — sieht
bequemer aus und ist falsch: das Kamera-Handy sperrt kurz den Bildschirm, das
Scoreboard hält den Raum allein, und beim Reconnect ist die Kamera stumm zum
Scoreboard geworden. Eine abgeleitete Rolle rät; eine kommandierte gilt.

Gesendet wird `set_role` genau auf dem Weg in ein Spiel: beim Anlegen (Kamera)
und beim Beitreten (gewählt). Das Gerät setzt sie lokal sofort, damit die
Ansicht etwas zu zeichnen hat; die Bestätigung des Servers ist maßgeblich und
kommt geordnet **nach** dem `client_state` des Handshakes, das noch die alte
Rolle trug.

**Was das an Client-Speicher spart.** Die Rolle liegt auf dem Client-Record, der
den Socket überlebt: ein neu verbundenes Gerät bekommt sie im Handshake zurück.
Damit muss der Browser sie nicht mehr halten, und im localStorage stehen nur
noch zwei **Identifikatoren** — `gameId` und `clientId` — statt Zustand. Der
Preis ist ein kurzer Moment beim Kaltstart, in dem die Rolle noch nicht
beantwortet ist; die Spielansicht zeigt dort einen Platzhalter. Wer eine Rolle
gerade gewählt hat, sieht sie sofort und bekommt sie gleich darauf bestätigt.

Die Rolle ist damit auch serverseitig durchsetzbar: Frames von einer Verbindung,
die nicht Kamera ist, werden verworfen.

**Warum nicht auch das Spiel am Client-Record?** Weil beide dann dieselbe
Lebensdauer vortäuschen würden: die Rolle ist gerätefest (§1), die
Spielzugehörigkeit flüchtig. Und weil Zugehörigkeit eine *Beziehung* ist, kein
Attribut des Geräts — der `GameHub` beantwortet sie bereits für alles, was
verbunden ist. Zu gewinnen wäre ein localStorage-Eintrag; die `gameId` braucht
das Frontend ohnehin zur Laufzeit (Teilen-Dialog, Join-Link, Routing).

---

## 5a. Mehrere Kameras an einem Spiel

Alles, was eine Kamera an Zustand hat, hängt an `(game_id, client_id)`:
`calibration_store` die Homographie, `detection_store` das Referenzbild. Der
Grund ist in beiden Fällen derselbe — das **Pixelraster**. Zwei Handys sehen
dasselbe Board durch verschiedene Homographien, also ist ein Bild des einen kein
Referenzbild, gegen das das andere differenzieren könnte. Jede Kamera rollt ihr
eigenes weiter, auch die, deren Erkennung nicht gebucht wird. Die Debug-Dumps
sind aus demselben Grund nach Kamera getrennt: ein Wurf hinterlässt zwei Spuren,
und die auseinanderhalten zu können ist der Zweck.

**Genau eine Kamera bucht** (`detection/services/scoring_camera.py`). Ohne diese
Regel ruft jede Kamera, die den Wurf sieht, `register_dart` — und die Runde
füllt sich doppelt so schnell, *ohne dass irgendetwas einen Fehler meldet*: ein
Dart jenseits des dritten wird von `Game.register_dart` geschluckt, nicht
abgelehnt. Bei zwei Kameras heißt das, dass nach anderthalb echten Würfen der
dritte spurlos verschwindet — ein Fehler, der wie eine Fehlerkennung aussieht,
aber keine ist.

Beansprucht wird die Rolle bei der **ersten erfolgreichen Kalibrierung**, dem
frühesten Moment, in dem eine Kamera überhaupt etwas erkennen könnte, und danach
nicht wieder abgegeben. Ein Gerät, das kurz wegbricht und mit derselben
`client_id` zurückkommt, behält sie — die Übergabe mitten in einer Runde würde
sonst genau den Wurf doppelt buchen, der gerade in der Luft ist. Der Preis: ein
Spiel, dessen buchende Kamera nie zurückkommt, wird nicht mehr automatisch
gezählt. Das ist derselbe Zustand wie bei einer einzelnen Kamera, die ausfällt.

Die nicht buchenden Kameras erkennen **vollständig** weiter und bekommen ihr
eigenes `detection_result`. Das ist der Punkt: so entstehen die Paare
unabhängiger Beobachtungen desselben Wurfs, auf denen eine spätere Fusion
aufsetzen würde.

**Bewusst nicht gelöst:** eben diese Fusion. Der Ansatz dafür steht in §5b, die
Begründung, warum er hier noch nicht implementiert ist, am Ende davon.

**Nicht umgesetzt (Frontend):** „Mit Kamera" ist im Join-Screen noch deaktiviert
(`cameraJoinAvailable`), es schickt also bislang nichts einen zweiten
Kamerastream. Geprüft ist das Backend über zwei rohe Sockets mit je einem
eigenen Testdaten-Setup.

---

## 5b. Ausblick: eine Schätzung aus zwei Ansichten

Skizze des Verfahrens, mit dem zwei Kameras zu *einem* Ergebnis kämen, statt zu
zwei, zwischen denen niemand entscheiden kann. Nicht implementiert; hier
festgehalten, weil die Herleitung erklärt, wo die Grenze des Einzelkamera-
Ansatzes liegt (vgl. PEELA,
[roadmap.md §6.4](../../roadmap.md#64-vergleichs--end-to-end-ansätze)).

### Der Restfehler ist kein Projektionsfehler

Die Spitze liegt **in** der Board-Ebene. Für Punkte auf der Ebene ist eine
Homographie exakt — keine Parallaxe, kein Winkelfehler, nichts, was eine zweite
Kamera geometrisch verbessern könnte. Bei perfekt getroffenem Spitzen-Pixel wäre
`tip_board` perfekt, mit einer einzigen Kamera.

Der Fehler steckt also nicht in der Abbildung, sondern in der **Sichtbarkeit**:
welches Pixel *ist* die Spitze. Sie steckt im Board, verdeckt vom eigenen
Barrel, von Nachbarpfeilen, vom Schatten. Was als Blob-Ende gemessen wird, ist
bei schrägem Blick oft die Silhouette des Barrels — und der steht 40–50 mm aus
der Ebene heraus, wofür die Homographie eben *nicht* mehr gilt. Der Fehler
wächst mit der Schrägheit der Kamera.

Anders gesagt: unbekannt ist nicht die Richtung des Pfeils, sondern **wo entlang
des Schafts die Spitze sitzt**. Genau diese eine Größe muss die zweite Ansicht
liefern.

### Die Achsengerade durch die Homographie

Eine Homographie bildet Geraden auf Geraden ab. Schickt man die Bildgerade der
Pfeilachse (`Dart.axis_image`, beide Endpunkte) durch `H`, erhält man eine
Gerade **g** in Board-Millimetern — und die hat eine exakte Bedeutung:

> Die echte Spitze liegt auf `g`.

Denn die räumliche Pfeilachse projiziert sich auf die Bildgerade; die Spitze
liegt auf dieser Achse *und* in der Board-Ebene, also auf `H`(Bildgerade). Das
gilt unabhängig von Kamerawinkel und Barrel-Überstand — und ohne dass die Spitze
je sichtbar gewesen sein muss.

Mit zwei Kameras:

```
g_A = H_A(Achse in Bild A)     →  Spitze liegt auf g_A
g_B = H_B(Achse in Bild B)     →  Spitze liegt auf g_B
Spitze = g_A ∩ g_B
```

Zwei Geraden in einer Ebene, ein Schnittpunkt.

Der Punkt daran ist nicht, zwei Fehler zu mitteln, sondern **einen Freiheitsgrad
zu eliminieren**: jede Kamera steuert bei, was sie gut weiß — die Richtung des
Schafts, ablesbar am unverdeckten Barrel — und nichts von dem, was sie schlecht
weiß. Die Position entlang des Schafts taucht in der Rechnung nicht mehr auf.

### Was es *nicht* braucht

Keine Intrinsics, keine Relativpose der Kameras, keine Triangulation, keine
Stereo-Rektifizierung. Nur die beiden Homographien, die ohnehin pro Kamera
vorliegen (§5a), und die Achse, die der Detektor ohnehin liefert.

Das ist der praktische Unterschied zur klassischen 3D-Rekonstruktion: die würde
`K` pro Gerät verlangen, und Handykameras sind da unangenehm — Autofokus
verändert die effektive Brennweite zwischen Frames, viele Geräte rechnen
Stabilisierung und Verzeichnungskorrektur dazwischen. Der projektive Weg umgeht
das vollständig.

Ausdrücklich **nicht** gemeint ist ein 3D-Modell des Pfeils. Dichte
Stereo-Rekonstruktion auf einem dünnen, glänzenden, texturlosen, sich selbst
verdeckenden Objekt vor periodisch gemustertem Hintergrund ist ungefähr der
Worst Case für Block-Matching. Rekonstruiert wird genau eine Gerade.

### Konfidenz fällt dabei ab

Der Fehler im Schnittpunkt skaliert mit `1/sin(α)`, wobei `α` der Schnittwinkel
von `g_A` und `g_B` ist. Damit ist der Winkel ein **berechenbares Gütemaß**, kein
heuristischer Score: bei flachem Schnitt stehen die Kameras für diesen Pfeil zu
ähnlich, das Ergebnis ist schlecht konditioniert — und das ist bekannt, *bevor*
gebucht wird. Sinnvoller Fallback dort: die Einzelkamera-Schätzung der buchenden
Kamera, oder Rückfrage beim Nutzer.

### Grenzen

- **Entartung.** Liegt die Pfeilachse in der Ebene durch beide Kamerazentren,
  fallen `g_A` und `g_B` zusammen. Zwei Kameras brauchen also spürbare
  Winkelöffnung, sonst wird es für einen Teil der Wurfrichtungen dünn — was der
  Prämisse des einfachen Aufbaus entgegensteht und mitgemessen werden müsste.
- **Rauschen.** Exakt schneiden sich die Geraden nie. Sauber ist der Punkt mit
  minimaler gewichteter Distanz zu allen Geraden (kleinste Quadrate); bei zwei
  Geraden fällt das mit dem Schnittpunkt zusammen, bei mehr Kameras
  verallgemeinert es sich ohne Änderung am Verfahren.

### Warum es (noch) nicht gebaut ist

Die Rechnung ist klein. Was fehlt, ist der Apparat drumherum:

1. **Zuordnung** — welcher Pfeil in A ist welcher in B. Lösbar über die schwachen
   Einzelkamera-Schätzungen: beide liefern bereits Board-Millimeter, also matcht
   man über Nähe im Board-Raum und verfeinert dann. Die bestehende Pipeline
   bootstrappt die Fusion.
2. **Zeitfenster** — welche zwei Detektionen sind *derselbe* Wurf. Das ist der
   Nebenläufigkeits-Teil: ein Timer im Buchungspfad, der heute streng synchron
   ist, plus Latenz auf jeder Buchung.
3. **Buchungspfad** — heute bucht genau eine Kamera sofort (§5a). Fusion hieße,
   auf die zweite zu warten, mit Timeout auf den Einzelkamera-Fall.

Punkt 2 und 3 sind der Grund für die Vertagung, nicht die Geometrie.

---

## 5c. Rekalibrierung anfordern

Kalibrieren kann nur, wer ein Bild hat. Ein Scoreboard-Handy hat keines — es
kann also nur **anfordern**, und genau das ist `request_calibration`: ein
Kommando ohne Inhalt, das der Server an jede Kamera im Raum als
`calibration_requested` weiterreicht. Jede Kamera greift daraufhin ihren
aktuellen Frame und läuft den normalen Kalibrierungspfad.

**Es fächert sich der Auslöser auf, nicht das Ergebnis.** Ein
`calibration_result` kann den Weg nicht zurückgehen: sein Overlay liegt im
Pixelraster der Kamera, die es erzeugt hat (§3). Jede Kamera bekommt also ihr
eigenes — und damit das anfordernde Gerät überhaupt erfährt, ob etwas passiert
ist, geht ein `calibration_status` an **genau dieses eine Gerät**: nur Erfolg
ja/nein, kein Overlay. Wer das ist, hält `calibration_request_store` fest, denn
der Antwortende ist nicht der Fragende.

> Der Status trug ursprünglich auch `clientId` und den Fehlergrund. Beides hat
> das Frontend nie gelesen und wurde entfernt; bei mehreren Kameras (§5a) kommt
> `clientId` zurück, sobald der Empfänger sie auseinanderhalten muss.

### Warum der Status nicht an den Raum geht

Der erste Wurf war ein Broadcast, und der hat die Kalibrierung auf dem
Kamera-Handy zuverlässig aufgehängt: Der Ladebalken drehte endlos, weil die
Kamera **zwei** Nachrichten für einen Versuch bekam — erst ihr
`calibration_result`, unmittelbar danach den Broadcast.

Die Ursache lag im Client und ist inzwischen behoben (§6a): der Socket führte
die ankommenden Nachrichten in einem Signal, das nur den letzten Wert trägt, und
zwei Nachrichten in einem Frame ergaben einen Effect-Lauf, der nur die zweite
sah. Das `calibration_result` wurde nie beobachtet, `status` blieb auf
`'pending'`.

Die Adressierung ist trotzdem geblieben, weil sie unabhängig davon richtig ist:
die Kamera bekommt ihr Ergebnis, der Anfragende seinen Status, sonst niemand.
Der Status beantwortet eine Frage, und nur wer sie gestellt hat, wartet auf die
Antwort. Weggefallen ist nur der *Zwang* — das Protokoll dürfte inzwischen zwei
Nachrichten an ein Gerät schicken, es hat hier bloß keinen Grund dazu.

Wie der Status aufbereitet wird: **Fehlschläge** immer — ab dem Moment wird
nichts mehr korrekt gewertet. Ein **Erfolg** bekommt keinen Toast: solange die
Anfrage offen ist, dreht sich das Sync-Icon des Buttons, und dass es aufhört, ist
die Bestätigung. Antwortet binnen 8 s keine Kamera (z. B. weil keine verbunden
ist — der Server schickt dann gar nichts), stoppt es mit einem Fehler-Toast.
Die automatische Rekalibrierung
verschickt gar keinen Status: niemand hat gefragt, und die Kamera meldet ihren
Fehlschlag ohnehin auf dem Gerät, an dem auch nachjustiert werden muss.

### Zwei Auslöser, ein Mechanismus

1. **Der Button auf dem Scoreboard** — der Fall, für den das Kommando existiert.
2. **Das Rundenende.** `next_player` fordert dieselbe Rekalibrierung an. Das ist
   der wichtigere der beiden: am Rundenende werden die Pfeile aus dem Board
   gezogen, und das ist zugleich der Moment, in dem ein frisches Leer-Board als
   Referenz aufgenommen werden kann (siehe [erkennung.md §1](../erkennung.md)) und
   der, in dem am ehesten gegen Board oder Kamera gestoßen wurde.

Der zweite Auslöser hängt an einer Annahme: dass der Rundenwechsel **nach** dem
Ziehen der Pfeile ausgelöst wird. Bei bestätigtem Wechsel („Wurf bestätigen")
stimmt das — der Spieler holt die Pfeile und tippt dann. Bei automatischer
Weiterschaltung nicht: die kommt direkt nach dem dritten Dart, und die
Kalibrierung sieht ein volles Board. Deshalb ist hier bewusst keine weitere
Logik eingebaut (kein Warten auf ein ruhiges Bild, keine Leer-Prüfung): der
Bestätigungs-Tap *ist* die Aussage „Board ist leer", und eine zweite Quelle
derselben Information hätte nur eigene Fehlerfälle.

Ein dritter Auslöser ist vorgezeichnet, aber nicht gebaut: die
Detection-Registrierung misst mit `alignment_shift_px` bereits, wie weit sich die
Kamera bewegt hat — ein Schwellwert darauf würde eine verrutschte Kamera selbst
melden.

**Fehlschlag ist folgenlos für den Bestand:** Der Server überschreibt
Homographie und Referenzbild nur bei Erfolg. Eine misslungene Rekalibrierung
lässt die alte stehen, die Erkennung läuft also weiter — nur eben gegen eine
Referenz, die die gezogenen Pfeile noch enthält.

---

## 6. Bekannte Stolpersteine

- **Erreichbarkeit im Dev-Setup.** Bewusst *nicht* gelöst: `environment.ts`
  zeigt im Dev-Modus weiter auf `localhost:8000`, beide Server binden lokal.
  Getestet wird mit **zwei Browsern** (oder einem privaten Fenster) auf
  `localhost` — nicht mit zwei Tabs: die `clientId` liegt im localStorage, den
  sich Tabs desselben Profils teilen, also wären beide dasselbe Gerät und
  teilten sich die Rolle. Ein Gerät ist ein Browser-Profil, kein Tab. In
  Produktion trägt die Domain den Rest: der Teilen-Link wird aus
  `location.origin` gebaut und die API liegt relativ unter `/api`.
- **Secure Context.** `navigator.share` und die Clipboard-API gibt es nur im
  Secure Context; der Dialog zeigt den Link deshalb immer im Klartext an und der
  Kopieren-Fehler sagt, dass stattdessen gescannt werden soll. Sobald ein
  zweites Gerät als *Kamera* dazukommt, braucht es ohnehin HTTPS
  (`getUserMedia`).
- **Reconnect** (bislang unter „später" geführt) wird hier notwendig: Ein
  Scoreboard-Handy, das den Bildschirm sperrt, verliert den Socket und zeigt
  danach stillschweigend veralteten Stand. Nötig sind automatischer Reconnect
  mit Backoff und ein sichtbarer Verbindungsindikator. Das Wiederherstellen
  selbst ist trivial — der Server pusht beim Connect bereits den vollen State.
- **Doppelbuchung durch zwei Personen.** Tippen beide manuell denselben Wurf,
  zählt er doppelt. Server-seitig nicht lösbar; wird über die Rollen-UI
  entschärft, nicht verhindert.

---

## 6a. Nachrichten als Stream, nicht als Signal

`SocketService` hielt die zuletzt eingetroffene Server-Nachricht in einem Signal
(`lastMessage`), und die fünf Konsumenten lasen es je in einem `effect()`. Das
ist die Ursache hinter dem Aufhänger aus §5c — kein Einzelfall, sondern ein
struktureller Fehler in der Transportschicht.

**Warum das Nachrichten verliert.** Ein Signal ist eine Zustandszelle, kein
Stream: es trägt den letzten Wert, keine Warteschlange. Effects laufen nicht
synchron pro Zuweisung, sondern gebündelt beim nächsten Change-Detection-Lauf.
Die App ist zoneless (Angular 21, kein `zone.js` in den Dependencies, kein
`provideZoneChangeDetection`), der Scheduler feuert also über einen
`requestAnimationFrame`/`setTimeout`-Race — bis zu ~16 ms später. Beide
`message`-Events sind in dieser Zeit längst durchgelaufen; der Effect sieht nur
den zweiten Wert, der erste wurde nie beobachtet.

Wichtig für die Einordnung: **auf der Socket-Ebene geht nichts verloren.**
WebSocket läuft über TCP, ist geordnet und zuverlässig, und der Listener feuert
auch zweimal. Der Verlust entsteht erst danach, im Client.

**Wo es zuschlug.** Drei Stellen im Backend schicken zwei Nachrichten
unmittelbar hintereinander an dasselbe Gerät:

| Auslöser | Nachrichten | verschluckt wurde |
|---|---|---|
| `next_player` | `game_state`, dann `calibration_requested` | `game_state` auf dem Kamera-Gerät |
| Wurf-Frame | `detection_result`, dann `game_state` | `detection_result` |
| Handshake | `client_state`, dann `game_state` | nichts — `client_state` wird synchron im Listener gelesen, nicht in einem Effect |

Der erste ist der auffällige: Nach „Weiter" auf dem Scoreboard rekalibrierte die
Kamera, ihr Spielstand blieb aber einen Visit zurück — und weil
`DetectionService` die Rundengrenze aus `game.state()?.turns` liest, blieben
zusätzlich die Outlines des beendeten Visits stehen. Der zweite traf jeden
getrackten Wurf und kostete das Wurf-Feedback samt Overlay.

**Warum es intermittierend wirkte.** Zwischen den beiden Sends steht jeweils ein
`await` mit echter Latenz — ein Redis-Roundtrip (`calibration_request_store`)
beziehungsweise ein DB-Commit. Fällt der zufällig über eine Frame-Grenze, kommen
beide Effects einzeln dran und alles funktioniert. Deshalb sah der Fehler beim
Testen sporadisch aus statt reproduzierbar.

**Der Fix.** Der Nachrichteneingang ist ein `Subject<ServerMessage>`, und
`SocketService.on(type)` liefert den gefilterten, typ-verengten Stream:

```ts
this.socket
  .on('game_state')
  .pipe(takeUntilDestroyed())
  .subscribe((state) => { /* ... */ });
```

Jede Nachricht wird genau einmal zugestellt, in Ankunftsreihenfolge, unabhängig
davon wie viele das Backend hintereinander schickt. Der *Zustand* bleibt in
Signals (`game.state()`, `calibration.status()`) — nur der Eingang ist keiner
mehr, denn ein ankommendes Event ist kein Zustand.

Nebeneffekt: In `GameService` fiel die `untracked()`-Konstruktion weg. Sie war
ein zweiter Ausläufer derselben Wurzel — der Effect hing über `setState()` an
seinem eigenen Cache, sodass `reset()` ihn mit der letzten Nachricht in der Hand
erneut auslöste und das gerade beendete Spiel wiederherstellte. Mit einem Stream
existiert das Problem nicht.

Nicht umgestellt wurden die Effects, die echte *Signale* beobachten
(`calibration.status()`, `game.state()?.turns`, `phase()`). Die sind richtig als
Effect: dort interessiert der aktuelle Wert, nicht jede Zwischenstufe.

---

## 7. Reihenfolge

1. Room-Registry und Broadcast des `game_state` — bestehende Pfade unverändert.
   Danach sieht ein zweites Gerät bereits live mit.
2. `revision` auf `GameStateDto`, Client verwirft ältere Snapshots.
3. Mutationen auf WS, REST-Schreibendpunkte entfernen.
4. Socket-Lebenszyklus im Frontend von der Kamera entkoppeln.
5. Join-Route, Teilen-Dialog mit QR, Rollenwahl und virtuelle Scheibe.
6. `client_id` als Geräte-Identität, Rolle serverseitig daran.
7. Reconnect.

Schritt 1 und 2 ergeben zusammen bereits einen benutzbaren Zwischenstand.
