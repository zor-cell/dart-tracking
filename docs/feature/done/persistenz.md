# Persistenz, Redis und Accounts

Planungsdokument für den Schritt vom Prototyp mit prozesslokalen Dicts zu
Postgres (dauerhafte Daten), Redis (heißer Zwischenzustand) und JWT-Accounts.
Beschreibt, was heute wo liegt, wohin es soll, warum diese Aufteilung, und was
im bestehenden Code dabei bricht.

> **Stand:** M0–M5 umgesetzt und verifiziert — Infrastruktur, Redis für die
> flüchtigen Stores, Postgres für die Spiele, Accounts mit rotierendem
> Refresh-Token, Spieler-Identitäten mit Adressbuch, Auswertung mit
> Statistik-Dashboard und Heatmap. Das Vorhaben ist damit umgesetzt; die
> verbliebenen Punkte stehen in §10.

---

## 1. Ausgangslage

Der gesamte Serverzustand liegt in prozesslokalen Dicts hinter modul-globalen
Singletons. Das ist bewusst so gebaut worden und in jedem Store dokumentiert
(„process-local, lost on restart, not shared across workers"), hat aber drei
Folgen:

- **Ein Neustart löscht jedes laufende Spiel.** Ein Deploy während einer Partie
  ist nicht möglich.
- **Nichts wird je gelöscht.** Kein Store hat eine `remove`-Methode. Jedes
  angelegte Spiel hält seine Kalibrierung, seinen Client und sein Referenz-Frame
  (3.5 MiB) bis zum Prozessende. Der Speicher wächst monoton.
- **Keine Historie.** Ein beendetes Spiel ist nicht von einem laufenden zu
  unterscheiden und nach dem Neustart weg — die Statistiken und die Heatmap aus
  [konzept.md §5](../../konzept.md) haben keine Datenbasis.

### Was heute im Speicher liegt

| Store | Inhalt | Größe | Schreibfrequenz |
|---|---|---|---|
| `game_store` | `Game` + Turns + Darts | einige KB | jeder Wurf |
| `client_store` | Gerät + Rolle | ~100 B | Connect, `set_role` |
| `calibration_store` | 3×3-Homographie + Bildmaße | ~250 B | je Kalibrierung |
| `calibration_request_store` | game → client id | ~50 B | je Rundenwechsel |
| `scoring_camera_store` | game → client id | ~50 B | einmal je Kamera |
| `detection_store` | dekodiertes BGR-Frame | **~3.5 MiB** | **jeder Wurf** |
| `game_hub` | `WebSocket`-Objekte + Client | — | Connect / Disconnect |

Das sind nicht sieben gleichartige Dinge, sondern drei Kategorien — und die
Aufteilung folgt genau dieser Unterscheidung.

---

## 2. Die Aufteilung

```
Postgres   dauerhaft, abfragbar      games, turns, darts, players, users
Redis      flüchtig, heiß, mit TTL   clients, calibrations, requests,
                                     scoring-claims
lokal      an den Prozess gebunden   game_hub (WebSockets), detection_store (Frame)
```

**Die Regel dahinter:** Redis bekommt, was einen Reconnect oder Neustart
überleben muss, aber mit dem Spiel wertlos wird. Prozesslokal bleibt, was
entweder gar nicht serialisierbar ist oder groß und billig neu zu bauen.

### 2.1 Postgres: das Spiel

Ein Spiel ist die einzige Sache, die wirklich dauerhaft sein muss, und die
einzige, die später abgefragt wird (Statistiken, Heatmap, „meine Spiele").

Würfe sind menschengetaktet — einer alle paar Sekunden. Ein direkter
Read-Modify-Write gegen Postgres kostet 2–5 ms und liefert **genau eine** Source
of Truth. Die Alternative (Spiel heiß in Redis, Checkpoint nach Postgres) kauft
Latenz, die hier niemand braucht, gegen zwei Kopien, die divergieren können.

### 2.2 Redis: der heiße Zwischenzustand

Vier Stores, zusammen unter einem KB je Spiel. Sie müssen einen Reconnect
überleben (eine Kalibrierung neu aufnehmen heißt, das Handy neu auszurichten),
aber nach dem Spiel will sie niemand mehr sehen.

Zwei Dinge rechtfertigen Redis hier gegenüber „einfach auch Postgres":

1. **TTL.** Das Leak aus §1 verschwindet ohne eine Zeile Aufräumcode.
2. **`SET NX` ist die Semantik von `scoring_camera.claim()`.** Das `setdefault`
   dort ist heute nur korrekt, weil ein Event-Loop es atomar macht. Redis hat
   die Primitive dafür; Postgres bräuchte eine Transaktion für einen Wert, der
   nach dem Spiel wertlos ist.

### 2.3 Prozesslokal: Hub und Referenz-Frame

**Der Hub kann nicht weg.** `WebSocket`-Objekte sind an den Prozess gebunden;
serialisieren lässt sich davon nichts. Das `_rooms`-Dict bleibt, wo es ist.

**Das Referenz-Frame bleibt lokal.** Es ist mit 3.5 MiB drei Größenordnungen
über allem anderen und wird pro Wurf gelesen *und* geschrieben (§3). Die
Begründung, warum das trotzdem konsistent ist: eine WebSocket-Verbindung ist für
ihre Lebensdauer an einen Prozess gebunden, die Frames einer Kamera landen also
immer im selben. Geht die Verbindung verloren und das Frame mit ihr, meldet die
nächste Detektion `NOT_CALIBRATED`, und der Client kalibriert neu — ein Pfad, den
es bereits gibt (`calibration_requested`, siehe
[multi-device.md §5c](multi-device.md#5c-rekalibrierung-anfordern)).

Damit ist der Verlust des Frames kein Fehlerfall, sondern ein bereits
modellierter Übergang. Siehe §9.1, warum die JPEG-Abkürzung ausscheidet.

---

## 3. Performance

Die Frage, ob Redis den Prototyp langsamer macht, zerfällt in zwei sehr
verschiedene Antworten.

**Die kleinen Stores: irrelevant.** Ein Roundtrip über Loopback liegt bei
**0.05–0.2 ms**. Gegen ein `dict` (~50 ns) ist das Faktor 1000, gegen eine
Detektion — ORB mit 4000 Features, Warp, Fusion, in derselben Größenordnung wie
die 370–590 ms der Kalibrierung — ist es nicht messbar.

Der Wurf-Pfad liest drei Keys (Kalibrierung, Frame-Metadaten, Scoring-Flag).
Die gehören in **eine Pipeline**, dann ist es ein Roundtrip statt drei.

**Das Frame: die einzige Zahl, die zählt.** 3.5 MiB pro Richtung, pro Wurf, plus
eine Kopie beim `np.frombuffer`. Über Loopback grob **5–15 ms je Richtung**, also
10–30 ms auf jede Detektion. Verkraftbar, aber nicht gratis — und geschätzt, nicht
gemessen. Solange die Detektionslaufzeit selbst nicht gemessen ist
([erkennung.md §6](../erkennung.md): „noch nicht systematisch gemessen"), lässt sich
der Anteil nicht beziffern. Deshalb bleibt das Frame lokal, bis es einen Grund
gibt, das zu ändern.

**Nebenbefund, unabhängig von diesem Vorhaben (erledigt in M0):**
`detect_board` und `detect_dart` liefen synchron im Event-Loop und blockierten
ihn für einige hundert Millisekunden. Solange nur die Vision-Pipeline darauf
läuft, fällt das kaum auf; sobald DB- und Redis-I/O denselben Loop teilen, staut
sich jede andere Verbindung hinter einer laufenden Detektion. Beide Aufrufe
liegen jetzt in `asyncio.to_thread`.

Dabei ist ein **`asyncio.Lock` um den Aufruf** nötig, und zwar nicht wegen der
Nebenläufigkeit an sich: beide Detektoren legen ihren `trace` in einer
Modul-Globalen ab und ersetzen sie bei jedem Lauf. Zwei gleichzeitige Läufe
läsen also den Trace des jeweils anderen — bei zwei Kameras an einem Spiel ein
realer Fall. Der Lock hält, bis der Trace ausgelesen ist, und stellt damit genau
die Serialisierung wieder her, die der Event-Loop vorher erzwungen hat.
Nebeneffekt: `trace.aligned` wird jetzt innerhalb des Locks gelesen statt nach
mehreren `await`s, gehört also garantiert zum eigenen Lauf.

Der saubere Endzustand wäre, dass die Detektoren ihren Trace **zurückgeben**
statt ihn global abzulegen; dann fällt der Lock weg und zwei Kameras könnten
echt parallel rechnen (OpenCV gibt das GIL in weiten Teilen frei). Das ist ein
Eingriff in `debug/render.py` und die CLI-Runner und deshalb nicht Teil von M0.

---

## 4. Datenmodell

Alle `id`-Spalten sind `uuid` mit `DEFAULT uuidv7()`, also serverseitig erzeugt
und zeitlich sortierbar (§8.5).

```
users(id, email UNIQUE, username UNIQUE, password_hash, created_at)

players(id, display_name, created_at,
        user_id       NULL → users,   -- dieser Spieler IST dieser Account
        owner_user_id NULL → users)   -- diese Identität hat dieser Account angelegt

games(id, mode, checkout_mode, owner_user_id NULL → users,
      current_player_index, revision, created_at, finished_at NULL,
      status)   -- active | finished | abandoned | discarded, siehe §4.5

game_players(game_id → games, player_index, player_id → players,
             PRIMARY KEY (game_id, player_index), UNIQUE (game_id, player_id))

turns(game_id → games, turn_index, player_index, busted,
      PRIMARY KEY (game_id, turn_index))

darts(game_id, turn_index, dart_index, value, multiplier,
      pos_x NULL, pos_y NULL,
      PRIMARY KEY (game_id, turn_index, dart_index),
      FOREIGN KEY (game_id, turn_index) → turns ON DELETE CASCADE)
```

**Zu den Namen.** `player_index` ist die Position im Spiel — dasselbe, was das
Domain `Player.id` nennt und das DTO als `currentPlayerIndex` überträgt. Auf
`game_turns` sagt es, *wer* geworfen hat, nicht *welche* Runde; das ist
`turn_index`. Die Runde hängt bewusst am Index und nicht an `players.id`: wer
auf Position 1 sitzt, ist eine Eigenschaft des Spiels, die `game_players` auflöst.

Runden und Würfe haben **natürliche zusammengesetzte Schlüssel** statt
Surrogat-IDs. Die Domain adressiert sie ohnehin über ihre Position, und der
Rewrite in `save()` (§8.3) verbrennt so keine Sequenz pro Wurf.

Auf `users` steht bewusst **kein** Vor-/Nachname: die Oberfläche zeigt
ausschließlich `players.display_name`, der Account taucht dort nie auf. `email`
ist der Login, `username` das öffentliche Handle — brauchbar, um später einen
Gast-Player an einen Account zu übergeben (§10), ohne die Adresse preiszugeben.

**Zeitstempel sind `timestamptz`, und das heißt UTC.** Der Typname führt in die
Irre: Postgres speichert dort keine Zeitzone, sondern einen absoluten Zeitpunkt
in 8 Byte — genauso viele wie `timestamp`, in denen gar kein Platz für eine Zone
wäre. Die Session-Zeitzone wirkt nur auf Eingabe-Interpretation und Ausgabe.
`timestamp` *ohne* Zone wäre die unsichere Wahl, weil eine Ablesung ohne
Bezugspunkt sich nicht mehr auf einen Moment zurückführen lässt. Nach Python
kommen zonenbehaftete `datetime` mit `tzinfo=UTC`. Gesetzt werden die Werte über
`server_default=func.now()`, also von Postgres — Uhr und Zone des App-Servers
spielen keine Rolle, was zählt, wenn dasselbe Backend mal auf dem RPi und mal
lokal läuft.

### 4.1 Warum `players` zwei User-Spalten hat

Die beiden beantworten verschiedene Fragen und fallen nur für den Kontoinhaber
selbst zusammen. Beispiel: ich habe einen Account und lege ein Spiel mit mir
und zwei Gästen an.

| | `user_id` | `owner_user_id` |
|---|---|---|
| ich | ich | ich |
| Gast B | `NULL` | ich |
| Gast C | `NULL` | ich |

`user_id` entscheidet die **Historie** (§4.2), `owner_user_id` das
**Autocomplete** (§4.3). Ein Gast ist also kein namenloser String, sondern eine
Identität in meinem Adressbuch — nur ohne Konto dahinter.

**Jeder Teilnehmer bekommt eine `players`-Zeile, Gäste eingeschlossen.** Die
Alternative — Gastnamen als reiner String auf `game_players` — spart eine
Tabelle, macht aber Wiederverwendung unmöglich: beim zweiten Spiel gäbe es
nichts zu vervollständigen, und „B" aus Spiel 1 und „B" aus Spiel 2 wären
unverbunden, also ohne spielübergreifende Statistik.

Zwei Accounts, die je einen Gast „Max" anlegen, führen zu zwei verschiedenen
`players` — beabsichtigt. Über Namensgleichheit wird nichts zusammengeführt.

### 4.2 „Meine Spiele" hängt an Teilnahme, nicht am Anlegen

```sql
games JOIN game_players … JOIN players … WHERE players.user_id = :me
UNION
games WHERE owner_user_id = :me
```

Der erste Zweig ist der Normalfall und der Grund, warum die Abfrage nicht an
`games.owner_user_id` allein hängen darf: legt ein Mitspieler mit Account die
Partie an, muss sie in **beiden** Historien stehen. Der zweite Zweig deckt den
Fall ab, dass jemand mitschreibt, ohne selbst zu spielen.

### 4.3 Der Autocomplete-Endpoint ist auf mich beschränkt

```
GET /api/players?q=<prefix>     → nur players WHERE owner_user_id = :me
```

Eine globale Spielersuche wäre ein User-Enumeration-Endpoint: ein Präfix würde
jeden registrierten Nutzer des Systems ausgeben. Gebraucht wird sie auch nicht —
gespielt wird mit immer denselben Leuten, und die stehen nach dem ersten Spiel
im eigenen Adressbuch.

Der Endpoint verlangt Auth. Ohne Account gibt es kein Adressbuch, dann werden
alle Namen frei eingetippt und nichts landet in einer Historie.

### 4.4 Spielanlage nimmt Identität *oder* Name

`GameConfigDto.player_names: list[str]` trägt das nicht mehr — ein Slot ist
entweder eine bestehende Identität oder ein neuer Name:

```json
{ "mode": 501, "checkoutMode": "doubleOut",
  "players": [ { "playerId": "…" }, { "name": "B" }, { "name": "C" } ] }
```

Seat ist der Array-Index. Breaking Change am DTO und an der Setup-View.

**Die Setup-View muss ohne Login funktionieren** (Entscheidung). Sie hat damit
zwei Modi: eingeloggt Autocomplete plus Freitext, ausgeloggt nur Freitext. Das
ist beim Bauen der View einzuplanen, nicht nachträglich — ein anonym angelegtes
Spiel bekommt `owner_user_id = NULL` und drei Gäste ohne Eigentümer, läuft
ansonsten aber wie jedes andere.

### 4.5 Nicht jedes Spiel zählt: `games.status`

Beim Entwickeln der CV-Pipeline entstehen **hunderte Wegwerf-Spiele** — drei
Würfe, Kalibrierung prüfen, Tab zu. Landen die ungefiltert in der Auswertung,
ist das Dashboard aus M5 wertlos. Der Status trennt sie ab:

| Wert | Wodurch | Zählt in der Statistik |
|---|---|---|
| `active` | beim Anlegen | nein |
| `finished` | jemand hat ausgecheckt (`Game.winner`) | ja |
| `abandoned` | nie beendet, lange keine Aktivität | ab genug Würfen |
| `discarded` | ausdrücklich verworfen | nein |

`abandoned` zählt bewusst mit: ein abgebrochenes Spiel mit 40 Würfen hat einen
validen 3-Dart-Average, auch ohne Checkout. Nur ein Checkout als Bedingung würde
echte Daten wegwerfen.

**Die Voreinstellung ist Opt-out, nicht Opt-in.** Der Normalfall — Spiel zu
Ende, alle legen das Handy weg und ziehen Pfeile — braucht keine Aktion. Nur der
Ausnahmefall („war Testerei") verlangt einen Klick, und das ist genau der Fall,
in dem man ohnehin am Rechner sitzt. Warum das andersherum nicht funktioniert,
steht in §9.6.

Entschieden in M5: **niemand setzt `abandoned`, es wird beim Lesen abgeleitet**
(§8.7). In der Spalte steht weiter `active`; was der Client sieht, ist das
Ergebnis von `effective_status`.

**Die Domain des Spiels ändert sich dabei nicht.** `Player(id: int, name: str)`
ist Seat plus Anzeigename, genau das, was das Scoreboard braucht. Die persistente
Identität ist ein eigener Begriff und liegt im Feature `player`
(`PlayerIdentity`); das Spiel-Domain kennt sie nicht.

**Relational, nicht ein JSONB-Blob** — die Begründung steht in §9.5, weil sie die
naheliegendste Alternative ist. Kurz: nicht wegen der Datenmenge (die ist
winzig), sondern weil die Auswertungen Aggregationen über entpackte Arrays sind
und der Schreibpfad ohnehin aus Deltas besteht.

**Gastspiele bleiben möglich.** `owner_user_id` und `players.user_id` sind
nullable. Ein Spiel per Link zu teilen, ohne dass irgendwer einen Account hat,
muss weiter funktionieren — sonst zerlegt die Auth den Multi-Device-Flow.

**Stack:** SQLAlchemy 2.0 async + `asyncpg` + Alembic.

Bewusst **nicht** SQLModel: das verschmilzt Pydantic-DTO und Tabelle zu einer
Klasse. Die Regel in
[backend-best-practices.md](../../guidelines/backend-best-practices.md) — „das Domain
muss nicht wissen, wie es serialisiert wird" — gilt für Persistenz genauso wie
für das Wire-Format. Also eine eigene Schicht `persistence/` je Feature
(SQLAlchemy-Modelle + Mapper), `domain/` bleibt reine Dataclasses. Die
Abhängigkeit zeigt in eine Richtung: `persistence/` → `domain/`, nie zurück.

Das ist eine neue Schicht neben `dto/`, `domain/`, `services/`, `debug/` und
gehört in die Backend-Guidelines nachgetragen.

---

## 5. Konsequenzen im bestehenden Code

Drei Stellen sind heute korrekt, weil alles ein geteiltes Python-Objekt im selben
Event-Loop ist. Sobald ein Store eine Kopie zurückgibt, sind sie es nicht mehr.

**5.1 Das Spiel wird einmal geholt und dauerhaft mutiert.**
`websocket_endpoint` lädt `game` beim Connect
([socket.py:91](../../../backend/src/app/api/core/socket/socket.py:91)) und reicht
die Referenz für die gesamte Socket-Lebensdauer an `_dispatch` weiter. Mit
Postgres muss pro Kommando geladen und geschrieben werden.

**5.2 Die Atomarität von `next_player` ruht auf dem Event-Loop.**
Der Docstring beschreibt genau den Fall: zwei Geräte beenden denselben Visit, das
zweite findet den frischen, leeren Turn und tut nichts. Das setzt voraus, dass
Read-Modify-Write nicht unterbrochen wird. Beim Weg über die Datenbank braucht
der Kommando-Pfad ein `SELECT … FOR UPDATE` auf die Game-Zeile (oder optimistisch
`WHERE revision = ?`), sonst kann ein Spieler übersprungen werden.

**5.3 Die Rolle wird im Store mitmutiert.**
`connection.client.role = command.role` ändert das Objekt, das im `client_store`
liegt, weil es dasselbe ist. Mit Redis ist der Write-Back explizit zu machen.

---

## 6. Auth

Access-Token (15 min) + Refresh-Token im httpOnly-Cookie mit Rotation,
`SameSite=Lax` gegen CSRF. `pwdlib[argon2]` fürs Hashing, `pyjwt` für die Token.

**Auth ist optional, nicht verpflichtend.** Die Game-Endpoints bekommen eine
*optionale* `current_user`-Dependency; ohne Account läuft alles wie bisher, nur
ohne Zuordnung zu einem Profil.

### 6.1 Der WebSocket bleibt anonym

**Die Trennlinie: alles Nutzerbezogene läuft über HTTP mit Token, der Socket
transportiert ausschließlich Spielbezogenes.** Über ihn gehen `game_state`,
`client_state`, `calibration_result` und `detection_result` — in keiner dieser
Nachrichten steckt ein Nutzer.

Auth im Socket würde auch nichts kaufen, das gebraucht wird:

- **Attribution passiert nicht dort.** Ein Wurf wird auf den *Seat* gebucht, den
  der Spielstand bestimmt. Die Kamera weiß nicht, welcher Nutzer dort sitzt, und
  muss es nicht — die Kette Seat → `game_players` → `players` → `users` steht in
  der Datenbank und wird beim Anlegen des Spiels über HTTP gesetzt.
- **Autorisierung liefe dem Design zuwider.** Der Join-per-Link
  ([multi-device.md](multi-device.md)) ist ein Feature: wer den Link hat, soll
  mitspielen. Ein Auth-Gate davor würde genau das entfernen.

**Die Konsequenz, bewusst getroffen: die Spiel-ID ist ein Capability-Token.** Wer
sie kennt, darf beitreten, werten und undoen. Das trägt, weil sie nicht erratbar
ist, und entspricht der Stärkeklasse eines Freigabelinks. Seit der Umstellung auf
`uuidv7()` (§8.5) ist die Entropie allerdings eine andere: **rund 62 zufällige
Bit statt 122**, weil 48 Bit Zeitstempel und die Versions-/Variantenbits fest
sind. Der Zeitanteil ist sogar gezielt ratbar — wer weiß, wann eine Partie
angelegt wurde, kennt ihn. Übrig bleiben 2⁶² ≈ 4.6·10¹⁸ Möglichkeiten, also
weiterhin weit jenseits dessen, was sich über HTTP durchprobieren lässt (und in
derselben Klasse wie ein zehnstelliges Freigabetoken). Die Entscheidung ist damit
unverändert tragfähig — aber sie ruht jetzt auf einer Zahl, die man kennen
sollte, statt auf einer, die keine Rolle spielt. Dieselbe Eigenschaft hat schon heute die
`clientId`: sie wird angenommen, wie sie kommt (`client_store.resolve`), und
damit ist auch der Scoring-Claim innerhalb eines Spiels reine
First-come-Vereinbarung, keine Zugriffskontrolle. Beides ist tragfähig, solange
Link-Inhaber als vertrauenswürdig gelten; das ist die Annahme, unter der das
System steht.

**Ein Fall braucht später eine Brücke:** jemand joint per Link, hat einen
Account und will die Partie in seiner Historie sehen. Auch das kommt ohne
Socket-Auth aus — ein einmaliges
`POST /api/games/{id}/players/{seat}/claim` mit Token, außerhalb des Sockets.

**CORS deckt den Socket nicht ab.** Browser wenden die Same-Origin-Policy nicht
auf WebSocket-Handshakes an: es gibt keinen Preflight, die Verbindung kommt
zustande, und der `Origin`-Header müsste vom Server geprüft werden. FastAPIs
`CORSMiddleware` läuft nur auf HTTP-Scope. Der Socket steht also jeder Origin
offen — konsistent mit dieser Entscheidung (der Zugang ist die Spiel-ID, nicht
die Origin), aber die Middleware darf nicht als sein Schutz verbucht werden.

Die Middleware selbst bleibt trotzdem nötig, allerdings nur in der Entwicklung:
in Prod liegen App und `/api` hinter demselben nginx und damit auf einer Origin
(`environment.ts` adressiert relativ), während der Angular-Dev-Server auf Port
4200 gegen ein Backend auf 8000 läuft — verschiedene Ports sind verschiedene
Origins. Der Container bekommt deshalb `CORS_ORIGINS: "[]"`, damit die
Dev-Defaults nicht mit nach Prod wandern; ab M3 wäre das mit
`allow_credentials=True` und Cookie sonst eine echte Lücke.

---

## 7. Was Redis *nicht* löst

Der Vollständigkeit halber, damit es in der Arbeit nicht als Allheilmittel steht:

- Der `game_hub` bleibt prozesslokal. Bei mehreren Workern bräuchte er Redis
  Pub/Sub als Fan-out — ist derzeit **kein Ziel** (Entscheidung: ein Worker,
  Redis dient Neustart-Festigkeit und TTL, nicht Skalierung).
- Redis ist kein Ersatz für Postgres-Transaktionen. Die Konsistenz eines Spiels
  über mehrere Geräte (§5.2) hängt an der DB, nicht am Cache.
- Ein `maxmemory` mit `allkeys-lru` würde stillschweigend Kalibrierungen
  wegwerfen. Stattdessen: keine Eviction, ausschließlich explizite TTLs.

---

## 8. Meilensteine

Jeder Schritt ist für sich lauffähig und deploybar.

| | Inhalt | Ergebnis |
|---|---|---|
| **M0** ✅ | Infrastruktur: postgres + redis in `compose.yaml` mit Volumes und Healthchecks, Ports in `compose.dev.yaml`, `app/infrastructure/` mit `config.py` (pydantic-settings, liest die `.env`/`.env.example` am Repo-Wurzelverzeichnis), `database.py` und `redis_client.py` über den FastAPI-Lifespan, Alembic-Scaffold gegen `app.infrastructure.config`, `/api/health` meldet beide Dienste und antwortet 503. Dazu `asyncio.to_thread` + Lock um die CV-Aufrufe (§3). | kein Verhaltensunterschied |
| **M1** ✅ | Redis für `client`, `calibration`, `calibration_request`, `scoring_camera`. Gleiche Schnittstellen, Methoden sind `async`, Call-Sites in `socket.py` bekommen `await`. TTLs. `claim()` → `SET NX`. Frame-Store und Hub bleiben lokal. | Speicher-Leak weg, Kalibrierung überlebt Neustart |
| **M2** ✅ | Postgres für Spiele: **das vollständige Schema aus §4** in einer Migration (`players` und `game_players` inklusive, User-Spalten bleiben vorerst `NULL`), `GameRepository`, `FOR UPDATE` im Kommando-Pfad, Laden pro Kommando (§5.1/5.2). `status`/`finished_at` setzen. | Spiele überleben einen Deploy |
| **M3** ✅ | Auth: users, register/login, Refresh-Rotation, optionale `current_user`-Dependency auf den HTTP-Endpoints. Der Socket bleibt unangetastet (§6.1). Frontend: `features/auth` (Login, Register, Account), HTTP-Interceptor mit Refresh-Retry, Guard, Route `/account`. | Accounts |
| **M4** ✅ | Spieler-Identitäten füllen: `user_id`/`owner_user_id` werden gesetzt, Spielanlage nimmt Identität *oder* Name (§4.4), `GET /api/players?q=` als Adressbuch (§4.3), Setup-View mit Autocomplete. | Würfe hängen an einer wiedererkennbaren Identität |
| **M5** ✅ | „Meine Spiele" + Statistik-Dashboard auf den neuen Tabellen. | der Teil, der M2–M4 rechtfertigt |

M5 ist nicht optional-am-Ende, sondern der Grund für alles davor: ohne Auswertung
ist die Persistenz reine Infrastruktur ohne Ergebnis für die Arbeit.

**Zur Reihenfolge von M2–M4.** Das Schema entsteht in M2 vollständig, obwohl die
User-Spalten dort noch niemand füllt — eine zweite Migration, die
`game_players` nachträglich unter die schon laufenden Spiele schiebt, wäre teurer
als ein paar Spalten, die eine Weile `NULL` bleiben. Auth kommt vor den
Spieler-Identitäten, weil das Adressbuch an `owner_user_id` hängt: umgekehrt
gebaut hätte M4 ein Autocomplete ohne Datenbasis und Identitäten ohne
Eigentümer.

### 8.1 Was M0 im Detail festgelegt hat

**Konfiguration.** Eine `.env` im Repo-Wurzelverzeichnis, gelesen von docker
compose *und* vom Backend (`config.py` löst den Pfad aus `__file__` auf, nicht
aus dem Arbeitsverzeichnis). Zugangsdaten stehen **nur** dort: `postgres_user`,
`postgres_password` und `postgres_db` haben in `Settings` keine Defaults, und in
`compose.yaml` sind sie als `${VAR:?…}` markiert. Eine fehlende `.env` scheitert
damit auf beiden Wegen sofort und sichtbar, statt still auf ein ratbares Konto
zurückzufallen. `database_url` und `redis_url` werden aus den Einzelwerten
zusammengesetzt (mit `quote_plus`), damit Benutzer und Passwort nicht doppelt in
der Datei stehen — einmal für Compose, einmal in einer URL — und auseinander
laufen können.

Hosts und Ports stehen nicht in der `.env`, sondern als Defaults in `config.py`,
und zeigen auf die von `compose.dev.yaml` publizierten Ports; das
containerisierte Backend bekommt stattdessen die Service-Namen aus
`compose.yaml` und liest die Datei gar nicht. Preis dieser Aufteilung: die
Portnummern stehen an zwei Stellen, die zusammenpassen müssen
(`compose.dev.yaml` und `config.py`).

**Redis verlangt ein Passwort, in jeder Umgebung.** Das offizielle Image startet
mit `protected-mode no` und ohne `requirepass` — gemessen: ein fremder Client
bekam von außen ein vollständiges `INFO server`. In Prod schützt zwar schon,
dass `compose.yaml` den Port nicht publiziert (erreichbar nur im
Compose-Netzwerk), aber das ist eine einzige Schicht, die eine später
hinzugefügte Portfreigabe oder ein kompromittierter Nachbarcontainer aushebelt.
`requirepass` kommt deshalb dazu, und zwar auch in der Entwicklung: eine
Umgebung, in der die Authentifizierung anders läuft als in Prod, ist die, in der
man Auth-Fehler erst in Prod findet. Das Passwort erreicht den Server über die
Umgebung statt über `argv`, damit es nicht in der Prozessliste des Containers
steht.

**Postgres 18, Volume eine Ebene höher gemountet.** Seit Version 18 liegt
`PGDATA` im offiziellen Image unter `/var/lib/postgresql/18/docker` statt unter
`/var/lib/postgresql/data`. Nur das Image-Tag zu tauschen wäre deshalb nicht
einmal ein Fehler gewesen, sondern etwas Schlimmeres: der Container hätte am
neuen Pfad eine leere Datenbank angelegt, während die alten Daten unsichtbar im
selben Volume liegen bleiben. Das Volume ist deshalb auf `/var/lib/postgresql`
gemountet — das versionierte Verzeichnis liegt darin, und der nächste
Major-Sprung fasst die Compose-Datei nicht mehr an. Der Wechsel selbst geschah
zu dem Zeitpunkt, an dem er nichts kostete: bei leerer Datenbank. Später
verlangt er `pg_upgrade` oder Dump/Restore, weil Major-Versionen inkompatible
Datenverzeichnisse haben.

**Keine festen Container-Namen.** `container_name:` beansprucht einen Namen
global pro Docker-Daemon; auf dem RPi kollidierte das mit einer zweiten App, die
ebenfalls `redis_container` hieß. Ohne die Zeile leitet Compose die Namen aus
`name: dart-tracking` ab (`dart-tracking-redis-1`) und die Kollision ist
konstruktiv ausgeschlossen. Zugriff läuft über `docker compose exec <service>`
statt `docker exec <container>`.

**Deployment.** Der GitLab-Runner auf dem RPi führt `docker compose up -d
--build` im ausgecheckten Repo aus. Die `.env` liegt dort *nicht* — sie ist
gitignored, und das Build-Verzeichnis des Runners wird ohnehin mit
`git clean -ffdx` geleert. Die Werte kommen stattdessen aus den
CI/CD-Variablen des Projekts, weil Compose auch aus der Prozessumgebung
interpoliert.

**Migrationen laufen beim Containerstart**, nicht als CI-Schritt:

```dockerfile
CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn …"]
```

Drei Eigenschaften, alle gemessen:

- **Schema und Code können nicht auseinanderlaufen**, weil beide in demselben
  Image stecken. Das gilt auch für einen Neustart ohne Deploy und für ein
  manuelles `docker compose up` — ein CI-Schritt würde nur den einen Pfad
  abdecken.
- **`&&` statt `;`**: scheitert die Migration, startet uvicorn nicht und der
  Container endet mit Exit-Code 1. Verifiziert mit falschem DB-Passwort — kein
  `Uvicorn running` im Log.
- **`exec`** macht uvicorn zu PID 1, sodass `docker stop` es erreicht und der
  Lifespan-Shutdown durchläuft (`Application shutdown complete` im Log). Ohne
  `exec` bliebe die Shell PID 1 und Docker würde nach 10 s hart abschießen.

Ein zweiter Start ist folgenlos: Alembic loggt dann nur noch `Context impl`
ohne `Running upgrade`.

**Damit ein kaputter Deploy auch sichtbar ist**, hat der Backend-Service einen
Healthcheck auf `/api/health` und der CI-Job `--wait`. `docker compose up -d`
allein meldet Erfolg, sobald der Container *gestartet* ist — mit
`restart: unless-stopped` liefe er danach in eine Crash-Schleife, während die
Pipeline grün bliebe. Mit `--wait` wartet Compose auf `healthy` und bricht sonst
ab; gemessen: Exit-Code 1 und `container … exited (1)`.

**Nebenbei:** `.dockerignore` schließt jetzt `testdata/` und `scripts/` aus. Der
Build-Kontext fiel damit von **173 MB auf 561 KB** — die Testfotos werden nur
von den CLI-Runnern gebraucht, nie vom laufenden Server, und wurden bei jedem
Deploy auf den RPi übertragen. Die Debug-Dumps legen ihr Verzeichnis selbst an
(`mkdir(parents=True)`), das Weglassen kostet also nichts.

### 8.2 Was M1 im Detail festgelegt hat

**Schlüsselschema.** Geräte leben unabhängig vom Spiel, alles andere hängt
darunter:

```
client:{client_id}:role                       30 Tage, bei jedem Connect erneuert
game:{game_id}:calibration:{client_id}        24 h, bei jedem Lesen erneuert
game:{game_id}:scoring_camera                 24 h, bei jedem Lesen erneuert
game:{game_id}:calibration_request             1 h, bewusst NICHT erneuert
```

Zwei verschiedene Lebensdauern, weil es zwei verschiedene Dinge sind: ein
Handy ist dasselbe Gerät über Wochen, eine Kalibrierung ist mit dem Spiel
wertlos. Erneuert wird per `GETEX` (Lesen und Verlängern in einem Roundtrip),
damit ein pausiertes Spiel nicht mitten in der Partie seine Kalibrierung
verliert. Der Recalibration-Request ist die Ausnahme: eine Antwort, auf die
niemand mehr wartet, soll auslaufen.

**JSON, nicht Pickle.** Die `Calibration` trägt ein `np.ndarray`; gespeichert
wird `homography.tolist()`. Pickle wäre kürzer, aber ein geteilter Store darf
keine Quelle für zu deserialisierende Objekte sein, und in `redis-cli` ist JSON
lesbar. Verifiziert: der Round-Trip ist bitgenau (`np.array_equal`), `float64`,
Form 3×3, und die Inverse ergibt weiterhin die Einheitsmatrix.

**`claim()` ist jetzt echt atomar.** Das alte `dict.setdefault` war nur korrekt,
weil ein Event-Loop es nicht unterbricht. `SET NX` ist die Primitive dafür —
gemessen mit 20 gleichzeitigen `claim()`-Aufrufen: **genau ein Gewinner**.

**`Client` wird nicht mehr mitmutiert.** Der Store gab früher das Objekt heraus,
das er selbst hielt, also war `connection.client.role = …` schon der Schreibvorgang.
Jetzt kommt eine Kopie zurück, und `set_role` braucht ein explizites
`client_store.save()`. Die Kopie an der Verbindung wird trotzdem weiter mutiert —
`hub.broadcast(role=…)` filtert daran.

**Was bei einem Redis-Ausfall passiert:** die `RedisError` läuft aus dem
Socket-Handler heraus, die Verbindung fällt, der Client verbindet neu. Bewusst
nicht abgefangen — ein stillschweigend als „nicht kalibriert" behandelter
Ausfall wäre schlechter als ein sichtbarer Abbruch.

### 8.3 Was M2 im Detail festgelegt hat

**`_apply` ist die einzige Stelle, an der ein Spiel geändert wird.** Sie öffnet
eine Transaktion, lädt das Spiel mit `SELECT … FOR UPDATE`, wendet die Mutation
an, schreibt zurück und meldet, ob sich etwas geändert hat. Der Socket trägt das
Spiel nicht mehr über seine Lebensdauer mit sich (§5.1); `_dispatch` bekommt nur
noch die `game_id`. Broadcastet wird **nach** dem Commit, damit kein Gerät einen
Zustand sieht, der noch nicht dauerhaft ist.

Gemessen: zwei Geräte senden im selben Tick `next_player` → das Spiel steht
danach bei **genau zwei Runden**, nicht drei. Ohne den Lock wäre das der Fall,
in dem ein Spieler übersprungen wird. Mit zwölf gleichzeitigen `register_dart`
auf dasselbe Spiel landen genau **drei** Würfe (das Visit-Limit), der Rest wird
absorbiert; `pg_stat_database.deadlocks` bleibt bei 0.

**Warten ja, Deadlock nein.** Ein Deadlock braucht einen Zyklus im Wartegraph.
Der kann hier nicht entstehen: jede Transaktion fasst genau *ein* Spiel an,
nimmt immer zuerst die `games`-Zeile und danach deren
`game_turns`/`game_darts`, und wer am `FOR UPDATE` blockiert, hält zu diesem
Zeitpunkt noch **gar keine** Sperre —
ohne gehaltene Sperre kein Zyklus. Zwei Transaktionen auf verschiedenen Spielen
berühren disjunkte Zeilen.

Dass die Wartezeit dabei kurz bleibt, hängt daran, was *nicht* in der
Transaktion steht: die Detektion (~400 ms) läuft davor, der Broadcast danach.
Letzteres war als Haltbarkeitsargument gedacht (kein Gerät sieht einen nicht
committeten Zustand), trägt hier aber genauso: läge der Versand innerhalb,
könnte ein Handy an einer schlechten Verbindung die Zeilensperre festhalten.

Entstehen könnte ein Zyklus erst, wenn eine Transaktion **zwei** Spiele anfasst
(ein Zusammenführen-Feature, ein Batch über mehrere Spiele) — dann müsste in
konsistenter Reihenfolge gesperrt werden, etwa nach `id` aufsteigend. Nicht
betroffen ist die Spieler-Tabelle: der Join in `_load` ist ein einfaches
`SELECT` ohne `FOR UPDATE` und nimmt keine Zeilensperre.

`lock_timeout` und `idle_in_transaction_session_timeout` stehen auf 0
(unbegrenzt). Heute unkritisch, weil keine Transaktion lange etwas hält; als
Absicherung für später würden 5 s bzw. 30 s ein pathologisches Warten in einen
klaren Fehler verwandeln statt in einen hängenden Socket.

**`save()` schreibt Runden und Würfe komplett neu**, statt einen Delta zu
bilden. Das weicht von der Erwartung in §9.5 ab, wo die Delta-Form als Argument
für relational auftauchte: ein Spiel hält rund 25 Runden und 70 Würfe, der
`DELETE` kaskadiert, und die einfache Form kostet ein paar Millisekunden — dafür
gibt es keine Sonderfälle rund um `undo`, das über Rundengrenzen hinweg
zurücknimmt. Die Delta-Variante bleibt die Optimierung, falls sie je nötig wird.

**Zwei Fallen beim Schreiben, beide real aufgetreten:**

1. *SQLAlchemy sortiert INSERTs nicht nach Fremdschlüssel*, solange keine
   `relationship()` deklariert ist — `game_players` lief vor `games`, `game_darts`
   wäre vor `game_turns` gelaufen. Beide Stellen haben jetzt eine explizite
   `flush()`-Grenze zwischen den Abhängigkeitsebenen.
2. *Ein nicht importiertes Tabellenmodul ist zur Laufzeit kein Fehler, sondern
   ein unauflösbarer Fremdschlüssel* (`NoReferencedTableError` beim ersten
   Flush). `api/tables.py` listet deshalb alle Tabellenmodule an einer Stelle
   und wird von Alembic **und** vom Repository importiert.

**Eine Datei pro Tabelle** unter `<feature>/persistence/`, benannt nach dem
Begriff, die Klasse nach der Schicht — wie es `dto/player.py` → `PlayerDto` und
`domain/player.py` → `Player` schon vormachen. Also `persistence/player.py` →
`PlayerTable`. `api/tables.py` sammelt die sechs Module ein.

**`status` wird beim Speichern aus `game.winner` abgeleitet**, nicht im Domain
gehalten. Damit kann er nicht auseinanderlaufen, und ein `undo` auf den
Siegwurf setzt ihn automatisch auf `active` zurück. `discarded` und `abandoned`
(§4.5) brauchen später einen eigenen Weg — die leitet niemand aus dem
Spielstand ab.

### 8.4 Was M3 im Detail festgelegt hat

**Zwei Token, zwei Aufbewahrungsorte.** Der Access-Token (JWT, HS256, 15 min)
geht im Antwortkörper an den Client und liegt dort **nur im Speicher** — ein
`localStorage` wäre ein Bearer-Token in Reichweite jedes Skripts auf der Seite.
Der Refresh-Token ist ein undurchsichtiges `secrets.token_urlsafe(32)` in einem
httpOnly-Cookie (`Path=/api/auth`, `SameSite=Lax`), das der Frontend-Code
folglich gar nicht lesen kann. Ein Reload holt sich über dieses Cookie eine
frische Sitzung; ohne es ist man abgemeldet.

**Rotation über `GETDEL`.** Die Sitzungen liegen als
`auth:refresh:{sha256(token)}` in Redis mit 30 Tagen TTL — dieselbe Begründung
wie bei den anderen heißen Stores (§2.2): die TTL *ist* das Ablaufdatum, es gibt
nichts aufzuräumen. Eingelöst wird mit `GETDEL`, also atomar lesen und löschen:
jeder Token gilt genau einmal, ein zweiter Versuch mit demselben findet nichts.
Verifiziert: der zurückgespielte Vorgänger bekommt 401. Der Schlüssel ist ein
Digest, damit ein Dump des Stores keine benutzbaren Token ausgibt.

**Das Cookie wird auch am Fehlerfall gelöscht.** Header, die auf dem injizierten
`Response` gesetzt werden, verwirft FastAPI, sobald der Handler eine
`HTTPException` wirft. Die Löschanweisung reist deshalb als `set-cookie`-Header
*an* der Exception mit (`_expired_session`), sonst bliebe ein toter Token
30 Tage im Browser stehen.

**Ein ungültiger Token ist ein Fehler, keine Anonymität.** Die entscheidende
Festlegung an `current_user`, und sie ist beim Testen erst falsch gewesen:
`CurrentUser` darf nur dann `None` liefern, wenn **gar kein** Token geschickt
wurde. Ein *vorhandener*, aber abgelaufener Token muss 401 ergeben. Mit dem
ursprünglichen „ungültig → anonym" legte ein angemeldeter Client nach 15 Minuten
still Spiele **ohne Eigentümer** an — gemessen mit auf 60 s verkürzter
Token-Laufzeit: das Spiel landete ohne `owner_user_id` in der Datenbank, ohne
eine einzige Fehlermeldung. Erst der 401 löst im Client den Refresh aus, und
genau das macht die optionale Auth überhaupt tragfähig.

**Der Client wartet auf die Wiederherstellung, bevor er signiert.** Der
`authInterceptor` hängt jede Anfrage an `AuthService.ready` — sonst ginge eine
Anfrage kurz nach dem Seitenaufbau unsigniert raus, weil der Refresh noch läuft.
Die Auth-Aufrufe selbst sind davon ausgenommen (`SKIP_AUTH_RETRY`); der Refresh
*ist* einer von ihnen und würde sonst auf sich selbst warten.

Zwei weitere Reihenfolgen, beide nicht beliebig:

- **`errorInterceptor` steht vor `authInterceptor`** in `withInterceptors`, ist
  damit der äußere. Ein Request, der erst im zweiten Anlauf durchgeht, erzeugt
  so kein Fehler-Banner für den 401 davor. Verifiziert: nach echtem Ablauf
  `POST /games 401 → POST /auth/refresh 200 → POST /games 201`, null Toasts.
- **Der Restore startet beim ersten Zugriff, nicht im Konstruktor.** Der
  Refresh-Aufruf läuft durch den Interceptor, und der injiziert den
  `AuthService` — täte er das, während dessen Konstruktor noch läuft, wäre es
  ein Abhängigkeitszyklus. Aus demselben Grund holt sich der Guard seinen
  `Router` **vor** dem `await`: eine Injection-Context überlebt kein `await`
  (NG0203, real aufgetreten).

**Gastbetrieb bleibt unangetastet.** `POST /api/games` nimmt die optionale
Dependency und setzt `owner_user_id` nur, wenn jemand angemeldet ist. Verifiziert
sind beide Wege: mit Token trägt die Zeile den Account, ohne Token bleibt sie
`NULL`. Die Spieler-Identitäten (`players.user_id`/`owner_user_id`) füllte
damals noch niemand; das kam in M4 dazu (§8.6).

**Register und Login sind zwei DTOs, und zwar mit verschiedenen Regeln.** Nicht
nur wegen „eine Datei pro DTO": Die Längen- und Zeichenregeln für ein Passwort
sind Regeln fürs *Wählen* eines Passworts. Auf dem Login-Weg wäre ein zu kurzes
Passwort damit ein 422 „ungültige Eingabe" statt eines 401 „falsches Passwort" —
zwei verschiedene Meldungen für denselben Vorgang, und nebenbei ein Hinweis
darauf, wie das echte Passwort *nicht* aussieht. `LoginDto` prüft deshalb nur
die Obergrenze, damit niemand argon2 ein Megabyte zu hashen gibt.

**Was in M3 bewusst *nicht* passiert ist:** kein Passwort-Reset (braucht
Mailversand), keine E-Mail-Verifikation, keine aktive Sitzungsliste („auf allen
Geräten abmelden" wäre ein `SCAN` über die Refresh-Keys oder ein zweiter Index
pro Nutzer), und kein Rate-Limit auf `/auth/login`. Das letzte ist der einzige
Punkt davon, der sicherheitsrelevant ist, sobald das System öffentlich erreichbar
ist (§10).

### 8.5 Server-generierte UUIDv7-Ids (nachgezogen)

Die Ids waren 32-stellige Hex-Strings aus `uuid4().hex`, in Python erzeugt und
als `VARCHAR(32)` gespeichert. Sie sind jetzt native `uuid`-Spalten mit
`DEFAULT uuidv7()`, also von Postgres 18 erzeugt.

**Warum serverseitig.** Der Einfüge-Pfad musste ohnehin schon flushen, um
`created_at` zu erfahren — der Server ist bei diesen Zeilen also längst die
Quelle, und die Id war die einzige Ausnahme. Zwei Erzeugungsstellen für dieselbe
Art Schlüssel sind eine Stelle zu viel: eine spätere zweite (ein Seed-Skript,
ein Import) müsste dieselbe Konvention nachbauen. Jetzt gibt es genau eine, und
sie steht in der Tabellendefinition.

**Warum v7 und nicht v4.** UUIDv7 trägt die Zeit in den führenden 48 Bit, ist
also sortierbar. Neue Zeilen landen am rechten Rand des B-Trees statt zufällig
über ihn verteilt — bei `uuid4` schreibt jede Einfügung in eine andere Seite,
was den Index zerstreut. Nebeneffekt: `ORDER BY id` ist Einfügereihenfolge, und
zwei kurz nacheinander angelegte Spiele teilen sich sichtbar den Präfix.
**Preis** ist die Entropie der Spiel-Id als Freigabetoken (§6.1) — der einzige
Punkt, an dem die Umstellung überhaupt etwas kostet.

**Warum `Uuid(as_uuid=False)`.** In der Datenbank steht ein natives 16-Byte-uuid
(halb so groß wie die 32 Zeichen davor, richtig typisiert, mit passenden
Operatoren). Auf der Python-Seite bleibt es ein `str`, sodass weder das Domain
noch das DTO noch der WebSocket-Raumschlüssel je ein `UUID`-Objekt anfassen. Ein
Feld-für-Feld-Umbau von `Game.id` und der Socket-Pfade wäre der Preis der
Alternative gewesen, ohne Gegenwert — die Id ist überall ein undurchsichtiger
String.

Ein Punkt kommt dadurch neu dazu: eine Zeichenkette, die **gar keine** uuid ist,
lässt der Treiber nicht mehr durch (früher lief sie als Vergleich ins Leere und
ergab schlicht keinen Treffer). Sie kommt aus einer URL, einem geteilten Link
und dem Socket-Pfad, also von außen. `GameRepository._load` prüft sie deshalb
mit `UUID(game_id)` und behandelt den Fehlschlag als „nicht gefunden" — ein 404
statt eines 500. Dasselbe in `UserRepository.get` für den Fall eines Tokens aus
einer früheren Schlüsselgeneration.

**Migration statt Reset.** `67f76ee220b7` behält die vorhandenen Daten: ein
32-stelliger Hex-String castet unverändert nach `uuid`, er bekommt nur seine
Bindestriche. Weil Postgres den Typ einer Spalte nicht ändert, an der ein
Fremdschlüssel hängt, werden die sieben Constraints davor abgeworfen und danach
neu gesetzt. Beide Richtungen sind gefahren: `downgrade` bildet über
`replace(id::text, '-', '')` die alte Form zurück, `upgrade` danach wieder die
neue, mit denselben Werten.

### 8.6 Was M4 im Detail festgelegt hat

**Die eigene Identität entsteht bei der Registrierung.** `POST /auth/register`
legt in derselben Transaktion eine `players`-Zeile mit
`user_id = owner_user_id = <neuer Account>` und `display_name = username` an.
Der Alternative — sie erst beim ersten Spiel anzulegen — fehlt der Zeitpunkt:
das Adressbuch wäre beim ersten Aufruf leer, und die Setup-View könnte den
eigenen Namen nicht vorbelegen. Konten aus der Zeit davor bekommen ihre Zeile
über die Datenmigration `d883252c5886` (`INSERT … SELECT … WHERE NOT EXISTS`),
denn sonst würde sie ihnen nie jemand anlegen.

**Ein Platz ist eine Identität *oder* ein Name, geprüft im Schema.**
`PlayerSlotDto` trägt `playerId` und `name` und lässt genau eines von beiden zu;
beides oder keines ist ein 422 aus dem Validator, ein leerer Name ebenfalls (er
wird vorher getrimmt). Der **Anzeigename einer gewählten Identität kommt aus der
Datenbank**, nie aus dem Request — sonst könnte man einen fremden Namen auf eine
eigene Identität schreiben.

**Die Zuordnung ist der Ort, an dem Autorisierung passiert.** `players.owned()`
sucht die angeforderten Ids **immer** zusammen mit `owner_user_id = ich`; wer
eine fremde Id schickt, bekommt „unknown player identity" (422) und erfährt
nicht einmal, ob sie existiert. Ohne diese Einschränkung könnte jeder ein Spiel
an eine fremde Identität hängen und deren Statistik verschieben — der
Endpoint hat keine andere Prüfung, die das abfängt. Verifiziert mit zwei
Konten: Bob kann Alices Identität nicht setzen und sieht ihr Adressbuch nicht.

Drei weitere Fälle, alle geprüft: dieselbe Identität auf zwei Plätzen ist ein
422 (die Tabelle hat `UNIQUE (game_id, player_id)`, aber ein Constraint-Fehler
wäre ein 500); ein `playerId` ohne Anmeldung ist ein 401, weil es ohne Konto
kein Adressbuch gibt; und eine Id, die gar keine uuid ist, wird in
`owned()` vorher aussortiert statt den Treiber zu sprengen (§8.5).

**Anonym bleibt vollwertig.** Ohne Anmeldung zeigt die Setup-View einfache
Textfelder mit den bisherigen Vorgaben, das Spiel bekommt keinen Eigentümer und
seine Gäste ebenfalls nicht (`owner_user_id = NULL`). Verifiziert von der
Oberfläche bis in die Datenbank.

**Was die View entscheidet, hängt an einer Antwort, die noch unterwegs ist.**
Ob Autocomplete oder Textfeld, und ob der erste Platz vorbelegt wird, steht erst
fest, wenn die Sitzungs-Wiederherstellung durch ist. Die Plätze werden deshalb
erst *nach* `AuthService.ready` gebaut und bis dahin gar nicht gerendert — sonst
stünde einen Moment lang „Spieler 1" da, das sich unter der Hand in den eigenen
Namen ändert.

**Vorschläge ohne die schon besetzten.** Die Autocomplete-Liste blendet aus, wer
bereits auf einem anderen Platz sitzt — sonst wäre der naheliegendste Klick
genau der 422 von oben. Die eigene Identität steht in der Suche vorn und trägt
in der Liste die Markierung „du".

**Namensgebung.** Das neue Feature heißt `player`, seine Klassen aber
`PlayerIdentity`/`PlayerIdentityDto`: `Player` ist im Spiel-Feature bereits der
*Sitzplatz* (Index plus Anzeigename, das, was das Scoreboard braucht). Die
Tabelle bleibt `players`, weil das Datenmodell in §4 so heißt.

### 8.7 Was M5 im Detail festgelegt hat

**`abandoned` steht in keiner Zeile.** Es ist das, was ein offenes Spiel wird,
das seit 24 h niemand angefasst hat — abgeleitet beim Lesen
(`effective_status`), nicht geschrieben. Damit braucht es keinen
Hintergrundjob, und es kann nicht veralten. Dafür kam eine Spalte dazu:
`games.updated_at`, bei jedem Schreibvorgang gesetzt. `created_at` hätte es
fast getan — ein Spiel dauert Minuten —, aber „zuletzt gespielt" ist auch die
Sortierung der Spielliste, und dafür ist der Erstellzeitpunkt das falsche
Datum.

**Die Schwelle für ein abgebrochenes Spiel steht bei 9 Darts** (drei
Aufnahmen), damit war der offene Punkt aus §10 zu beantworten. Darunter ist es
im Zweifel eine Kalibrierprobe, darüber eine kurze Sitzung mit einem gültigen
Average. Gezählt werden **eigene** Darts, nicht die des ganzen Spiels: was den
eigenen Schnitt bewegen darf, muss man selbst geworfen haben.

**Eine Regel, zwei Leser.** `counts_in_statistics` liegt im Spiel-Domain und
wird von der Auswertung *und* von der Spielliste benutzt — die Liste zeigt
`counted` als Feld an. Läge die Regel nur in der Statistik-Abfrage, könnte die
Liste ein Spiel als gewertet zeigen, das im Dashboard fehlt, und niemand fände
den Grund.

**`discarded` überlebt den nächsten Wurf.** `save()` leitet den Status aus dem
Spielstand ab (`finished`/`active`) und würde ein verworfenes Spiel damit beim
nächsten Dart wieder aufwecken. Der `UPDATE` schreibt deshalb ein `CASE`: ist
der Status `discarded`, bleibt er es. Verifiziert mit einem Dart in ein
verworfenes Spiel — Spalte danach unverändert `discarded`.

**Zurücknehmen heißt herleiten, nicht `active` schreiben.** Der erste Versuch
setzte beim Zurücknehmen schlicht `active`, und ein gewonnenes Leg verschwand
damit genauso zuverlässig aus der Statistik wie vorher durch `discarded` — nur
unsichtbar. `PATCH` lädt das Spiel jetzt und schreibt `finished`, wenn es
einen Sieger hat. Der Rundlauf ist gemessen: 39.00 → 35.75 → 39.00.

**Die Kennzahlen entstehen in Python, nicht in SQL.** Bust und Checkout sind im
Spiel-Domain bereits entschieden; eine zweite Fassung davon in einer Abfrage
wäre eine zweite Wahrheit. Die Auswertung holt deshalb in **drei** Abfragen für
die ganze Historie (Sitzplätze, Runden, Darts) das Rohmaterial und lässt die
Regeln darüber laufen — nicht vier Abfragen pro Spiel. Was rein
mengenmäßig ist (Punkte und Darts je Sitzplatz für die Spielliste), bleibt eine
SQL-Aggregation.

Ein Gegencheck, der die Rechnung stützt: über vier gespielte Legs kamen 1996
Punkte heraus, und 501·3 + (501−8) für das verlorene Leg ist genau das.

**Was gemessen wird, und was es heißt:**

| Kennzahl | Definition |
|---|---|
| 3-Dart-Average | 3 · Punkte / geworfene Darts; gebustete Aufnahmen zählen als geworfen, aber nicht als Punkte |
| Checkout-Quote | gewonnene Legs / Legs, in denen mindestens eine Aufnahme bei ≤ 170 begann |
| Doppel-Quote | Darts, die das Leg beendet haben / Darts, die auf ein Doppel geworfen wurden (Restwert 50 oder gerade ≤ 40) |
| Bestes Visit, 180er, 100+ | über nicht gebustete Aufnahmen |

Die Doppel-Quote gilt nur für Double-Out-Legs — bei Single Out gibt es kein
Doppel, auf das geworfen würde.

**Die Heatmap hat eine Obergrenze und einen Vorbehalt.** Übertragen werden die
letzten 2000 Punkte; darüber ist das Bild ohnehin eine schwarze Scheibe. Und
eine Position hat nur ein **von der Kamera gefundener** Dart — von Hand
gebuchte zählen in jeder anderen Kennzahl mit, lassen sich aber nicht
platzieren. Die Seite schreibt das hin, statt eine leere Scheibe zu zeigen.

**Verworfen wird vom Eigentümer.** `PATCH` greift nur auf Spielen mit
`owner_user_id = ich`; wer nur mitgespielt hat, sieht das Spiel in seiner Liste,
kann es aber nicht aus der Wertung nehmen. Das folgt §4.5, wo der Status eine
Eigenschaft des *Spiels* ist und nicht der Teilnahme — bleibt aber ein Punkt für
§10.

**Frontend.** Ein Dashboard unter `/stats` (Kennzahlen, Trefferbild,
Spielliste mit Werten-Schalter), plus ein fünfter Eintrag in der Bottom-Nav. Die
Board-Zeichnung, die bisher in `virtual-board.component.ts` steckte, liegt jetzt
als reine Daten in `game/models/board-face.ts` und wird von Spielansicht und
Heatmap geteilt; das war die Alternative dazu, vierzig Zeilen SVG-Pfadbau zu
kopieren.

---

## 9. Verworfene Ansätze

### 9.1 Referenz-Frame als JPEG in Redis

*Idee:* Statt 3.5 MiB roh das Frame als JPEG ablegen — ~200 KB, Transfer unter
einer Millisekunde, das Performance-Argument aus §3 wäre erledigt.

*Warum verworfen:* Die Referenz **rollt nach jedem Wurf weiter** auf das
ausgerichtete Bild ([erkennung.md §1](../erkennung.md)). Ein JPEG-Roundtrip pro Wurf
schreibt also generationsweise Kompressionsartefakte in genau das Bild, gegen das
mit Schwellwert 40 differenziert wird. Die Artefakte sitzen an Kanten — dort, wo
laut [erkennung.md §5.11](../erkennung.md) das Registrierungs-Residuum ohnehin bei
~52 Grauwerten pro Pixel liegt und die Fusion sich schon heute gelegentlich einen
falschen Anker holt. Zehn Millisekunden gegen ein Risiko auf der Kernmetrik der
Arbeit ist der falsche Tausch.

### 9.2 Spiel heiß in Redis, Checkpoint nach Postgres

*Idee:* Das laufende Spiel in Redis halten, bei Spielende (oder periodisch) nach
Postgres schreiben.

*Warum verworfen:* Löst ein Latenzproblem, das es nicht gibt — ein Wurf alle paar
Sekunden gegen 2–5 ms Schreibzeit. Kauft dafür zwei Repräsentationen desselben
Spiels, die auseinanderlaufen können, und einen Verlustfall (Absturz zwischen
zwei Checkpoints), den die direkte Variante gar nicht kennt.

### 9.3 SQLModel

*Idee:* Tabelle und Wire-Schema als eine Pydantic-Klasse, weniger Code.

*Warum verworfen:* Verletzt die bestehende Trennung `dto/` ↔ `domain/`. Die
Spielregeln würden an das Tabellenlayout gekoppelt, und ein zweites Wire-Format
(der `game_state`-Push über den WebSocket) müsste dann im Domain modelliert
werden — dasselbe Argument, das die Guidelines schon gegen Pydantic im `domain/`
führen.

### 9.4 Einmal-Ticket für den WebSocket-Handshake

*Idee:* Die Browser-WebSocket-API kann keine Header setzen, ein JWT im
Query-String steht in jedem Access-Log. Also ein kurzlebiges Ticket:
`POST /api/auth/ws-ticket` legt ein einmal einlösbares Token mit 30 s TTL in
Redis, der Handshake reicht es als Query-Param, der Server löst ein und löscht.

*Warum verworfen:* Löst ein Problem, das es nicht gibt. Der Entwurf war aus der
Annahme „ein WebSocket gehört authentifiziert" abgeleitet statt aus dem, was
über ihn läuft — und darüber läuft nichts Nutzerbezogenes (§6.1). Das Ticket
hätte den Join-per-Link zerstört, ohne eine Attribution zu liefern, die nicht
schon in der Datenbank steht.

*Was der Fehlschlag zeigt:* Die Authentifizierungsgrenze gehört dorthin, wo
nutzerbezogene Daten fließen, nicht an jeden Kanal aus Gewohnheit. Kosten des
Irrtums wären hier nicht nur Aufwand gewesen, sondern ein verlorenes Feature.

*Nebeneffekt:* Damit fällt einer der drei Gründe für Redis weg (§2.2). Die
verbliebenen zwei — TTL und atomarer Claim — tragen die Entscheidung weiter,
aber knapper.

### 9.5 Turns und Darts als JSONB auf der `games`-Zeile

*Idee:* Statt drei Tabellen ein Dokument. Die Domain behandelt `turns` ohnehin
als verschachtelte Liste, `dataclasses.asdict` wäre der ganze Mapper; ein Spiel
laden wäre ein Row-Read statt eines Joins, und der Lock in §5.2 läge auf einer
einzigen Zeile.

*Die Mengenannahme, die dagegen sprach, stimmt nicht.* Ein 501 mit drei Spielern
endet, wenn der Erste auscheckt — rund 7–9 Aufnahmen je Spieler:

| | pro Spiel | 500 Spiele | 10.000 Spiele |
|---|---|---|---|
| `game_turns` | ~25 | 12.500 | 250.000 |
| `game_darts` | ~70 | 35.000 | 700.000 |

Eine indizierte Heatmap-Abfrage über 700.000 Dart-Zeilen liegt im einstelligen
Millisekundenbereich. Datenmenge ist hier kein Argument, in keine Richtung.

*Warum trotzdem verworfen:* zwei Gründe, beide auf der Zugriffsseite.

1. **GIN-Indizes helfen bei der falschen Abfrageart.** Sie beschleunigen
   Containment („welches Dokument enthält X"). Die geplanten Auswertungen sind
   aber Aggregationen über entpackte Arrays — 3-Dart-Average, Checkout-Quote,
   Doppelquote, Heatmap. Jede davon bräuchte `jsonb_array_elements` doppelt
   verschachtelt (Turns, darin Darts) und müsste jedes Spieldokument des
   Spielers vollständig lesen und parsen. Indizieren lässt sich das nicht.
2. **Der Schreibpfad ist ohnehin schon delta-förmig.** Die Kommandos mappen 1:1
   auf kleine DML: `register_dart` → `INSERT` einer Dart-Zeile, `undo` →
   `DELETE` der letzten, `next_player` → `INSERT` Turn + `UPDATE` auf `games`.
   Der erwartete Vorteil des Dokuments (ein einfacher Schreibvorgang) fällt
   damit weg, während JSONB pro Wurf das ganze Dokument neu schreiben würde. Der
   optimistische Lock bleibt in beiden Fällen `WHERE revision = ?`.

   *Nachtrag aus der Umsetzung (§8.3):* M2 schreibt Runden und Würfe trotzdem
   komplett neu, weil `undo` über Rundengrenzen hinweg zurücknimmt und die
   Delta-Form dafür Sonderfälle bräuchte. Dieses Argument trägt also weniger
   weit als beim Entwurf angenommen — es beschreibt, was *möglich* ist, nicht
   was gebaut wurde. Ausschlaggebend ist Punkt 1.

*Plan B, falls das Mapping in M2 zur Plage wird:* JSONB als **Schreibmodell**
während des Spiels, und beim Setzen von `finished_at` einmal nach
`game_turns`/`game_darts` projizieren. Das ist ausdrücklich nicht der doppelte
Live-Zustand aus §9.2 — die Projektion läuft einmal, in eine Richtung, aus der
autoritativen Quelle, und ist aus den Dokumenten jederzeit neu aufbaubar. Kosten:
eine Repräsentation mehr im Code und keine Statistik über laufende Spiele.

### 9.6 Spiel nur in Redis, Postgres erst auf ausdrückliches „Speichern"

*Idee:* Das laufende Spiel liegt ausschließlich in Redis. Erst wenn der Spieler
aktiv speichert, wird es nach Postgres geschrieben. Der Schreibpfad während des
Spiels wäre ein einziger Key — kein `FOR UPDATE`, keine Delta-DML, kein
Repository über vier Tabellen —, und in der Datenbank stünde nur, was jemand
behalten wollte.

*Warum verworfen:*

1. **Datenverlust wird der Normalfall.** Der natürliche Speicherzeitpunkt ist
   das Spielende — und das ist exakt der Moment, in dem alle das Handy weglegen
   und Pfeile ziehen. Opt-in trifft die Ergonomie genau falsch herum.
2. **Redis würde zur Primärdatenbank für die wertvollsten Daten.** Verlässt man
   sich auf RDB/AOF, ist für das einzige dauerhaft wichtige Datum die Komponente
   ohne Schema, Constraints und Transaktionen gewählt — und das Standard-Image
   macht per Default nur RDB-Snapshots, verliert also laufende Spiele beim
   Neustart. Verlässt man sich nicht darauf, ist genau das Problem zurück, das
   M2 lösen soll.
3. **Zwei Repräsentationen bleiben trotzdem** (Dokument in Redis, Tabellen in
   Postgres) — der Grund, aus dem §9.2 gefallen ist.

*Was übernommen wurde:* die Motivation, und die ist berechtigt — nicht jedes
Spiel gehört in die Auswertung. Sie lebt in `games.status` (§4.5) weiter, nur
als **Opt-out** statt Opt-in: geschrieben wird immer, aussortiert wird der
Ausnahmefall. Damit ist zugleich ein offener Punkt erledigt (das Spiel, das nie
endet).

### 9.7 Alles nach Postgres, kein Redis

*Idee:* Eine Datenbank weniger im Stack.

*Warum verworfen:* Die vier kleinen Stores sind heißer Zustand mit
Lebensdauer = Spiel. Sie in Postgres zu schreiben heißt: Row-Churn auf jedem
Rundenwechsel, ein eigener Cleanup-Job statt TTL, und für den atomaren
Scoring-Claim (§2.2) eine Transaktion um einen Wert, der nach dem Spiel wertlos
ist. Der Betrieb einer zweiten Komponente ist der geringere Preis.

---

## 10. Offene Punkte

- **Detektionslaufzeit ist unbekannt.** Ohne sie lässt sich der Anteil eines
  Redis-Roundtrips nicht beziffern (§3). Sollte vor M1 gemessen werden — die
  Zahl fehlt ohnehin für die Evaluation in Phase 4.
- **Verwerfen kann nur der Eigentümer.** Wer an einem fremden Spiel nur
  teilgenommen hat, sieht es in seiner Liste und in seinem Schnitt, kann es aber
  nicht herausnehmen (§8.7). Ein Status je Teilnahme wäre die Lösung, ist aber
  ein zweites Feld im Datenmodell — offen, ob es das wert ist.
- **Die Statistik ist eine Gesamtsumme.** Kein Verlauf, kein Filter nach Gegner,
  Modus oder Zeitraum, keine Werte je Mitspieler. Die Daten tragen das alles
  (jede Runde und jeder Dart stehen einzeln), es ist nur nicht abgefragt.
- **Gast-Player übergeben.** Gewünschtes Feature, noch nicht terminiert: Gast B
  legt sich nach zehn gemeinsamen Spielen einen Account an, und ich als
  `owner_user_id` ordne meine Identität „B" seinem Account zu (`players.user_id`
  setzen). **Owner-initiiert, nicht beansprucht** — die Gegenrichtung wäre das
  Loch, über das jeder fremde Statistiken einsammelt, indem er behauptet, B zu
  sein.
  Zwei Punkte für den Entwurf: die Zuordnung wirkt **rückwirkend** (B sieht
  sofort alle zehn Spiele, inklusive meiner Scores darin) — das ist eine
  Freigabe, keine bloße Verknüpfung, und die UI muss es so benennen. Und
  `owner_user_id` bleibt danach bei mir, damit B in meinem Adressbuch steht;
  offen ist nur, wem der Anzeigename dann gehört.
- **Doppelte Namen im Adressbuch.** Wer zweimal „Max" frei eintippt, statt aus
  dem Autocomplete zu wählen, bekommt zwei Identitäten. Automatisch über den
  Namen zusammenzuführen wäre falsch (zwei verschiedene Maxe), das Autocomplete
  *ist* der Zusammenführungsmechanismus. Ob es beim exakten Treffer stärker
  drängen soll, ist eine UI-Frage.
- **Client ↔ User.** Der Docstring in `client.py` sieht vor, dass „ein `user_id`
  diesem Record beitritt statt ihn zu ersetzen". Ob ein Gerät fest zu einem
  Account gehört oder pro Spiel neu zugeordnet wird, ist offen.
- **Kein Rate-Limit auf `/auth/login`.** Argon2 macht jeden Versuch teuer, aber
  eine Bremse (nach IP und nach Konto) fehlt; solange nur im LAN gespielt wird,
  ist das vertretbar, an einer öffentlichen Adresse nicht mehr.
- **`cookie_secure` steht auf `false`.** Das Deployment liefert reines HTTP, ein
  `Secure`-Cookie würde der Browser verwerfen. Sobald TLS davor steht, gehört
  `COOKIE_SECURE=true` gesetzt — die Variable ist in `compose.yaml` schon
  vorgesehen.
- **Migrations-Disziplin.** Solange nichts produktiv läuft, ist ein
  Schema-Reset billiger als eine Migrationskette. Ab wann Alembic-Migrationen
  wirklich vorwärtskompatibel sein müssen, ist zu entscheiden.
