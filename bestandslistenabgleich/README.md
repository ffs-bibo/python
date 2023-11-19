# Bestandslistenabgleich

Der Katalog der SBA (Schulbibliothekarische Arbeitsstelle der Stadtbücherei Frankfurt am Main) kann abgefragt aber nicht eingesehen werden. Grob gesagt handelt es sich damit nicht um einen klassischen Katalog, sondern um eine Katalogsuche.

Der Link zur spezifischen Suche durch den Bestand der FFS-Bibo ist [dieser](https://sbakatalog.stadtbuecherei.frankfurt.de/A-F/Friedrich-Fr%C3%B6bel-Schule).

Freundlicherweise wurde seitens der SBA eine Bestandsliste als Excel-Sheet zur Verfügung gestellt (Stand 2023-10-30) und wir haben eine eigene Liste die von einem langjährigen ehrenamtlichen Freiwilligen händisch in Excel gepflegt wurde.

* Die Liste der SBA hat einen Nachteil: die Inventarnummer welche im Karteisystem genutzt wird, ist dort nicht aufgeführt.
* Bei unserer eigenen Liste stellt sich die Frage wie korrekt diese ist und welcher Natur die Diskrepanzen zur Bestandsliste der SBA sind.

Solange ich keine Freigabe dafür habe, werde ich die eigentlichen Bestandsdaten nicht hier hinterlegen, sondern eine repräsentative Untermenge -- ggf. anonymisiert -- um zu vermitteln was das Skript erwartet usw. Die Skripte selber und jegliche andere anfallende Software sollen unter einer FLOSS-Lizenz bereitgestellt werden, wobei die Wahl der Lizenz für die einzelnen Komponenten bisher noch nicht feststeht.

## Weiteres

* Offenbar wird unsere Schulbücherei als Nummer 51 im System der SBA behandelt.
* Während prinzipiell für Schulbüchereien der Weg offensteht Littera von der Stadt bezahlt zu bekommen, gibt es in keinem Fall eine Anbindung an den Datenbestand der SBA (weder als API noch anderweitig). Daher liegt es nahe eine eigene Lösung zu erstellen die ggf. auch anderen Schulbüchereien eine (Teil-)Digitalisierung ihrer Prozesse erleichtert.
* Die Warteliste der Schulbüchereien die digitalisiert werden wollen ist ellenlang und Grundschulen scheinen in jedem Fall im Hintertreffen zu sein. Kurzum: mir wurde signalisiert daß eine Digitalisierung in absehbarer Zeit nicht zu erwarten ist.

## Zielstellung

_Dieses_ Projekt soll helfen die beiden Listen abzugleichen und eventuell über (teil-)automatisierte Abfragen des der SBA-Katalogsuche anzureichern.

Ziel ist es eine Bestandsliste zu erhalten, die als Basis für ein eigenes digitales Ausleihesystem dienen kann.

Dabei soll die Inventarnummer als eine der Grundlagen dienen. Grob gesagt geht es darum die Inventarnummer, welche seitens der SBA vor dem Versand an uns vergeben wird, mit den anderen Metadaten zum Buch zu verknüpfen.

Das wäre dann:

* Inventarnummer (diese beinhaltet meiner Beobachtung nach bereits das Jahr in zweistelliger Form)
* Autor
* Titel
* Serie
* Kategorie
* Verlag (?)
* ISBN (?)

Sofern freigegeben, könnten wir dann die Klassenlisten dazu einpflegen. Hier wären wichtig:

* Klassenlehrer(in)
* Klasse: 1..4 a..f
* Die jeweiligen Schüler mit allen Vor- und Nachnamen
* Datum des Klassendatensatzes (Schüler rücken natürlich mit dem neuen Schuljahr eine Klasse auf usw.)
* Ggf. böte sich noch eine weitere Liste mit dem Personal der Schule an, für Ausleihen durch Lehrer usw.

### Erfahrungswerte und sich daraus ergebende Ausblicke ...

* Wir haben da eine Regel: pro Kind nur ein Buch zu jedem Zeitpunkt -- die Regel kann aber nicht durchgesetzt werden, weil jedesmal ein Blättern durch die Karteikarten notwendig wäre, was auch durch teilweise falsche Einsortierung noch weiter erschwert wird.
* Digitalisierung würde folgende Probleme lösen:
  * Lange Suchen durch die Kartei könnte man sich ersparen
  * Gleichzeitige Zugriffe auf die Kartei wären quasi ein Ding der Vergangenheit, da die Suche viel schneller ginge ohne bspw. einen bestimmten Buchstabenblock der Kartei zu entnehmen.
  * Spezifisch bei Ausleihe:
    * Fehlende Karteikarten wären kein Problem -- denn: sobald der Datenbestand digital vorliegt, können die Karteikarten aus den Büchern entfernt werden.
    * Versuchte Mehrfachausleihen würden sofort erkannt und könnten direkt unterbunden werden.
  * Spezifisch bei Rückgabe:
    * Die Suche nach Klasse, Name oder Buchtitel o.ä. würde die Rückgabe deutlich beschleunigen.
    * Fehlende Karteikarten gäbe es auch hier nicht mehr -- denn die Karteikarten wären unnötig und somit wäre die Rückgabe damit erledigt, daß das Buch als zurückgegeben markiert wird und ggf. auf dem eingeklebten Zettel hinten die entsprechende Zeile durchgestrichen wird.
* Notizen zu Ausleihen, Reservierungen und diverse andere Extras ließen sich vergleichsweise einfach einbauen und würden Kontinuität zwischen den Freiwilligen bieten _ohne_ auf externe Kommunikationsmittel angewiesen zu sein (wobei uns diese wohl erhalten blieben).

### Wie's jetzt läuft (grob vereinfacht)

#### Ausleihe

Kind kommt mit Buch und will ausleihen

* Option 1: Karteikarte fehlt im Buch -> kann nicht verliehen werden, Kind wird vertröstet und Buch einbehalten
* Option 2: Karteikarte ist vorhanden:
    1. _Eigentlich_ müßte an dieser Stelle ein Suche durch den Karteikasten stattfinden um auszuschließen daß das Kind bereits andere Bücher entliehen hat (Regel, s.o.) -> leider zeitraubend und unpraktikabel und wird daher nicht gemacht
    1. Kind wird nach Klasse und Nachnamen gefragt
    1. Klassenliste (Hefter mit 1 A4-Seite pro Klasse) wird durchsucht um den Namen dort zu finden
    1. Abgabezeitpunkt wird im Buch auf den eingeklebten Zettel gestempelt und die Initialen (Nachname, dann Vornamen) eingetragen
    1. Abgabezeitpunkt wird auf der Karteikarte gestempelt und der voll Name, sowie die Klasse vermerkt
        * Karteikarte wandert in den Karteikasten (manchmal auch falsch einsortiert; hier ist eigentlich gefordert Sortierung nach Nachnamen)
    1. Kind bekommt Buch ausgehändigt

#### Rückgabe

Kind kommt mit Buch und möchte es zurückgeben

* Kind wird nach dem Nachnamen gefragt, es sei denn die Initialen auf dem eingeklebten Zettel sind ersichtlich
* Option 1: Karteikarte ist im Karteikasten auffindbar
    1. Karteikarte wird "abgehakt" und ins Buch gelegt
    1. Die aktuellste Zeile mit dem Rückgabedatum auf dem eingeklebten Zettel wird optional (?) durchgestrichen
    1. Buch landet auf dem Stapel zum Einsortieren
* Option 2: Karteikarte ist im Karteikasten _nicht_ auffindbar
    1. Die aktuellste Zeile mit dem Rückgabedatum auf dem eingeklebten Zettel wird optional (?) durchgestrichen
    1. Buch landet auf dem Stapel zum mit unklaren Fällen, da Karteikarte nicht auffindbar
    1. Im Anschluß ergibt sich die Frage ob eine Karteikarte nachgefertigt werden soll oder sie sich doch noch anfindet (meist kombiniert mit einer langwierigen Suche mit Gegenprobe durch den Karteikasten, wobei nicht selten mehrere Freiwillige beteiligt sind ...  ein zeit- und nervenraubender Prozeß)

#### Ankunft

Bei Antritt des "Dienstes" in der Bücherei heißt es erst einmal den Datumsstempel "vorstellen" und die Klassenlisten heraussuchen und bereitlegen.

Ersteres würde auch bei einer Digitalisierung nicht entfallen, würde sich aber insofern vereinfachen, weil man der Software das Wissen um Ferien und Leihfristen mitgeben könnte, bzw. diese konfigurierbar gestalten kann. Klassenlisten wären der Software direkt verfügbar und damit auch durchsuchbar, die Hefter entfielen.

Je nachdem wie früh man ankam, werden dann die Rückgaben aus dem Wäschekorb bearbeitet. Dabei steht meistens der Name als Haftnotiz auf dem Buch, die Karteisuche und der Rest erfolgt dann wie unter "Rückgabe" oben beschrieben.

Weiterhin haben wir Mahnungen so gestaltet, daß jeder Tag der Woche einen bestimmten Bereich des Alphabets im Karteikasten abklappert um überfällige Ausleihen aufzuspüren. Das wird offensichtlich nicht konsequent gemacht -- kein Wunder, es ist zeitraubend, insbesondere wenn man fündig wird.

Die Mahnungen ließen sich deutlich vereinfachen und ggf. flexibilisieren. Insbesondere sollte es möglich sein durch den gestellten Laptop direkt wahlweise bei "Tagesabschluß" eine Email an die Schulsekretärin zu verschicken in welcher die Mahnungen gebündelt (bspw. als PDF) zum Ausdruck vorbereitet wären. Alternativ ist vielleicht sogar der Direktdruck auf dem Drucker möglich (erfordert in beiden Fällen weitere Abklärung).
