# Turnazione VVF
Questo programma calcola la turnazione per i vigili del fuoco volontari, tenendo conto dei numerosi vincoli che ciò comporta, e del numero e tipo di servizi particolari svolti nel recente passato.
È basato su una formulazione di [programmazione lineare intera](https://it.wikipedia.org/wiki/Programmazione_lineare) (Integer Linear Programming, ILP).

## Prerequisiti
Questo programma è scritto in [Python](https://www.python.org/) (testato con la versione 3.6) e si basa, per la soluzione di una formulazione ILP, su [Google OR Tools](https://developers.google.com/optimization) ed il solver GLOP da esso fornito.
Su e.g. Ubuntu Linux (e distribuzioni analoghe) si possono installare con:
```
sudo apt install python3
python -m pip install --upgrade --user ortools
```
Mentre su Windows si vedano i link di cui sopra.

## Uso
```
python main.py data_di_inizio data_di_fine squadra_di_partenza 
```
Ad esempio: `python main.py 2021-1-15 2022-1-14 3` calcola i turni da venerdì 15 gennaio 2021 a venerdì 14 gennaio 2022 con la squadra 3 reperibile per la prima settimana, consumando i file di organico e riporti di default.

### Argomenti
```
  data_di_inizio        Data di inizio, che dev'essere un venerdì
  data_di_fine          Data di fine, che dev'essere un venerdì
  squadra_di_partenza   Squadra reperibile per la prima settimana
```

### Opzioni
```
  -h, --help            Mostra le opzioni d'uso (in inglese)
  -c, --servizi-compleanno
                        Abilita l'assegnazione di servizi il giorno di compleanno
  -j JOBS, --jobs JOBS  Numero di thread paralleli per la risoluzione del modello
                        Default: 1
  -l, --loose           Abilita l'assegnazione di notturni al di fuori della settimana di reperibilità
  -m MEDIA_NOTTI MEDIA_FESTIVI, --media-notti-festivi MEDIA_NOTTI MEDIA_FESTIVI
                        Numero medio di notti e festivi per vigile, abilita servizi extra per l'eccezione "PocheManovre"
  -n, --neo-vigili      Abilita l'assegnazione di notti extra (10, o una al mese se <10 mesi) per i primi due anni ai neo-vigili
  -o ORGANICO_FN, --organico-fn ORGANICO_FN
                        Percorso del file CSV contenente i dati dei vigili
                        Default: organico.csv
  -r RIPORTI_FN, --riporti-fn RIPORTI_FN
                        Percorso del file CSV contenente i riporti dei turni extra od onerosi svolti negli anni precedenti
                        Default: riporti.csv
  -t TIME_LIMIT, --time-limit TIME_LIMIT
                        Tempo limite in secondi
                        Default: nessun limite
  -v, --verbose         Abilita l'output verboso del solver
```
Ad esempio: `python main.py 2021-1-15 2022-1-14 3 -o organico_2020.csv -r riporti_2020.csv -j 4 -t 300 -l -n` calcola, come sopra, i turni da venerdì 15 gennaio 2021 a venerdì 14 gennaio 2022 con la squadra 3 reperibile per la prima settimana, consumando però i file organico_2020.csv e riporti_2020.csv, limitando il solver ad utilizzare circa 5 minuti di CPU, distribuendo il calcolo della soluzione su 4 thread, permettendo l'assegnazione di notti fuori dalla settimana di reperibilità (se necessario a ridurre le differenze tra i numeri di servizi assegnati), ed assegnando notti extra per i primi due anni ai neo-vigili (dopo l'aspirantato).

## Input
Il programma consuma in input due file (esempi dei quali sono forniti in questo repository):
* *organico.csv*: contiene l'elenco dei vigili, i loro gradi, cariche, squadre e festivi di appartenenza ed eventuali richieste eccezionali circa la relativa turnistica. Il file è strutturato come segue:
	* *ID*: identificativo numerico del vigile. Dev'essere unico e stabile nel tempo.
	* *Nome*, *Cognome* e *Data di Nascita*: generalità del vigile. La data dev'essere nel formato GG/MM/AAAA.
	* *Grado*: grado del vigile (determina alcune restrizioni sul tipo e numero di servizi). I gradi validi sono: Comandante, Vicecomandante, Capoplotone, Caposquadra, Vigile, Aspirante, Complemento, Ispettore, Presidente.
	* *Squadra*: squadra reperibile cui il vigile afferisce. Il numero 0 è riservato ai vigili non afferenti ad alcuna squadra (e.g. il Comandante).
	* *Gruppo Festivo*: identificativo della squadra festivo cui il vigile afferisce.
	* *Data Passaggio a Vigile*: per gli aspiranti, determine quanti servizi assegnare perl'anno del passaggio e quando assegnarli. Dev'essere nel formato GG/MM/AAAA.
	* *Eccezioni*: lista separata da virgola e senza spazi (e case sensitive) di eccezioni, dovute a cariche o altre richieste, alla normale turnazione. Le eccezioni valide sono:
		* Cariche: Segretario, Cassiere, Magazziniere, Vicemagazziniere, Resp. Allievi.
		* Altre richieste: 
			* Aspettativa: nessun servizio durante l'anno.
			* EsenteCP: notti extra per compensare la non-reperibilità.
			* EsenteNotti: nessun servizio notturno.
			* PocheManovre: servizi extra per poche manovre frequentate l'anno precedente.
			* NottiSoloSabatoFestivi, NoNottiGiornoLun, NoNottiGiornoMar, NoNottiGiornoMer, NoNottiGiornoGio, NoNottiGiornoVen, NoNottiGiornoSab, NoNottiGiornoDom, NoNottiMese1, NoNottiMese2, NoNottiMese3, NoNottiMese4, NoNottiMese5, NoNottiMese6, NoNottiMese7, NoNottiMese8, NoNottiMese9, NoNottiMese10, NoNottiMese11, NoNottiMese12: limiti ai giorni per i quali è possibile assegnare notti al vigile.
			* NoServiziMese1, NoServiziMese2, NoServiziMese3, NoServiziMese4, NoServiziMese5, NoServiziMese6, NoServiziMese7, NoServiziMese8, NoServiziMese9, NoServiziMese10, NoServiziMese11, NoServiziMese12, FestiviComunque: limiti ai giorni per i quali è possibile assegnare servizi di qualunque genere al vigile, ed eccezione per i festivi.
			* NottiAncheFuoriSettimana: consente di assegnare notti anche fuori dalla settimana di reperibilità al vigile (versione individuale di -l).
			* LimiteNotti1, LimiteNotti2, LimiteNotti3, LimiteNotti4, LimiteNotti5, LimiteNotti6, LimiteNotti7, LimiteNotti8, LimiteNotti9, LimiteNotti10: limite specifico al numero di notti assegnabili; sovrascrive il limite per carica.
* *riporti.csv*: opzionale, contiene numeri di servizi extra o onerosi assegnati negli ultimi anni. Il file è strutturato come segue:
	* *ID*: identificativo numerico del vigile nel file organico.csv.
	* *Servizi Extra Media*: numero (potenzialmente negativo) indicante qualora al vigile (che non ricopre cariche particolari) siano stati assegnati più o meno servizi della media nell'anno precedente.
	* *Capodanni*: numero di capodanni assegnati negli anni precedenti.
	* *Sabati*: 5 colonne indicanti il numero di sabati assegnati nei 5 anni precedenti.
	* *Servizi Onerosi*: 5 colonne indicanti il numero di servizi onerosi assegnati nei 5 anni precedenti.

## Output
Il programma produce due file:
* *turni_&lt;anno&gt;.csv*: contiene la turnistica calcolata; per ogni data è indicato il vigile assegnato al relativo notturno, e per sabati ed i festivi i vigili assegnati ai medesimi.
* *riporti_&lt;anno&gt;.csv*: file dei riporti (aggiornato) da utilizzare per il calcolo l'anno successivo.