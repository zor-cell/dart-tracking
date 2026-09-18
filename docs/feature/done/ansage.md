# Sprachansage

Die Kamera bucht einen Dart, und ein Gerät im Raum sagt ihn an („Triple 20").
Wer spielt, muss dann nicht aufs Scoreboard schauen.

---

## 1. Genau ein Ansager pro Spiel

Wenn alle Geräte ansagen, gibt es im selben Raum ein Echo mit Versatz. Deshalb
bestimmt der Server pro Spiel **einen** Ansager und schickt die Ansage nur an
dieses Gerät. Gesprochen wird im Browser (Web Speech API, `speechSynthesis`).
Dafür braucht es kein TTS im Backend und keine Audiodateien.

### Auswahlregel

Der Server rechnet bei jeder Änderung im Raum neu aus
(`features/announcement/domain/announcer.py`). Es gilt die erste zutreffende
Regel:

1. **Ausdrücklich gewählt:** Ein Gerät hat „Ansage hier" getippt und ist
   gerade im Raum.
2. **Erstes Scoreboard** in Beitrittsreihenfolge.
3. **Buchende Kamera** ([multi-device.md §5a](multi-device.md)).
4. **Erste Kamera**, solange noch keine kalibriert hat.

Das Scoreboard hat Vorrang vor der Kamera. Das Kamera-Handy steht meist ein
paar Meter entfernt im Stativ, und sein Lautsprecher kommt nicht weit. Die
Kamera ist nur die Rückfallebene für ein Spiel ohne zweites Gerät.

### Warum die Rolle wechseln darf

Die buchende Kamera gibt ihre Rolle nie ab, denn eine Übergabe mitten in der
Runde könnte einen Wurf doppelt buchen. Beim Ansager kostet eine Übergabe
höchstens eine verpasste oder doppelte Ansage. Die Regel wird deshalb bei jedem
Beitritt, Verlassen, Rollenwechsel und jeder Kalibrierung neu ausgewertet, und
der Raum erfährt das Ergebnis als `announcer_state`.

Die ausdrückliche Wahl liegt in Redis (`game:{id}:announcer`, 24 h) und bleibt
bestehen, wenn das Gerät kurz wegbricht. Kommt es mit derselben `client_id`
zurück, sagt es wieder an. Solange es fehlt, greift die Regel darunter.

Gerechnet wird nur mit Geräten, die gerade im Raum sind. Der Raum ist
prozesslokal (`game_hub.py`), die Auswahl also auch.

---

## 2. Was angesagt wird

Nur **Darts, die die Kamera gebucht hat**, und nur, wenn das Spiel sie auch
angenommen hat. Ein vierter Trigger in einer vollen Runde ändert die Revision
nicht und bleibt stumm.

| Ereignis | Ansage |
|---|---|
| Single / Double / Triple | „Single 5", „Double 20", „Triple 20" |
| Bull / Bullseye | „Bull", „Bullseye" |
| Daneben | „Daneben" |
| Runde voll (dritter Dart) | danach die Punktsumme, z. B. „140" |
| Überworfen | „Bust" |
| Spiel gewonnen | „Game shot" |

Manuelle Eingaben werden **nicht** angesagt: Wer tippt, weiß schon, was er
getippt hat. Das `detection_result` der nicht buchenden Kameras löst ebenfalls
keine Ansage aus. Sonst würde ein Wurf, den zwei Kameras sehen, zweimal
angesagt.

Die Nachricht `dart_announcement` trägt die Rohdaten (Feld, Rundensumme, Bust,
Sieg). Den Satz baut der Client (`announcement-text.ts`). So bleibt die Sprache
Sache der Oberfläche, und eine Übersetzung betrifft nur den Client.

---

## 3. Bedienung

In der Kopfleiste jedes Geräts sitzt ein Lautsprecher-Button:

| Zustand | Anzeige | Tippen |
|---|---|---|
| anderes Gerät sagt an | `pi-volume-off`, grau | holt die Ansage auf dieses Gerät (`claim_announcer`) |
| dieses Gerät sagt an | `pi-volume-up`, gefüllt | schaltet stumm |
| dieses Gerät sagt an, stumm | `pi-volume-off`, gefüllt | schaltet wieder laut |

Stumm ist eine **Einstellung des Geräts** (localStorage) und keine Rolle. Das
stumme Gerät bleibt Ansager, es sagt dann eben niemand an. Genau das ist die
Absicht, wenn jemand die Ansage abschalten will. Würde der Server die Rolle
stattdessen weiterreichen, spräche einfach das nächste Handy.

### Autoplay-Sperre

Browser spielen Sprache erst nach einer Nutzeraktion ab. iOS Safari ist dabei
am strengsten: Die erste Äußerung muss direkt in einem Touch-Handler starten.
Der Client spricht deshalb bei `pointerdown` eine stumme Äußerung (Lautstärke
0). Irgendein Tippen reicht also, etwa auf „Kamera starten" oder auf den
Lautsprecher. Ein Gerät, das die Rolle automatisch bekommt und nie berührt
wurde, bleibt allerdings stumm.

Der Handler bleibt hängen, bis die Freischaltung nachweislich geklappt hat:
Erst wenn die stumme Äußerung ein `start`-Ereignis meldet, wird er entfernt.
Vorher galt sie nach dem ersten Tippen als erledigt — misslang sie, blieb das
Gerät für den Rest der Sitzung stumm, ohne dass man es noch einmal versuchen
konnte. Die Äußerung trägt außerdem echten Text: WebKit verwirft eine leere
Äußerung, ohne sie je abzuspielen, und schaltet damit auch nichts frei.

---

## 4. WebKit-Eigenheiten

Die Web Speech API ist auf iOS deutlich empfindlicher als auf Desktop-Browsern.
Drei Punkte, an denen dieselbe Implementierung auf einem Windows-Laptop läuft
und auf einem iPhone stumm bleibt:

**Nur der Kopf der Warteschlange wird gesprochen.** Ein Dart erzeugt bis zu zwei
Phrasen („Triple 20", dann „140"). Werden beide unmittelbar nacheinander an
`speechSynthesis.speak` übergeben, spielt WebKit die zweite oft nicht mehr ab
und bleibt anschließend in einem Zustand hängen, in dem auch jede weitere
Äußerung verschluckt wird — ab dem ersten Wurf ist dann Ruhe. Der Client hält
die Phrasen deshalb selbst in einer Liste und schickt die nächste erst im
`end`-Ereignis der vorigen los.

Weil `end` und `error` auf iOS ebenfalls ausbleiben können, sichert ein Timer
den Übergang ab (2 s Grundzeit plus 120 ms je Zeichen). Ohne ihn würde eine
einzige verlorene Rückmeldung die Ansage dauerhaft blockieren.

**Der Synthesizer bleibt pausiert.** Wechselt die Seite in den Hintergrund —
Bildschirmsperre, App-Wechsel, eingehender Anruf —, pausiert WebKit die
Sprachausgabe und nimmt sie beim Zurückkommen nicht von selbst wieder auf. Vor
jeder Äußerung steht deshalb ein `resume()`. Auf anderen Browsern ist der Aufruf
wirkungslos.

**`getVoices()` ist beim ersten Aufruf leer.** Die Stimmliste lädt
asynchron. Der Client fragt sie deshalb pro Äußerung neu ab und setzt
`utterance.voice` nur, wenn eine deutsche Stimme dabei ist; sonst bleibt das
Feld unberührt und die Auswahl läuft über `utterance.lang`. Ein ausdrücklich auf
`null` gesetztes `voice` hat in manchen WebKit-Versionen dieselbe Wirkung wie
eine ungültige Stimme.

### Was außerhalb des Codes liegt

Bleibt ein iPhone trotzdem stumm, sind zwei Ursachen wahrscheinlicher als ein
Fehler in der Pipeline:

- **Der Stummschalter am Gehäuse.** iOS führt die Sprachausgabe der Web Speech
  API über den Klingelton-Kanal. Steht der Schalter auf stumm, ist die Ansage
  lautlos, während jedes Video auf demselben Gerät normal tönt.
- **Das Gerät ist gar nicht der Ansager.** Ist ein Laptop als Scoreboard im
  Spiel, gewinnt er nach Regel 2 gegen das Kamera-Handy. Der Lautsprecher-Button
  ist dann auf dem iPhone grau; ein Tippen holt die Rolle herüber (§3).

---

## 5. Offene Punkte

- **Restpunktzahl ansagen** („noch 32"). Ist nicht eingebaut, weil sie bei jeder
  Aufnahme mitläuft und schnell zu viel wird. Denkbar nur ab Checkout-Bereich.
- **Korrekturen ansagen.** Ein Undo oder eine manuell nachgetragene Korrektur
  bleibt stumm.
- **Stimme wählen.** Genommen wird die erste deutsche Stimme, die das Gerät
  anbietet. Wie gut die klingt, hängt vom Gerät ab.
