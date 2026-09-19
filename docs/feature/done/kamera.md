# Kamera am Gerät

Was die Web-App von der Handykamera bekommt und was nicht: der Stream, das
Licht, und wo die Plattformen auseinanderlaufen.

Referenz-Implementierung: `frontend/src/app/features/camera/`.

---

## 1. Der Stream

```ts
navigator.mediaDevices.getUserMedia({
  video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
  audio: false,
});
```

`facingMode: 'environment'` wählt die Rückkamera, die Auflösung ist ein Wunsch
und keine Bedingung — ein `exact` würde auf Geräten scheitern, die genau diese
Kombination nicht liefern, und die Kalibrierung skaliert ohnehin auf 1280 px
Kantenlänge herunter. **Kein Audio:** gebraucht wird es nicht, und eine
Audio-Spur schaltet iOS in eine Aufnahme-Sitzung, was die Sprachausgabe der
Ansage betrifft ([ansage.md](ansage.md)).

Der Stream gehört dem `CameraService` und überlebt den Wechsel der Ansicht; das
`<video>`-Element wird nur angehängt (`attachTo`). Beendet wird er erst mit der
Sitzung.

---

## 2. Das Licht

Ein Blitz im Foto-Sinn existiert im Web nicht. Was es gibt, ist die **Taschen-
lampe** (`torch`) als Dauerlicht auf der Videospur:

```ts
track.getCapabilities().torch === true          // hat das Gerät eine?
track.applyConstraints({ advanced: [{ torch: true }] });
```

Beides steht **nicht** in den DOM-Typings — `torch` ist eine Erweiterung der
Media-Capabilities, die nicht jede Engine implementiert. Die beiden Casts stehen
gesammelt in `camera/models/torch.ts`, damit der Rest des Codes ohne `any`
auskommt.

**Gefragt wird das Gerät, nicht die Liste der Browser.** Der Knopf erscheint nur,
wenn `getCapabilities()` die Lampe meldet; lehnt `applyConstraints` sie danach
trotzdem ab, verschwindet er wieder, statt einen Schalter anzubieten, der nichts
tut. Damit taucht er auf jedem Gerät auf, das es kann, auch auf einem, das es
erst später lernt — ohne dass hier eine Browser-Version gepflegt werden muss.

| Plattform | Lampe |
|---|---|
| Android, Chromium-Browser | ja, das ist die Herkunft der Capability |
| iOS / iPadOS | ja, am Testgerät bestätigt |
| Desktop | in aller Regel nein — Webcams haben keine |

Dass iOS mitspielt, war nicht zu erwarten: WebKit hat die Capability lange nicht
gemeldet, und die verbreiteten Fundstellen sagen bis heute, es ginge nicht. Genau
deshalb wird gefragt statt nachgeschlagen — eine Browser-Liste im Code hätte den
Knopf auf dem iPhone weggelassen, obwohl er dort funktioniert.

Der Knopf sitzt in der Titelzeile neben dem Lautsprecher, nicht im Kamerabild:
er gehört zum Gerät und nicht zum Bild, und die Ecken über dem Board sind für
Rekalibrieren, Rollenwechsel und Vollbild belegt.

---

## 3. Offene Punkte

- **Bildschirmsperre.** Nichts hält den Bildschirm wach. Das Kamerabild tut es
  auf vielen Geräten nebenbei, das Scoreboard-Gerät nicht — und mit gesperrtem
  Bildschirm friert dessen Seite ein, samt Ansage. `navigator.wakeLock` wäre der
  Weg; verbaut ist er nicht.
- **Belichtung fest.** Weißabgleich und Belichtung bleiben der Automatik des
  Geräts überlassen. Gegen Beleuchtungsvarianz
  ([kalibrierung.md §7](kalibrierung.md#7-offene-punkte)) wäre eine feste
  Belichtung die naheliegende Stellschraube — dieselbe Capability-Mechanik wie
  beim Licht, nur mit mehreren Werten.
