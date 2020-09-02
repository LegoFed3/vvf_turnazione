# Turnazione VVF
Questo programma calcola la turnazione per i vigili del fuoco volontari, tenendo conto dei numerosi vincoli che ciò comporta, e del numero e tipo di servizi particolari svolti nel recente passato.
È basato su una formulazione di [programmazione lineare intera](https://it.wikipedia.org/wiki/Programmazione_lineare) (Integer Linear Programming, ILP).

## Prerequisiti
Questo programma è scritto in [Python](https://www.python.org/) (testato con la versione 3.6) e si basa, per la soluzione di una formulazione ILP, su [Google OR Tools](https://developers.google.com/optimization) ed il solver GLOP da esso fornito.
Su e.g. Ubuntu Linux (e vari derivati) si possono installare con:
```
sudo apt install python3
python -m pip install --upgrade --user ortools
```
Mentre su Windows si vedano i link di cui sopra.

## Input
Il programma consuma in input due file (esempi dei quali sono forniti in questo repository):
* *organico.csv*: contiene l'elenco dei vigili, i loro gradi, cariche, squadre e festivi di appartenenza ed eventuali richieste eccezionali circa la relativa turnistica;
* *riporti.csv*: opzionale, contiene numeri di servizi extra o onerosi svolti negli ultimi anni.

## Uso
```
python main.py
```
### Argomenti posizionali
```
  data_di_inizio        Data di inizio, che dev'essere un venerdì
                        Default: 2021-1-15
  data_di_fine          Data di fine, che dev'essere un venerdì
                        Default: 2022-1-14
  squadra_di_partenza   Squadra reperibile per la prima settimana
                        Default: 1
```
### Opzioni
```
  -h, --help            Mostra le opzioni d'uso (in inglese)
  -c, --servizi-compleanno
                        Abilita l'assegnazione di servizi il giorno di
                        compleanno
  -j JOBS, --jobs JOBS  numero di thread paralleli per la risoluzione del modello
                        Default: 3
  -l, --loose           Abilita l'assegnazione di notturni al di fuori della
                        settimana di reperibilità
  -o ORGANICO_FN, --organico-fn ORGANICO_FN
                        Percorso del file CSV contenente i dati dei vigili
                        Default: organico.csv
  -r RIPORTI_FN, --riporti-fn RIPORTI_FN
                        Percorso del file CSV contenente i riporti dei turni
                        extra od onerosi svolti negli anni precedenti
                        Default: riporti.csv
  -t TIME_LIMIT, --time-limit TIME_LIMIT
                        Tempo limite in ms
                        Default: 300000
  -v, --verbose         Abilita l'output verboso del solver
```
## Output
Il programma produce due file:
* *turni_&lt;anno&gt;.csv*: contiene la turnistica calcolata; per ogni data è indicato il vigile assegnato al relativo notturno, e per sabati ed i festivi i vigili assegnati ai medesimi.
* *riporti_&lt;anno&gt;.csv*: file dei riporti (aggiornato) da utilizzare per il calcolo l'anno successivo.