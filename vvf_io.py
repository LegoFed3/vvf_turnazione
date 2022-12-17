import datetime as dt
import pandas as pd
import os

_GRADI_VALIDI = [
    "Comandante",
    "Vicecomandante",
    "Capoplotone",
    "Caposquadra",
    "Vigile",
    "Aspirante",
    "Complemento",
    "Ispettore",
    "Presidente",
]

_ECCEZZIONI_VALIDE = [
    # Cariche
    "Segretario",
    "Cassiere",
    "Magazziniere",
    "Vicemagazziniere",
    "Resp. Allievi",
    # Esenzioni
    "Aspettativa",
    "EsenteNotti",
    "EsenteSabati",
    "EsenteFestivi",
    "EsenteServizi",
    "NottiSoloSabatoFestivi",
    "NoNottiGiornoLun",
    "NoNottiGiornoMar",
    "NoNottiGiornoMer",
    "NoNottiGiornoGio",
    "NoNottiGiornoVen",
    "NoNottiGiornoSab",
    "NoNottiGiornoDom",
    "NottiAncheFuoriSettimana",
    "FestiviComunque",
]
for i in range(1, 12 + 1):
    _ECCEZZIONI_VALIDE.append(f"NoNottiMese{i}")
    _ECCEZZIONI_VALIDE.append(f"NoFestiviMese{i}")
    _ECCEZZIONI_VALIDE.append(f"NoServiziMese{i}")
    # _ECCEZZIONI_VALIDE.append(f"LimiteNotti{i}")
    # _ECCEZZIONI_VALIDE.append(f"ExtraNotti{i}")
    # _ECCEZZIONI_VALIDE.append(f"ExtraSabati{i}")


