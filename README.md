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
* *vigili.csv*: contiene l'elenco dei vigili, i loro gradi, squadre e festivi di appartenenza ed eventuali richieste eccezionali circa la relativa turnistica;
* *riporti.csv*: opzionale, contiene numeri di servizi extra o onerosi svolti negli ultimi anni.

## Uso
```
python main.py
```
### Opzioni
```
  -h, --help            Mostra le opzioni d'uso (in inglese)
  -c, --servizi-compleanno
                        Abilita l'assegnazione di servizi il giorno di
                        compleanno
  -di DATA_INIZIO, --data-inizio DATA_INIZIO
                        Data di inizio, che dev'essere un venerdì
                        Default: 2021-1-15
  -df DATA_FINE, --data-fine DATA_FINE
                        Data di inizio, che dev'essere un venerdì
                        Default: 2022-1-14
  -l, --loose           Abilita l'assegnazione di notturni al di fuori della
                        settimana di reperibilità
  -R RIPORTI_FN, --riporti-fn RIPORTI_FN
                        Percorso del file CSV contenente i riporti dei turni
                        extra od onerosi svolti negli anni precedenti
                        Default: riporti.csv
  -s SQUADRA_DI_PARTENZA, --squadra-di-partenza SQUADRA_DI_PARTENZA
                        Squadra reperibile per la prima settimana
                        Default: 1
  -t TIME_LIMIT, --time-limit TIME_LIMIT
                        Tempo limite in ms
                        Default: 300000
  -v, --verbose         Abilita l'output verboso del solver
  -V VIGILI_FN, --vigili-fn VIGILI_FN
                        Percorso del file CSV contenente i dati dei vigili
                        Default: vigili.csv
```
## Output
Il programma produce due file:
* *turni_&lt;anno&gt;.csv*: contiene la turnistica calcolata; per ogni data è indicato il vigile assegnato al relativo notturno, e per sabati ed i festivi i vigili assegnati ai medesimi.
* *riporti_&lt;anno&gt;.csv*: file dei riporti (aggiornato) da utilizzare per il calcolo l'anno successivo.