# SAJ Elekeeper for Home Assistant

Home-Assistant-Custom-Integration für die private SAJ-Elekeeper-Web-API. Diese Integration überwacht die Anlage und alle von der API gemeldeten **Komponenten außer Smart Plugs**.

Die separate Integration [SAJ Elekeeper Smart Plug](https://github.com/M-Rapske/SAJ-Elekeeper-Smart-Plug) bleibt für Steckdosen zuständig. Beide Komponenten können parallel verwendet werden.

## Unterstützte Daten

- PV-, Last-, Netz-, Batterie- und Eigenverbrauchsleistung – jeweils als getrennte Home-Assistant-Geräte für eine klare Zuordnung
- Tages- und Gesamtenergien für PV, Verbrauch, Netzbezug/-einspeisung sowie Batterie
- Batterieladezustand, Gesundheitszustand, Spannung, Strom, Temperatur und Betriebsrichtung
- Betriebsmodus und Leistungsflussrichtungen
- Alle nicht als Smart Plug erkannten Geräte aus der API, etwa Wechselrichter, eManager, Batterie und Wallbox; die Wallbox wird als eigenes Gerät angelegt
- Bekannte Gerätewerte als typisierte Sensoren; zusätzliche, nicht eindeutig benennbare API-Felder werden als deaktivierte Experten-Sensoren angelegt und können bei Bedarf einzeln aktiviert werden

Smart-Plug-Geräte und deren Werte werden ausdrücklich gefiltert und nicht als Entitäten angelegt.

## Installation

### HACS

1. HACS → **Integrationen** → Menü → **Benutzerdefinierte Repositorys**.
2. Dieses Repository als Kategorie **Integration** hinzufügen.
3. **SAJ Elekeeper** installieren und Home Assistant neu starten.

### Manuell

Den Ordner [`custom_components/saj_elekeeper`](custom_components/saj_elekeeper) nach `/config/custom_components/saj_elekeeper` kopieren und Home Assistant neu starten.

## Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen.
2. **SAJ Elekeeper** auswählen.
3. Region, **Benutzername oder E-Mail-Adresse** und Passwort eingeben.
4. Bei mehreren Anlagen die gewünschte Anlage auswählen.

Das Aktualisierungsintervall lässt sich anschließend unter **Konfigurieren** in ganzen Minuten von 1 bis 1.440 einstellen. Der Standard beträgt fünf Minuten, damit die private Cloud-API nicht unnötig häufig abgefragt wird.

## Hinweise

- Die Elekeeper-API ist privat und kann sich jederzeit ändern.
- Die Integration meldet sich bei dem API-Fehler `10002: Please login first` automatisch erneut an und wiederholt den Abruf einmal.
- Wallboxen werden zusätzlich über Elekeepers V2-Smart-Geräteliste erkannt; Smart Plugs werden daraus weiterhin verworfen.
- Historische Diagramm-Endpunkte werden nicht im Minutentakt abgefragt; die Langzeitdaten werden stattdessen von Home Assistant aus den Live-Sensoren aufgezeichnet.
- Nicht jedes SAJ-Gerät liefert jeden Wert. Leere Entitäten sind daher bei nicht unterstützten Komponenten normal.

## Unterstützung

Bei Problemen bitte die Home-Assistant-Logs mit `saj_elekeeper` sowie eine Diagnose-Datei der Integration bereitstellen. Die Diagnose enthält eine gekürzte Geräteerkennung (Modell, Typ, Seriennummer-Endung und Feldnamen), aber keine Zugangsdaten, Tokens oder Messwerte.

## Lizenz

MIT – siehe [LICENSE.md](LICENSE.md).