class Vigile:
    id = 0
    nome = ""
    cognome = ""
    data_di_nascita = dt.date(1900, 1, 1)
    grado = "Vigile"
    squadre = []
    eccezioni = set()
    notti = 0
    notti_fuori_squadra = 0
    sabati = 0
    sabati_fuori_squadra = 0
    festivi = 0
    festivi_fuori_squadra = 0
    capodanno = 0
    festivi_onerosi = 0
    passato_festivi_onerosi = [0] * 10
    passato_sabati = [0] * 10
    passato_servizi_extra = 0
    passato_capodanni = 0
    delta_notti = 0
    delta_sabati = 0
    delta_festivi = 0
    notti_non_standard = False

    def __init__(self, id_vigile, nome, cognome, ddn, grado, autista, squadre, dn, ds, df, eccezzioni):
        self.id = id_vigile
        self.nome = nome
        self.cognome = cognome
        self.data_di_nascita = dt.datetime.strptime(ddn, '%d/%m/%Y').date()
        self.grado = grado
        self.autista = autista == 'y'
        if len(squadre) > 0:
            self.squadre = list(map(int, squadre.split(",")))
        else:
            self.squadre = [0]
        if len(dn) > 0:
            self.delta_notti = int(dn)
        if len(ds) > 0:
            self.delta_sabati = int(ds)
        if len(df) > 0:
            self.delta_festivi = int(df)
        self.eccezioni = set(eccezzioni.strip(" ").split(","))
        if '' in self.eccezioni:
            self.eccezioni.remove('')

        # Verifiche
        if self.grado not in _GRADI_VALIDI:
            print("ERRORE! Grado sconosciuto: ", self.grado)
            exit(-1)
        if self.grado in ["Comandante", "Vicecomandante", "Ispettore", "Presidente"]:
            self.squadre = [0]
        for e in self.eccezioni:
            if e not in _ECCEZZIONI_VALIDE:
                print("ERRORE: eccezione sconosciuta {} per il vigile {}".format(e, self.id))
                exit(-1)
        if "Aspettativa" in self.eccezioni and self.squadre != [0]:
            print(f"ATTENZIONE: il vigile {self.id} è in aspettativa ma è assegnato alla squadra {self.squadre}! "
                  f"Ignoro la squadra.")
            self.squadre = [0]
        if self.delta_notti != 0:
            self.notti_non_standard = True

    def __str__(self):  # Called by print()
        s = "{:03d} {}".format(self.id, self.grado)
        return s + f" {self.nome} {self.cognome}"

    def __repr__(self):
        return self.__str__()

    def esente_servizi(self):
        return (self.grado in ["Ispettore", "Presidente", "Complemento"] or "Aspettativa" in self.eccezioni
                or "EsenteServizi" in self.eccezioni)

    def esente_notti(self):
        return (self.esente_servizi() or self.grado in ["Aspirante", "Complemento"] or "Aspettativa" in self.eccezioni
                or "EsenteNotti" in self.eccezioni)

    def esente_sabati(self):
        return (self.esente_servizi() or self.grado in ["Aspirante", "Complemento"] or "Aspettativa" in self.eccezioni
                or "EsenteSabati" in self.eccezioni)

    def esente_festivi(self):
        return self.esente_servizi() or "Aspettativa" in self.eccezioni or "EsenteFestivi" in self.eccezioni

    def graduato(self):
        return self.grado in ["Comandante", "Vicecomandante", "Capoplotone", "Caposquadra"]

    def altre_cariche(self):
        return ("Segretario" in self.eccezioni
                or "Cassiere" in self.eccezioni
                or "Magazziniere" in self.eccezioni
                or "Vicemagazziniere" in self.eccezioni
                or "Resp. Allievi" in self.eccezioni)

    def membro_direttivo(self):
        return (self.grado in ["Comandante", "Vicecomandante", "Caposquadra"]
                or "Segretario" in self.eccezioni
                or "Cassiere" in self.eccezioni
                or "Magazziniere" in self.eccezioni
                or "Vicemagazziniere" in self.eccezioni)

    def haSquadra(self):
        return 0 not in self.squadre

    def offset_compleanno(self, data_inizio):
        if (
                self.data_di_nascita.month <= data_inizio.month
                and self.data_di_nascita.day < data_inizio.day
        ):
            compleanno = dt.date(data_inizio.year + 1, self.data_di_nascita.month, self.data_di_nascita.day)
        else:
            compleanno = dt.date(data_inizio.year, self.data_di_nascita.month, self.data_di_nascita.day)
        offset = (compleanno - data_inizio).days
        return offset

    def numero_servizi(self):
        return self.notti + self.sabati + self.festivi


def read_csv_vigili(filename):
    db = {}
    if not os.path.isfile(filename):
        print(f"ERRORE: il file '{filename}' che descrive i vigili non esiste!")
        print("\tImpossibile continuare senza.")
        exit(-1)
    df = pd.read_csv(filename, sep=";", dtype=str, keep_default_na=False)
    for idx, row in df.iterrows():
        if len(row) == 0:
            continue
        id_vigile = int(row['ID'])
        db[id_vigile] = Vigile(
            id_vigile,
            row['Nome'],
            row['Cognome'],
            row['Data di Nascita'],
            row['Grado'],
            row['Autista'],
            row['Squadra'],
            row['DeltaNotti'],
            row['DeltaSabati'],
            row['DeltaFestivi'],
            row['Eccezioni'],
        )
    return db


def read_csv_riporti(db, filename):
    if not os.path.isfile(filename):
        print(f"ATTENZIONE: il file '{filename}' che descrive i riporti dello scorso anno non esiste!")
        print("\tContinuo senza.")
        return db
    df = pd.read_csv(filename, sep=";")
    for idx, row in df.iterrows():
        id_vigile = row[0]
        if id_vigile in db.keys():
            db[id_vigile].passato_servizi_extra = int(row[1])
            db[id_vigile].passato_capodanni = int(row[2])
            db[id_vigile].passato_sabati = list(map(lambda x: int(x), row[3:13]))
            db[id_vigile].passato_festivi_onerosi = list(map(lambda x: int(x), row[13:23]))
    return db
