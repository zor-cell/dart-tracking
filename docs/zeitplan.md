### **Zeitplan (Stand 08.06)**

**Phase 1: Architektur, Setup (KW 24 \- 25 | bis 21.06.)**

* *Modus:* Fokus auf Low-Code-Tasks und formale Grundlagen.  
* *Meilensteine:*  
  * Abstimmung des Zeitplans mit dem Betreuer und Registrierung der Arbeit im TISS.  
  * Aufsetzen des Repositories im TU Wien GitLab und Freigabe für den Betreuer. Download und Einrichtung der offiziellen LaTeX-Vorlage der Fakultät.  
  * Definition der API-Contracts. Wie sollen die Schnittstellen aussehen?  
  * Generieren von Test-Set von 100-200 Würfen mit Smartphone aufgenommen unter verschiedenen Lichtverhältnissen. Das fungiert als initiales Test-Set.

**Phase 2: Core Development Sprint (KW 26 \- 28 | 22.06. \- 12.07.)**

* *Modus:* Fokus auf MVP  
* *Meilensteine:*  
  * Implementierung der hybriden Architektur (Frontend mit Canvas API, Backend mit FastAPI/Flask).  
  * Aufbau der Computer-Vision-Pipeline (Board-Segmentierung, Kalibrierung via Homographie-Matrix).  
  * Die client-seitige Frame-Differenz-Analyse löst zuverlässig aus.  
  * Erste erfolgreiche OpenCV-Extraktionen der Pfeil-Position aus den in Phase 1 erstellten Videodaten.

**Phase 3: Edge Cases & System-Stabilisierung (KW 29 | 13.07. \- 19.07.)**

* *Modus:* Fokus auf Robustheit des Systems  
* *Meilensteine:*  
  * Lösungsansatz für die Beleuchtungsvarianz und Schattenbildung ist integriert.  
  * Umgang mit Pfeil-Verdeckungen (partielle Verdeckung) ist definiert und implementiert.  
  * Ende-zu-Ende-Latenz ist optimiert.

**Phase 4: Praxis-Test & Evaluation (KW 30 \- 32 | 20.07. \- 09.08.)**

* *Modus:* Fokus auf Testen der Anwendung  
* *Meilensteine:*  
  * Generierung der finalen Ergebnisse (Benchmarks, Screenshots, Auswertungen).  
  * Messung der Genauigkeit: Wie oft triggert das System falsch? Wie hoch ist die Trefferquote bei der Segment-Klassifikation?

**Phase 5: Akademisches Schreiben & Feinschliff (KW 33 \- 35 | 10.08. \- 31.08.)**

* *Modus:* Verfassen der Arbeit in LaTeX  
* *Meilensteine:*  
  * Verfassen der Arbeit im Umfang von 15 bis 25 Seiten.  
  * **31.08.2026: Finale Einreichung.**