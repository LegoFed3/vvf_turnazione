import datetime as dt
import pandas as pd
import icalendar as ical
import pytz
import os

_GRADI_VALIDI = [
    "Comandante",
    "Vicecomandante",
    "Capoplotone",
    "Caposquadra",
    "Vigile",
    "Aspirante",
    "Allievo",
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
for i in range(1, 13 + 1):
    _ECCEZZIONI_VALIDE.append(f"NoNottiMese{i}")
    _ECCEZZIONI_VALIDE.append(f"NoSabatiMese{i}")
    _ECCEZZIONI_VALIDE.append(f"NoFestiviMese{i}")
    _ECCEZZIONI_VALIDE.append(f"NoServiziMese{i}")


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

    def __init__(self, id_vigile, nome, cognome, ddn, grado, email, autista, istruttore, squadre, dn, ds, df, exc):
        self.id = id_vigile
        self.nome = nome
        self.cognome = cognome
        self.data_di_nascita = dt.datetime.strptime(ddn, '%d/%m/%Y').date()
        self.grado = grado
        self.email = email if email != "" else None
        self.autista = autista == 'y'
        self.istruttore_allievi = istruttore == 'y'
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
        self.eccezioni = set(exc.strip(" ").split(","))
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

    def __str__(self):  # Called by print()
        s = "{:03d} {}".format(self.id, self.grado)
        return s + f" {self.nome} {self.cognome}"

    def __repr__(self):
        return self.__str__()

    def get_full_name(self):
        return f'{self.nome} {self.cognome}'

    def esente_servizi(self):
        return (self.grado in ["Ispettore", "Presidente", "Complemento", "Allievo"] or "Aspettativa" in self.eccezioni
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
    print(f"\tLeggo file organico {filename}...")
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
            row['Email'],
            row['Autista'],
            row['Istruttore Allievi'],
            row['Squadra'],
            row['DeltaNotti'],
            row['DeltaSabati'],
            row['DeltaFestivi'],
            row['Eccezioni'],
        )
    return db


def read_csv_riporti(db, filename):
    print(f"\tLeggo file riporti {filename}...")
    if not os.path.isfile(filename):
        print(f"ATTENZIONE: il file '{filename}' che descrive i riporti dello scorso anno non esiste!")
        print("\tContinuo senza.")
        return db
    df = pd.read_csv(filename, sep=";")
    for idx, row in df.iterrows():
        id_vigile = row.iloc[0]
        if id_vigile in db.keys():
            db[id_vigile].passato_servizi_extra = int(row[1])
            db[id_vigile].passato_capodanni = int(row[2])
            db[id_vigile].passato_sabati = list(map(lambda x: int(x), row[3:13]))
            db[id_vigile].passato_festivi_onerosi = list(map(lambda x: int(x), row[13:23]))
    return db


def save_solution_to_files(model):
    if len(model.solution) == 0:
        print("ERRORE: impossibile salvare soluzione vuota su file.")
        return
    else:
        # Salva i turni calcolati in un CSV
        print("Creo file di output...")

        with open(f"./turni_{model.anno}.csv", "w") as out:
            out.write("Data;Notte;Sabato/Festivo;;;;;Affiancamento\n")
            for giorno in range(len(model.solution)):
                data = model.solution[giorno]['data']
                line = str(data) + ";"

                # Notti
                for vigile in model.solution[giorno]['notte']:
                    line += model.DB[vigile].nome + " " + model.DB[vigile].cognome + ";"

                # Sabati e Festivi
                frag = ""
                for vigile in model.solution[giorno]['sabato']:
                    frag += model.DB[vigile].nome + " " + model.DB[vigile].cognome + ";"
                for vigile in model.solution[giorno]['festivo']:
                    frag += model.DB[vigile].nome + " " + model.DB[vigile].cognome + ";"
                line += frag + ";" * (5 - len(frag.split(";")))

                # Affiancamenti
                for affiancamento in ["notte_affiancamenti", "sabato_affiancamenti", "festivo_affiancamenti"]:
                    for vigile in model.solution[giorno][affiancamento]:
                        line += model.DB[vigile].nome + " " + model.DB[vigile].cognome + ";"

                out.write(line + "\n")

        with open(f"./turni_per_vigile_{model.anno}.txt", "w") as out:
            for vigile in model.DB:
                out.write(model.DB[vigile].nome + " " + model.DB[vigile].cognome + ":\n")
                for srv in model.servizi_per_vigile[vigile]:
                    out.write("- " + srv + "\n")
                out.write("\n")

        # Riporta il numero di servizi extra ed i servizi speciali
        with open(f"./riporti_{model.anno + 1}.csv", "w") as out:
            out.write("#Vigile;Differenza vs. Media;Capodanno;Sabati;;;;;;;;;;Festivi Onerosi\n")
            for vigile in model.DB:
                line = f"{vigile};"
                servizi_extra = 0
                if (
                        not model.DB[vigile].esente_notti()
                        and model.DB[vigile].esente_sabati()
                        and model.DB[vigile].esente_festivi()
                        and model.DB[vigile].delta_notti == 0
                        and model.DB[vigile].delta_sabati == 0
                        and model.DB[vigile].delta_festivi == 0
                ):
                    servizi_extra = round(model.DB[vigile].numero_servizi() - model._SERVIZI_MINIMI)
                line += f"{servizi_extra};"
                line += f"{model.DB[vigile].passato_capodanni + model.DB[vigile].capodanno};"
                line += f"{model.DB[vigile].sabati - model.DB[vigile].delta_sabati};"
                for sabati in model.DB[vigile].passato_sabati[0:9]:
                    line += f"{sabati};"
                line += f"{model.DB[vigile].festivi_onerosi};"
                for festivi in model.DB[vigile].passato_festivi_onerosi[0:9]:
                    line += f"{festivi};"
                out.write(line + "\n")

        # Genera ics per calendario
        tz = pytz.timezone('Europe/Rome')
        organizer = ical.vCalAddress('MAILTO:dati@vigilidelfuocoarco.it')
        organizer.params['cn'] = ical.vText('VVF Arco')

        cal = ical.Calendar()
        cal.add('version', '2.0')
        cal.add('prodid', '-//VVF Arco//VVF Turnazione//EN')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')

        for giorno, val in enumerate(model.solution):

            # Notti
            e = ical.Event()
            e.add('uid', f'vvfarco{model.anno}notte{giorno}')
            e.add('summary', 'Servizio Notturno')
            e.add('name', 'Servizio Notturno')
            e.add('description', 'Servizio Notturno')
            e.add('organizer', organizer)
            e.add('location', 'Caserma VVF Arco')
            e.add('dtstamp', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=20, minute=0, second=0))))
            e.add('dtstart', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=20, minute=0, second=0))))
            e.add('dtend', tz.localize(dt.datetime.combine((val['data'] + dt.timedelta(days=1)),
                                                           dt.time(hour=8, minute=0, second=0))))

            for key in ['notte', 'notte_affiancamenti']:
                for vigile in val[key]:
                    a = ical.vCalAddress(f'MAILTO:{model.DB[vigile].email}')
                    a.params['cn'] = ical.vText(f'{model.DB[vigile].get_full_name()}')
                    a.params['ROLE'] = ical.vText('REQ-PARTICIPANT')

                    e.add('attendee', a, encode=0)

            cal.add_component(e)

            # Sabati
            if len(val['sabato']) > 0:
                e = ical.Event()
                e.add('uid', f'vvfarco{model.anno}sabato{giorno}')
                e.add('summary', 'Servizio Sabato')
                e.add('name', 'Servizio Sabato')
                e.add('description', 'Servizio Sabato')
                e.add('organizer', organizer)
                e.add('location', 'Caserma VVF Arco')
                e.add('dtstamp', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=8, minute=0, second=0))))
                e.add('dtstart', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=8, minute=0, second=0))))
                e.add('dtend', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=20, minute=0, second=0))))

                for key in ['sabato', 'sabato_affiancamenti']:
                    for vigile in val[key]:
                        a = ical.vCalAddress(f'MAILTO:{model.DB[vigile].email}')
                        a.params['cn'] = ical.vText(f'{model.DB[vigile].get_full_name()}')
                        a.params['ROLE'] = ical.vText('REQ-PARTICIPANT')

                        e.add('attendee', a, encode=0)

                cal.add_component(e)

            # Festivi
            if len(val['festivo']) > 0:
                e = ical.Event()
                e.add('uid', f'vvfarco{model.anno}festivo{giorno}')
                e.add('summary', 'Servizio Festivo')
                e.add('name', 'Servizio Festivo')
                e.add('description', 'Servizio Festivo')
                e.add('organizer', organizer)
                e.add('location', 'Caserma VVF Arco')
                e.add('dtstamp', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=8, minute=0, second=0))))
                e.add('dtstart', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=8, minute=0, second=0))))
                e.add('dtend', tz.localize(dt.datetime.combine(val['data'], dt.time(hour=20, minute=0, second=0))))

                for key in ['festivo', 'festivo_affiancamenti']:
                    for vigile in val[key]:
                        a = ical.vCalAddress(f'MAILTO:{model.DB[vigile].email}')
                        a.params['cn'] = ical.vText(f'{model.DB[vigile].get_full_name()}')
                        a.params['ROLE'] = ical.vText('REQ-PARTICIPANT')

                        e.add('attendee', a, encode=0)

                cal.add_component(e)

        # print(cal.to_ical().decode("utf-8").replace('\r\n', '\n').strip())

        with open(f"./icalendar_{model.anno}.ics", "wb") as out:
            out.write(cal.to_ical())

        print(f"Dati salvati in turni_{model.anno}.csv, turni_per_vigile_{model.anno}.txt, icalendar_{model.anno}.ics "
              f"e riporti_{model.anno + 1}.csv.")
        return
