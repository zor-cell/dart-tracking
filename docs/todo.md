TODOs:

Wenig Aufwand:
- detection linien sind sehr falsch derzeit, ich glaub es werden auch welche geschickt, wenn nicht erkannt wurde
- testdaten erstellung während eines spiels, dann komm ich locker auf 500+ pfeile
- socket.py cleanen, die debug writes wirken dort fehl am platz

Viel Aufwand:
- client diff löst ja derzeit öfter aus, fokus auf recall, das backend muss da was checken (ist das überhaupt möglich), weil
  wenn ein pfeil abgefallen ist, gabs bewegung, frame war aber leer, dh das müsste als 0 erkannt werden, obwohl frame leer ist, wahrscheinlich
  muss die client diff doch nochmal besser werden. ganz wichtiger punkt!
- detection am server verbessern, gibt noch einige falsche fälle
- die kalibrierung muss sich wahrscheinlich automatisch anpassen, wenn ein ruckeln registriert wird, weil das affected ja alle pfeile danach
    (also auf jeden) den ersten pfeil, weil der ja davon die homographie hat
- möglichkeit für knappe tripe/double erkennung, wieder mit farbmaske arbeiten, wenn eine maske unterbrochen ist, aber nikcht durchgängig, dann steckt wahrscheinlich
  ein pfeil drinnen