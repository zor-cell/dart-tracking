# Einstellungen am Konto

Die Schalter der App liegen nicht mehr im Browser, sondern am Konto. Ohne
Anmeldung läuft die App auf den Standardwerten und lässt sich nicht umstellen.

Referenz-Implementierung: `backend/src/app/api/features/settings/`,
Client: `frontend/src/app/features/settings/services/settings.service.ts`.

---

## 1. Warum am Server

Vorher lagen alle sechs Schalter in `localStorage`. Das hat drei Folgen, die
alle im Betrieb auffallen:

- **Gerätegebunden.** Ein Spiel wird über mehrere Geräte gespielt
  ([multi-device.md](multi-device.md)). Wer am Handy „Manuell Würfe akzeptieren"
  ausschaltet, hat es am Tablet wieder an.
- **Nicht abfragbar.** Für die Auswertung ist es relevant, mit welchen
  Einstellungen ein Testlauf gespielt wurde; im Browser des Spielers ist das
  nicht nachzulesen.
- **Weg beim Leeren.** Ein geleerter Browser-Speicher nimmt sie mit, ohne dass
  irgendwo etwas fehlt — man merkt es erst am veränderten Verhalten.

Die Einstellungen gehören damit in dieselbe Kategorie wie Spiele und Spieler:
dauerhaft und abfragbar, also Postgres
([persistenz.md §2](persistenz.md#2-die-aufteilung)).

## 2. Anonym heißt: implizit die Standardwerte

Accounts sind im ganzen Projekt optional — ein anonymes Spiel funktioniert
([persistenz.md §6](persistenz.md)). Für Einstellungen gibt es aber ohne Konto
keinen Ort, an dem eine Antwort liegen könnte. Statt eines zweiten,
gerätelokalen Speicherpfads daneben gilt schlicht:

| | lesen | schreiben |
|---|---|---|
| angemeldet | die eigene Zeile, sonst die Defaults | `PUT`, upsert |
| anonym | die Defaults | **401** |

Ohne Konto ist die Seite **gar nicht vorhanden**: der Eintrag auf der
Konto-Seite hängt an `@if (user())`, die Route `account/settings` am
`authGuard`. Eine anonyme Sitzung läuft damit stillschweigend auf den Defaults,
statt eine Seite voller gesperrter Schalter zu bekommen — es gibt nichts zu
entscheiden, also auch nichts anzuzeigen.

Der Server bleibt trotzdem streng: `GET` antwortet auch anonym (mit den
Defaults), `PUT` mit 401. Die Oberfläche ist eine Bequemlichkeit, nicht die
Absicherung.

## 3. Ablage

`user_settings`, eine Zeile je Konto, sechs Boolean-Spalten statt eines
JSON-Feldes — typisiert, migrierbar und abfragbar. Der Primärschlüssel **ist**
die Konto-Id: ein Konto hat genau einen Satz, und ein gelöschtes Konto nimmt ihn
per `ON DELETE CASCADE` mit (verifiziert).

**Kein Insert bei der Registrierung.** Ein Konto, das nie etwas umgestellt hat,
hat keine Zeile und bekommt `DEFAULTS` — dieselbe Antwort wie eine anonyme
Sitzung. Geschrieben wird per Upsert (`ON CONFLICT DO UPDATE`), die erste
Änderung ist also zugleich der Insert. Damit gibt es keinen Pfad, auf dem ein
Konto ohne Zeile zum Fehler wird.

Übertragen wird immer der **vollständige** Satz, nicht ein Patch: so hat kein
Schalter je einen undefinierten Zustand auf der Leitung, und die Antwort des
`PUT` ist das, was gespeichert wurde.

## 4. Auf dem Client

`SettingsService` hält weiterhin ein Signal, das die Views synchron lesen — an
den Verwendern (`game.component.html`, `calibration.service.ts`, …) ändert sich
nichts. Nur die Quelle ist eine andere:

- Startwert `DEFAULT_SETTINGS`, damit vor der ersten Antwort nichts leer ist —
  und zugleich das, worauf eine anonyme Sitzung dauerhaft läuft.
- Ein `effect` auf `auth.user()` lädt bei Anmeldung nach und setzt bei Abmeldung
  auf die Defaults zurück. Das deckt zugleich den Seitenaufruf ab, weil die
  Sitzungswiederherstellung dasselbe Signal setzt.
- Eine Änderung wird **erst lokal** gesetzt und dann geschickt, damit der
  Schalter sofort antwortet; scheitert das `PUT`, wird neu geladen, statt den
  Schalter lügen zu lassen.

**Nebenwirkung, mitbehoben:** die Konto-Seite rendert alles aus `user()`, stieß
die Sitzungswiederherstellung aber selbst nie an — bei direktem Aufruf stand dort
„Nicht angemeldet". Vorher fiel das kaum auf, seit der Einstellungen-Eintrag
daran hängt schon. `AccountComponent` liest jetzt `auth.ready`, wie es
`game-new` bereits tat.

## 5. Offene Punkte

- **Alte lokale Werte werden verworfen, nicht übernommen.** Der Schlüssel
  `dart-tracking.settings` wird beim Start einmal entfernt; wer dort etwas
  stehen hatte, startet auf den Defaults. Die Aufräumzeile kann weg, sobald
  keine alten Browser-Stände mehr zu erwarten sind.
- **Kein Gerätebezug mehr.** `debugClientDetection` betrifft nur die Anzeige auf
  *einem* Gerät, gilt jetzt aber kontoweit. In der Praxis unkritisch, weil es
  ein Diagnoseschalter ist — nur ist die Kategorie „gerätelokal" damit
  ersatzlos verschwunden. Käme je eine Einstellung dazu, die wirklich ans Gerät
  gehört, bräuchte es beide Pfade.
