TODOs:

Wenig Aufwand:
- revanche sollte auf alle im game room angewendet werden, dass man das kamera phone gleich weiterverwenden kann
- sprache englisch machen
- /game/new soll angezeigt bleiben, wenn man page wechselt?
- stats page spiel werten geht nicht, nur von wertung rausnehmen geht

Viel Aufwand:
- client diff löst ja derzeit öfter aus, fokus auf recall, das backend muss da was checken (ist das überhaupt möglich), weil
  wenn ein pfeil abgefallen ist, gabs bewegung, frame war aber leer, dh das müsste als 0 erkannt werden, obwohl frame leer ist, wahrscheinlich
  muss die client diff doch nochmal besser werden. ganz wichtiger punkt!
- detection am server verbessern, gibt noch einige falsche fälle
- möglichkeit für knappe tripe/double erkennung, wieder mit farbmaske arbeiten, wenn eine maske unterbrochen ist, aber nikcht durchgängig, dann steckt wahrscheinlich
  ein pfeil drinnen

Zukunft:
- Players ansicht im konto profil. dort muss man player löschen können. man muss auch einen existierenden user
seine games zuschreiben können, der muss halt akzeptieren. 
- statistiken nach datum sortieren können, die default ansicht einfach letzten monat (eher letzte 30 tage montasübergreifend)
- kamera und scoreboard auch ändern können