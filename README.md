# Turnazione VVF
Questo programma calcola la turnazione attuale per i vigili del fuoco volontari, tenendo conto dei numerosi vincoli che ciò comporta, tenendo anche conto del numero e tipo di servizi particolari svolti nel recente passato.

## Prerequisiti
Questo programma richiede python (testato con la versione 3.6) e si basa, per la soluzione din un ILP, su [Google OR Tools](https://developers.google.com/optimization) ed il solver GLOP da esso fornito.
Su e.g. Ubuntu Linux (e vari derivati) si possono installare con:
```
sudo apt install python3
python -m pip install --upgrade --user ortools
```

## Input
Il programma consuma in input due file:
* *vigili.csv*: contiene l'elenco dei vigili, i loro gradi, squadre e festivi di appartenenza ed eventuali richieste eccezionali circa la relativa turnistica;
* *riporti.csv*: opzionale, contiene numeri di servizi extra o onerosi svolti negli ultimi anni.

## Uso
```
python main.py
```

## Output
Il programma produce due file:
* *turni_&gt;anno&lt;.csv*: contiene la turnistica calcolata; per ogni data è indicato il vigile assegnato al relativo notturno, e per sabati ed i festivi i vigili assegnati agli stessi.
* *riporti_&gt;anno&lt;.csv*: file aggiornato dei riporti da utilizzare per il calcolo per'anno successivo.