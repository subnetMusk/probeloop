# Recording script for the STT spike

Record each passage as a separate file in `spikes/audio/`, for example with the Windows Sound
Recorder app. Read at a natural pace, as if answering an interviewer. Hesitations and small
self-corrections are fine and realistic. For files `read_01` to `read_05`, also create a `.txt`
file with the same name containing the passage text below, so that WER can be computed.

Then record two free answers of about one minute each (`free_01`, `free_02`), with no `.txt`:
for example "Mi parli di un progetto di cui è orgoglioso" and "Come gestisce una scadenza
difficile".

## read_01

Negli ultimi tre anni ho lavorato come sviluppatore backend in un'agenzia di e-commerce. Il nostro
stack era basato su Python e FastAPI, con PostgreSQL come database principale e Redis per la cache.
Mi occupavo soprattutto delle API per la gestione degli ordini e dei pagamenti.

## read_02

Il microservizio di ottimizzazione dei percorsi riceveva ogni mattina gli ordini del giorno e
calcolava i giri dei furgoni. Per il problema di routing usavamo OR-Tools, mentre le matrici delle
distanze venivano salvate in Redis con una scadenza di un'ora.

## read_03

Quando una query è lenta parto sempre da EXPLAIN ANALYZE, per vedere se il piano usa una scansione
sequenziale e quanto tempo richiede ogni nodo. Poi valuto un indice mirato sulle colonne usate nei
filtri, tenendo presente che ogni indice rallenta le scritture.

## read_04

Organizzo i test su due livelli. I test unitari girano con pytest e usano dei fake per le
dipendenze esterne. I test di integrazione invece avviano un vero PostgreSQL in un container
durante la pipeline di integrazione continua.

## read_05

Una volta il team voleva introdurre Kafka per gestire gli eventi tra i servizi. Io ero contrario,
perché il volume di messaggi non lo giustificava. Ho preparato una stima dei costi e un piccolo
prototipo con una coda più semplice, e alla fine il team ha scelto quella soluzione.
