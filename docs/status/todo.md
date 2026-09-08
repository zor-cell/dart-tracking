TODOs:

Wenig Aufwand:
- momentan ist der gewinner in einem eigenen div angegeben, er sollte einfach in dem player panel
wo man die punkte sieht gehighlighted werden, vllt mit icon aber auch jeden fall kein eigener banner
- wenn der wurf gewinnt muss er aktuell nicht bestätigt werden, sollte aber so sein#
- am iphone ist das keyboard für entry gerade abgeschnitten und die kamera zu klein. die kamera muss eine mindesthöhe haben
es muss wohl an den extra viewport einschränkungen liegen (url bar, untere leiste)
- ok button vllt größer?, manchmal unabsichtlich auf zurück gedrückt.
- man muss das spiel wiederholen können (auch alle beteiligten im room), es soll auch möglich sein eine andere
spielart da auszuwählen
- die anzeigten tips im scoreboard verschwinden ja mit undo. das ist aber blöd wenn ich nur einen phantom guess weghaben
will, wenn das phantom problem weg ist, ist aber auch das weg
- phantom pfeile unglaublich nervig bei bedienung!!!
- daten aus test runs in prod exportieren.

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