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

## Output
Il programma produce due file:
* *turni_&lt;anno&gt;.csv*: contiene la turnistica calcolata; per ogni data è indicato il vigile assegnato al relativo notturno, e per sabati ed i festivi i vigili assegnati ai medesimi.
* *riporti_&lt;anno&gt;.csv*: file dei riporti (aggiornato) da utilizzare per il calcolo l'anno successivo.