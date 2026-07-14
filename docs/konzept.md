Bachelorarbeit – Konzept-Draft

**Automatisches Dart-Tracking-System**

Philippe Zorman  |  Matrikelnummer: 12225143 

# **1\. Ausgangslage & Motivation**

Beim Dartsport ist das manuelle Mitzählen der geworfenen Punkte oft fehleranfällig und stört den Spielfluss. Professionelle Auto-Scoring-Systeme sind teuer und erfordern spezielle Hardware-Setups (meist mehrere Kameras an einem Ring). Ziel dieser Arbeit ist es, ein zugängliches Tracking-System zu entwickeln, das lediglich eine handelsübliche Smartphone-Kamera und eine einfache Weboberfläche benötigt.

# **2\. Minimallösung (MVP)**

Das MVP umfasst die grundlegende Funktionalität, um ein normales Spiel (z. B. 501\) ohne manuelles Eingreifen zu spielen:

•        **Board-Kalibrierung:** Die Handykamera wird auf das Dartboard gerichtet. Das System erkennt das Board automatisch mittels Hough-Kreiserkennung oder Konturverfolgung und berechnet eine Homographie-Matrix, die Bildkoordinaten in Board-Koordinaten überführt

•        **Ereigniserkennung (client-seitig):** Per Frame-Differenz-Analyse im Browser (Canvas API) wird erkannt, sobald ein neuer Pfeil im Bild erscheint und zur Ruhe kommt. Das vermeidet Echtzeit Video-Streams ans Backend

•        **Pfeil-Erkennung & Scoring (server-seitig):** Das ausgelöste Standbild wird an ein Python-Backend übermittelt. Dort wird mittels OpenCV die exakte Pfeil-Position extrahiert, auf Board-Koordinaten transformiert und der entsprechende Punktewert berechnet

•        **Web-Interface:** Eine responsive Webseite zeigt Spielstand, verbleibende Punkte und die geworfenen Darts pro Runde in Echtzeit an (WebSocket-Verbindung zum Backend)

# **3\. Technologischer Ansatz**

## **3.1 Hybrid-Architektur (Client \+ Backend)**

Aufgrund der Echtzeit-Anforderungen wird ein Hybrid-Ansatz verfolgt, der kontinuierliches Video-Streaming vermeidet und damit Latenz minimiert:

•        Der Browser übernimmt ausschließlich die leichtgewichtige Ereigniserkennung (Frame-Differenz) sowie die Darstellung der Spieloberfläche

•        Erst bei einem erkannten Wurf-Event wird ein einzelnes JPEG-Standbild per WebSocket an das Python-Backend gesendet

•        Das Backend führt die rechenintensive Bildverarbeitung (Board-Segmentierung, Pfeil-Lokalisierung, Scoring) durch und liefert das Ergebnis zurück

## **3.2 Technologie-Stack**

•        **Frontend (Browser):** Moderne, responsive Webanwendung, Media API für Kamerazugriff, Canvas API für Frame-Differenz-Berechnung, WebSocket für Echtzeit-Kommunikation

•        **Backend (Python):** FastAPI oder Flask als WebSocket-Server, OpenCV für Bildverarbeitung, NumPy für Matrizenoperationen

•        **Computer-Vision-Pipeline:** Kalibrierung via Homographie-Matrix, Pfeil-Detektion via Konturanalyse oder Hough-Linien, Board-Segment-Klassifikation

# **4\. Technische Herausforderungen**

Folgende Teilprobleme werden in der Arbeit wissenschaftlich untersucht:

•        **Board-Kalibrierung:** Robuste automatische Erkennung des Dartboards unter verschiedenen Beleuchtungsbedingungen und Kamerawinkeln, Berechnung einer stabilen Homographie für die Koordinatentransformation

•        **Pfeil-Erkennung:** Mehrere Pfeile können sich gegenseitig verdecken, die Erkennung aller Pfeil-Positionen muss auch bei partieller Verdeckung zuverlässig funktionieren

•        **Beleuchtungsvarianz:** Wechselnde Lichtverhältnisse (Kunstlicht, Schatten durch Pfeile) erfordern robuste Vorverarbeitungsschritte

•        **Trigger-Zuverlässigkeit:** Die client-seitige Ereigniserkennung muss Fehlauslöser (z. B. Bewegung neben dem Board) minimieren

# **5\. Erweiterte Features & Statistiken**

Sobald die Minimallösung stabil läuft, bildet das System die Grundlage für tiefergehende Analysen:

•        **Heatmap-Generierung:** Visualisierung der Einschlagpunkte über einen längeren Zeitraum, z. B. zur Analyse systematischer Wurfabweichungen auf Triple-20

•        **Statistik-Dashboard:** Auswertung von 3-Dart-Average, Checkout-Quoten und Doppel-Trefferquoten

•        **Trainingsmodus:** Datengestützte Schwachstellenanalyse mit Vorschlägen für spezifische Trainingsspiele