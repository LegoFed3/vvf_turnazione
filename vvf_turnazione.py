# from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import math
import vvf_io


class ILPTurnazione:
    # Collections
    giorno_squadra = {}
    var_notti = {}
    var_sabati = {}
    var_festivi = {}
    var_cost_servizi_vigile = {}
    var_cont_servizi_vigile_mese = {}
    var_diff_servizi_vigile_mesi = {}

    DB = {}
    vigili_squadra = {}
    anno = 0
    data_inizio = 0
    data_fine = 0
    num_medio_notti = -1
    _printed_solution = False
    _FESTIVI_SPECIALI = []
    _FESTIVI_ONEROSI = []
    _NOTTI_ONEROSE = []

    # Model
    solver = pywraplp.Solver('VVF_Turnazione', pywraplp.Solver.SCIP_MIXED_INTEGER_PROGRAMMING)
    STATUS = -1
    solution = []
    servizi_per_vigile = {}

    def __init__(self, args):
        print("* Creo il modello per la turnazione...")
        self.args = args
        self.data_inizio = args.data_di_inizio
        self.data_fine = args.data_di_fine
        self.anno = self.data_inizio.year
        if self.data_inizio.weekday() != 0:
            print("ERRORE: il giorno di inizio non è un lunedì!")
            exit(-1)
        if self.data_fine.weekday() != 6:
            print("ERRORE: il giorno di fine non è una domenica!")
            exit(-1)
        if (self.data_fine - self.data_inizio).days > 400:
            print(f"ERRORE: il periodo dal {self.data_inizio} al {self.data_fine} è troppo lungo, sicuri sia giusto?")
            exit(-1)
        elif (self.data_fine - self.data_inizio).days < 350:
            print(f"ERRORE: il periodo dal {self.data_inizio} al {self.data_fine} è troppo corto, sicuri sia giusto?")
            exit(-1)
        loose = args.loose

        self._compute_servizi_speciali_onerosi()
        self.DB = vvf_io.read_csv_vigili(args.organico_fn)
        self.DB = vvf_io.read_csv_riporti(self.DB, args.riporti_fn)
        self.vigili_squadra = {}
        for vigile in self.DB:
            # Squadra
            for squadra in self.DB[vigile].squadre:
                if squadra == 0:
                    continue
                elif squadra not in self.vigili_squadra:
                    self.vigili_squadra[squadra] = []
                self.vigili_squadra[squadra].append(vigile)

        num_squadre = len(self.vigili_squadra)
        num_giorni = self._get_offset_from_date(self.data_fine)
        curr_squadra = args.squadra_di_partenza
        if curr_squadra not in self.vigili_squadra:
            print(f"ERRORE: squadra iniziale {curr_squadra} inesistente!")
            exit(-1)

        print("* Fase 1: creo possibilità...")

        zero_vars = []
        giorno = 0
        settimana = 0
        pers_festivo_tot = 0
        num_festivi_estivi = 0
        pers_festivo = set()
        pers_notte = set()
        giorni_settimana = list(range(7))
        while giorno < num_giorni:

            for i in giorni_settimana:
                curr_giorno = giorno + i
                curr_data = self._get_date_from_offset(curr_giorno)
                self.giorno_squadra[curr_giorno] = curr_squadra

                # NOTTI

                # VAR: vigili di squadra candidati per la notte
                self.var_notti[curr_giorno] = {}
                for vigile in self.DB:
                    if (not self.DB[vigile].esente_notti()
                        and f"NoServiziMese{curr_data.month}" not in self.DB[vigile].eccezioni
                        and f"NoNottiMese{curr_data.month}" not in self.DB[vigile].eccezioni
                        and (curr_squadra in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre
                             or curr_data == dt.date(self.anno, 12, 31)  # Tutti candidati per capodanno
                             or "NottiAncheFuoriSettimana" in self.DB[vigile].eccezioni or loose)
                    ):
                        self.var_notti[curr_giorno][vigile] = \
                            self.solver.IntVar(0, 1, f"var_vigile({vigile})_notte({curr_giorno})")
                        if curr_squadra not in self.DB[vigile].squadre:
                            zero_vars.append(self.var_notti[curr_giorno][vigile])
                        pers_notte.add(vigile)

                # CONSTR: 1 vigile per notte
                c = self.solver.Constraint(1, 1, f"constr_notte({curr_giorno})")
                for var in self.var_notti[curr_giorno].values():
                    c.SetCoefficient(var, 1)

                # SABATO
                if curr_data.weekday() == 5 and curr_giorno not in self._FESTIVI_SPECIALI:

                    # VAR: vigili candidati per il sabato
                    self.var_sabati[curr_giorno] = {}
                    for vigile in self.DB:
                        if (not self.DB[vigile].esente_sabati()
                            and f"NoServiziMese{curr_data.month}" not in self.DB[vigile].eccezioni
                            and (curr_squadra in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre
                                 or loose)
                        ):
                            self.var_sabati[curr_giorno][vigile] = \
                                self.solver.IntVar(0, 1, f"var_vigile({vigile})_sabato({curr_giorno})")

                    # CONSTR: 1 vigile per sabato
                    c = self.solver.Constraint(1, 1, f"constr_sabato({curr_giorno})")
                    for vigile in self.DB:
                        if vigile in self.var_sabati[curr_giorno]:
                            c.SetCoefficient(self.var_sabati[curr_giorno][vigile], 1)

                # FESTIVO
                if curr_data.weekday() == 6 or curr_giorno in self._FESTIVI_SPECIALI:

                    # VAR: vigili candidati per il festivo
                    self.var_festivi[curr_giorno] = {}
                    for vigile in self.DB:
                        if (not self.DB[vigile].esente_festivi()
                            and f"NoServiziMese{curr_data.month}" not in self.DB[vigile].eccezioni
                            and (curr_squadra in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre
                                 or loose)
                        ):
                            self.var_festivi[curr_giorno][vigile] = \
                                self.solver.IntVar(0, 1, f"var_vigile({vigile})_festivo({curr_giorno})")
                            if curr_squadra not in self.DB[vigile].squadre:
                                zero_vars.append(self.var_festivi[curr_giorno][vigile])
                            pers_festivo.add(vigile)

                    # CONSTR: personale minimo
                    p = _MESE_TO_PERSONALE_FESTIVO[curr_data.month]
                    pers_festivo_tot += p
                    if p == 4:
                        num_festivi_estivi += 1
                    c = self.solver.Constraint(p, 4, f"constr_festivo({curr_giorno})_personale")
                    for vigile in self.var_festivi[curr_giorno]:
                        c.SetCoefficient(self.var_festivi[curr_giorno][vigile], 1)

                    # CONTR: max 3/4 vigili non aspiranti
                    c = self.solver.Constraint(3, p, f"constr_festivo({curr_giorno})_personale_non_aspirante")
                    for vigile in self.var_festivi[curr_giorno]:
                        if self.DB[vigile].grado not in ["Aspirante", "Allievo"]:
                            c.SetCoefficient(self.var_festivi[curr_giorno][vigile], 1)

                    # CONSTR: almeno 1 autista per festivo
                    c = self.solver.Constraint(1, self.solver.infinity(), f"constr_festivo({curr_giorno})_autista")
                    for vigile in self.var_festivi[curr_giorno]:
                        if self.DB[vigile].autista:
                            c.SetCoefficient(self.var_festivi[curr_giorno][vigile], 1)

                    # CONST: max 1 aspirante
                    c = self.solver.Constraint(-self.solver.infinity(), 1, f"constr_festivo({curr_giorno})_aspirante")
                    for vigile in self.var_festivi[curr_giorno]:
                        if self.DB[vigile].grado == "Aspirante":
                            c.SetCoefficient(self.var_festivi[curr_giorno][vigile], 1)

            # CONSTR: max 1 notte per vigile a settimana
            # Max 2+ se fa notti extra o solo in alcuni giorni
            c_notti_settimana_vigile = {}
            for vigile in self.var_notti[giorno]:  # curr_giorno?
                max_notti_settimana = 1
                if self.DB[vigile].delta_notti > 0:
                    max_notti_settimana = 2
                lim_giorni = len([e for e in self.DB[vigile].eccezioni if "NoNottiGiorno" in e])
                lim_mesi = len([e for e in self.DB[vigile].eccezioni if "NoNottiMese" in e])
                if (
                        "NottiSoloSabatoFestivi" in self.DB[vigile].eccezioni
                        # or self.DB[vigile].esenteCP()
                        or lim_giorni >= 4
                        or lim_mesi >= 4
                ):
                    max_notti_settimana = 2
                elif lim_mesi >= 8:
                    max_notti_settimana = 3
                c_notti_settimana_vigile[vigile] = \
                    self.solver.Constraint(-self.solver.infinity(), max_notti_settimana,
                                           f"constr_notti_settimana({settimana})_vigile({vigile})")
                for i in range(len(giorni_settimana)):
                    if vigile in self.var_notti[giorno + i]:
                        c_notti_settimana_vigile[vigile].SetCoefficient(self.var_notti[giorno + i][vigile], 1)

            curr_squadra = (curr_squadra % num_squadre) + 1
            giorno += len(giorni_settimana)
            settimana += 1

        # Inizializza soluzione per notti fuori squadra a 0
        if len(zero_vars) > 0:
            self.solver.SetHint(zero_vars, [0] * len(zero_vars))

        # Numero di notti, sabati e festivi
        print(f"\tL'anno avrà {len(self.var_notti)} notti, {len(self.var_sabati)} sabati "
              f"e {len(self.var_festivi)} festivi.")

        notti_extra_tot = sum([v.delta_notti for v in self.DB.values()])
        _NUM_MEDIO_NOTTI = (len(self.var_notti) - notti_extra_tot) / len(pers_notte)
        _NUM_MIN_NOTTI = math.floor(_NUM_MEDIO_NOTTI)
        _NUM_MAX_NOTTI = _NUM_MIN_NOTTI + 1

        print(f"\tCon {len(pers_notte)} vigili che svolgono notti ({notti_extra_tot} extra) "
              f"assegnerò {_NUM_MIN_NOTTI}-{_NUM_MAX_NOTTI} notti a testa.")

        _NUM_PERS_SABATI = len(self.var_sabati[5])  # Giorno 5 è sabato perchè 0 è lunedì
        sabati_extra_tot = sum([v.delta_sabati for v in self.DB.values()])
        _NUM_MIN_SABATI = 0
        _NUM_MAX_SABATI = 1
        if _NUM_PERS_SABATI < len(self.var_sabati) - sabati_extra_tot:
            media_sabati = len(self.var_sabati) / _NUM_PERS_SABATI
            _NUM_MIN_SABATI = math.floor(media_sabati)
            _NUM_MAX_SABATI = math.ceil(media_sabati)

        print(f"\tCon {_NUM_PERS_SABATI} vigili che svolgono sabati ({sabati_extra_tot} extra) "
              f"assegnerò {_NUM_MIN_SABATI}-{_NUM_MAX_SABATI} sabati a testa.")

        festivi_extra_tot = sum([v.delta_festivi for v in self.DB.values()])
        num_aspiranti_festivo = len([p for p in pers_festivo if self.DB[p].grado == "Aspirante"])
        num_vigili_festivo = len(pers_festivo) - num_aspiranti_festivo
        media_festivi = pers_festivo_tot / (len(pers_festivo) - 1)  # -1 perchè comandante e vice ne fanno metà
        media_festivi = (len(self.var_festivi) * 3 - festivi_extra_tot  # numero vigili necessari
                         + max(num_festivi_estivi - math.ceil(media_festivi) * num_aspiranti_festivo, 0)) / \
                        (num_vigili_festivo - 1)  # -1 perchè comandante e vice ne fanno metà
        _NUM_MIN_FESTIVI = math.floor(media_festivi)
        _NUM_MAX_FESTIVI = math.ceil(media_festivi)

        print(f"\tCon {num_vigili_festivo} vigili e {num_aspiranti_festivo} aspiranti che svolgono festivi "
              f"({festivi_extra_tot} extra) assegnerò {_NUM_MIN_FESTIVI}-{_NUM_MAX_FESTIVI} festivi a testa.")

        self._SERVIZI_MINIMI = _NUM_MIN_NOTTI + _NUM_MIN_SABATI + _NUM_MIN_FESTIVI

        print("* Fase 2: aggiungo vincoli...")

        for vigile in self.DB:
            if self.DB[vigile].esente_servizi():
                continue

            # CONSTR: numero notti
            if not self.DB[vigile].esente_notti():
                notti_attese = round(_NUM_MEDIO_NOTTI) + self.DB[vigile].delta_notti
                # if self.DB[vigile].delta_notti != 0 and notti_attese > _NUM_MEDIO_NOTTI:
                #     print(f"\t{self.DB[vigile]} avrà {notti_attese} notti, più della media ~{_NUM_MEDIO_NOTTI}.")
                # elif self.DB[vigile].delta_notti != 0 and notti_attese < _NUM_MEDIO_NOTTI:
                #     print(f"\t{self.DB[vigile]} avrà {notti_attese} notti, meno della media ~{_NUM_MEDIO_NOTTI}.")
                if self.DB[vigile].delta_notti != 0:
                    c = self.solver.Constraint(notti_attese, notti_attese, f"constr_notti_totali({vigile})")
                    for notte in self.var_notti:
                        if vigile in self.var_notti[notte]:
                            c.SetCoefficient(self.var_notti[notte][vigile], 1)
                else:  # notti standard
                    c = self.solver.Constraint(_NUM_MIN_NOTTI, _NUM_MAX_NOTTI + 1, f"constr_notti_totali({vigile})")
                    for notte in self.var_notti:
                        if vigile in self.var_notti[notte]:
                            c.SetCoefficient(self.var_notti[notte][vigile], 1)


            # CONSTR: numero sabati
            if not self.DB[vigile].esente_sabati():
                sabati_extra = self.DB[vigile].delta_sabati
                c = self.solver.Constraint(_NUM_MIN_SABATI + sabati_extra, _NUM_MAX_SABATI + sabati_extra,
                                           f"constr_sabati_vigile({vigile})")
                for sabato in self.var_sabati:
                    if vigile in self.var_sabati[sabato]:
                        c.SetCoefficient(self.var_sabati[sabato][vigile], 1)

            # CONSTR: max 1 tra venerdì notte, sabato e sabato notte
            if not self.DB[vigile].esente_sabati() and "NottiSoloSabatoFestivi" not in self.DB[vigile].eccezioni:
                for sabato in self.var_sabati:
                    if vigile not in self.var_sabati[sabato]:
                        continue
                    c = self.solver.Constraint(-self.solver.infinity(), 1,
                                               f"constr_no_sabato_notte_consec_vigile({vigile})_sabato({sabato})")
                    c.SetCoefficient(self.var_sabati[sabato][vigile], 1)
                    if vigile in self.var_notti[sabato]:
                        c.SetCoefficient(self.var_notti[sabato][vigile], 1)
                    if vigile in self.var_notti[sabato - 1]:
                        c.SetCoefficient(self.var_notti[sabato - 1][vigile], 1)

            # CONSTR: max 1 tra sabato e festivi circostanti
            if not self.DB[vigile].esente_sabati() and not self.DB[vigile].esente_festivi():
                for sabato in self.var_sabati:
                    if vigile not in self.var_sabati[sabato]:
                        continue
                    c = self.solver.Constraint(-self.solver.infinity(), 1,
                                               f"constr_sabato_festivi_circostanti_vigile({vigile})_sabato({sabato})")
                    c.SetCoefficient(self.var_sabati[sabato][vigile], 1)
                    for i in range(1, 8):
                        if (sabato - i) in self.var_festivi and vigile in self.var_festivi[sabato - i]:
                            c.SetCoefficient(self.var_festivi[sabato - i][vigile], 1)
                        if (sabato + i) in self.var_festivi and vigile in self.var_festivi[sabato + i]:
                            c.SetCoefficient(self.var_festivi[sabato + i][vigile], 1)

            # CONSTR: max 1 tra festivo e notti circostanti
            for festivo in self.var_festivi:
                if (
                    "NottiSoloSabato" not in self.DB[vigile].eccezioni
                    and ("NottiSoloSabatoFestivi" not in self.DB[vigile].eccezioni
                         or self._get_weekday_from_offset(festivo) not in [5, 6])
                    and not self.DB[vigile].esente_notti()
                    and not self.DB[vigile].esente_festivi()
                    and vigile in self.var_festivi[festivo]
                ):
                    c = self.solver.Constraint(-self.solver.infinity(), 1,
                                               f"constr_no_festivo_notte_consec_vigile({vigile})_festivo({festivo})")
                    c.SetCoefficient(self.var_festivi[festivo][vigile], 1)
                    if vigile in self.var_notti[festivo]:
                        c.SetCoefficient(self.var_notti[festivo][vigile], 1)
                    giorno_prima = festivo - 1
                    if vigile in self.var_notti[giorno_prima]:
                        c.SetCoefficient(self.var_notti[giorno_prima][vigile], 1)

            # CONSTR: max 1 notte in 4 giorni consecutivi
            for notte in self.var_notti:
                if vigile in self.var_notti[notte]:
                    c = self.solver.Constraint(-self.solver.infinity(), 1,
                                               f"constr_notti_consec_vigile({vigile})_giorno({notte}-{notte + 3})")
                    c.SetCoefficient(self.var_notti[notte][vigile], 1)
                    if notte + 1 in self.var_notti and vigile in self.var_notti[notte + 1]:
                        c.SetCoefficient(self.var_notti[notte + 1][vigile], 1)
                    if notte + 2 in self.var_notti and vigile in self.var_notti[notte + 2]:
                        c.SetCoefficient(self.var_notti[notte + 2][vigile], 1)
                    if notte + 3 in self.var_notti and vigile in self.var_notti[notte + 3]:
                        c.SetCoefficient(self.var_notti[notte + 3][vigile], 1)

            # CONSTR: no festivi in settimane adiacenti
            for festivo in self.var_festivi:
                next_festivi = []
                for i in range(1, 8):
                    if festivo + i in self.var_festivi:
                        next_festivi.append(festivo + i)
                if len(next_festivi) == 0:
                    continue
                if vigile in self.var_festivi[festivo]:
                    c = self.solver.Constraint(-self.solver.infinity(), 1,
                                               f"constr_festivi_consec_vigile({vigile})_giorno({festivo})")
                    c.SetCoefficient(self.var_festivi[festivo][vigile], 1)
                    for next_festivo in next_festivi:
                        if vigile in self.var_festivi[next_festivo]:
                            c.SetCoefficient(self.var_festivi[next_festivo][vigile], 1)

            # CONSTR: max 1 servizio oneroso l'anno
            c = self.solver.Constraint(-self.solver.infinity(), 1, f"constr_servizi_onerosi_vigile({vigile})")
            for festivo in self.var_festivi:
                if festivo in self._FESTIVI_ONEROSI:
                    if vigile in self.var_festivi[festivo]:
                        c.SetCoefficient(self.var_festivi[festivo][vigile], 1)
            for notte in self.var_notti:
                if notte in self._NOTTI_ONEROSE:
                    if vigile in self.var_notti[notte]:
                        c.SetCoefficient(self.var_notti[notte][vigile], 1)

            # CONSTR: numero festivi
            if not self.DB[vigile].esente_festivi():
                c = self.solver.Constraint(_NUM_MIN_FESTIVI + self.DB[vigile].delta_festivi,
                                           _NUM_MAX_FESTIVI + self.DB[vigile].delta_festivi,
                                           f"constr_festivi_vigile({vigile})")
                for festivo in self.var_festivi:
                    if vigile in self.var_festivi[festivo]:
                        c.SetCoefficient(self.var_festivi[festivo][vigile], 1)

            # ECCEZIONI alle regole usuali
            if len(self.DB[vigile].eccezioni) > 0:

                # CONSTR_EX: notti solo il sabato o festivi
                if "NottiSoloSabatoFestivi" in self.DB[vigile].eccezioni:
                    c = self.solver.Constraint(-self.solver.infinity(), 0,
                                               f"constr_ex_notti_solo_sabato_festivi_vigile({vigile})")
                    for giorno in self.var_notti:
                        if vigile in self.var_notti[giorno] and self._get_weekday_from_offset(
                                giorno) != 5 and giorno not in self.var_festivi:
                            c.SetCoefficient(self.var_notti[giorno][vigile], 1)

                # CONSTR_EX: no notti in specifici giorni della settimana
                giorni_da_saltare = [_GIORNO_TO_NUM[e[len("NoNottiGiorno"):]] for e in self.DB[vigile].eccezioni
                                     if "NoNottiGiorno" in e]
                if len(giorni_da_saltare) > 0:
                    c = self.solver.Constraint(-self.solver.infinity(), 0,
                                               f"constr_ex_no_notti_giornosettimana_vigile({vigile})")
                    for giorno in self.var_notti:
                        if self._get_weekday_from_offset(giorno) in giorni_da_saltare:
                            if vigile in self.var_notti[giorno]:
                                c.SetCoefficient(self.var_notti[giorno][vigile], 1)

                # CONSTR_EX: no notti specifico mese
                mesi_da_saltare = [int(e[len("NoNottiMese"):]) for e in self.DB[vigile].eccezioni if "NoNottiMese" in e]
                if len(mesi_da_saltare) > 0:
                    c = self.solver.Constraint(-self.solver.infinity(), 0, f"constr_ex_no_notti_mese({vigile})")
                    for giorno in self.var_notti:
                        mese = self._get_date_from_offset(giorno).month + \
                               (self._get_date_from_offset(giorno).year - self.anno) * 12
                        if mese in mesi_da_saltare:
                            if vigile in self.var_notti[giorno]:
                                c.SetCoefficient(self.var_notti[giorno][vigile], 1)

                # CONSTR_EX: no sabati specifico mese
                mesi_da_saltare = [int(e[len("NoSabatiMese"):]) for e in self.DB[vigile].eccezioni if "NoSabatiMese" in e]
                if len(mesi_da_saltare) > 0:
                    c = self.solver.Constraint(-self.solver.infinity(), 0, f"constr_ex_no_sabati_mese({vigile})")
                    for giorno in self.var_sabati:
                        mese = self._get_date_from_offset(giorno).month + \
                               (self._get_date_from_offset(giorno).year - self.anno) * 12
                        if mese in mesi_da_saltare:
                            if vigile in self.var_sabati[giorno]:
                                c.SetCoefficient(self.var_sabati[giorno][vigile], 1)

                # CONSTR_EX: no festivi specifico mese
                mesi_da_saltare = [int(e[len("NoFestiviMese"):]) for e in self.DB[vigile].eccezioni if "NoFestiviMese" in e]
                if len(mesi_da_saltare) > 0:
                    c = self.solver.Constraint(-self.solver.infinity(), 0, f"constr_ex_no_festivi_mese({vigile})")
                    for giorno in self.var_festivi:
                        mese = self._get_date_from_offset(giorno).month + \
                               (self._get_date_from_offset(giorno).year - self.anno) * 12
                        if mese in mesi_da_saltare:
                            if vigile in self.var_festivi[giorno]:
                                c.SetCoefficient(self.var_festivi[giorno][vigile], 1)

                # CONSTR_EX: no servizi specifico mese
                mesi_da_saltare = [int(e[len("NoServiziMese"):]) for e in self.DB[vigile].eccezioni if
                                   "NoServiziMese" in e]
                if len(mesi_da_saltare) > 0:
                    c = self.solver.Constraint(-self.solver.infinity(), 0,
                                               f"constr_ex_no_servizi_mese_vigile({vigile})")
                    for giorno in self.var_notti:
                        mese = self._get_date_from_offset(giorno).month + \
                               (self._get_date_from_offset(giorno).year - self.anno) * 12
                        if mese in mesi_da_saltare:
                            if vigile in self.var_notti[giorno]:
                                c.SetCoefficient(self.var_notti[giorno][vigile], 1)
                            if giorno in self.var_sabati and vigile in self.var_sabati[giorno]:
                                c.SetCoefficient(self.var_sabati[giorno][vigile], 1)
                            elif giorno in self.var_festivi and vigile in self.var_festivi[giorno] \
                                    and "FestiviComunque" not in self.DB[vigile].eccezioni:
                                c.SetCoefficient(self.var_festivi[giorno][vigile], 1)

            # CONSTR: no servizi il giorno di compleanno
            if not args.servizi_compleanno:
                compleanno = self.DB[vigile].offset_compleanno(self.data_inizio)
                c = self.solver.Constraint(-self.solver.infinity(), 0, f"constr_compleanno_vigile({vigile})")
                if compleanno in self.var_notti and not (self.DB[vigile].esente_notti()):
                    if vigile in self.var_notti[compleanno]:
                        c.SetCoefficient(self.var_notti[compleanno][vigile], 1)
                if compleanno in self.var_sabati and not (self.DB[vigile].esente_sabati()) \
                        and vigile in self.var_sabati[compleanno]:
                    c.SetCoefficient(self.var_sabati[compleanno][vigile], 1)
                if compleanno in self.var_festivi and not (self.DB[vigile].esente_festivi()) \
                        and vigile in self.var_festivi[compleanno]:
                    c.SetCoefficient(self.var_festivi[compleanno][vigile], 1)

            # Somma costo servizi per calcolo distribuzione equa
            if not self.DB[vigile].esente_servizi():

                # VAR: costo servizi per vigile (ausiliaria)
                self.var_cost_servizi_vigile[vigile] = self.solver.NumVar(0, self.solver.infinity(),
                                                                          f"var_aux_cost_servizi_vigile({vigile})")
                # CONSTR: implementa quanto sopra
                c = -2 * self.DB[vigile].passato_servizi_extra + self.DB[vigile].delta_notti + \
                    self.DB[vigile].delta_sabati + self.DB[vigile].delta_festivi
                c = self.solver.Constraint(c, c, f"constr_costo_servizi_vigile({vigile})")
                c.SetCoefficient(self.var_cost_servizi_vigile[vigile], -1)
                mul_sabati = 1 + sum(self.DB[vigile].passato_sabati)  # Sabati più probabili se pochi in anni recenti
                compleanno = self.DB[vigile].offset_compleanno(self.data_inizio)
                for giorno in range(len(self.var_notti)):
                    mul_squadra = 1
                    mul_bday = 1
                    pen_notti_onerose = 0
                    pen_festivi_onerosi = 0
                    if giorno == compleanno:
                        mul_bday = 2
                    if giorno in self._NOTTI_ONEROSE:
                        pen_notti_onerose = 1
                    if giorno in self._FESTIVI_ONEROSI:
                        pen_festivi_onerosi = 2 + sum(self.DB[vigile].passato_festivi_onerosi)
                    if not (self.giorno_squadra[giorno] in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre):
                        mul_squadra = 2  # Servizi NON di squadra costano di più
                    if giorno in self.var_sabati:
                        if vigile in self.var_sabati[giorno]:
                            c.SetCoefficient(self.var_sabati[giorno][vigile],
                                             2 * mul_bday * mul_squadra * mul_squadra * mul_sabati)
                    if giorno in self.var_festivi:
                        if vigile in self.var_festivi[giorno]:
                            # Base 1.5 per incoraggiare massima equità
                            if self.DB[vigile].grado == "Aspirante":
                                c.SetCoefficient(self.var_festivi[giorno][vigile],
                                                 mul_bday * mul_squadra * mul_squadra - 1)
                            else:
                                c.SetCoefficient(self.var_festivi[giorno][vigile],
                                                 1.5 * mul_bday * mul_squadra * mul_squadra + pen_festivi_onerosi)
                    if vigile in self.var_notti[giorno]:
                        if giorno == self._NOTTI_ONEROSE[2]:  # Capodanno
                            c.SetCoefficient(self.var_notti[giorno][vigile],
                                             1 * mul_bday + 100 * self.DB[vigile].passato_capodanni)
                        else:
                            if mul_squadra > 1 and self.DB[vigile].delta_notti > 0 \
                                    or "NottiAncheFuoriSettimana" in self.DB[vigile].eccezioni:
                                mul_squadra = 1.5  # con notti in più paga meno a metterle fuori settimana
                            c.SetCoefficient(self.var_notti[giorno][vigile],
                                             1 * mul_bday * mul_squadra + pen_notti_onerose)

        # CONSTR: numero servizi uguale per tutti +/- 1
        for vigile in self.DB:
            if self.DB[vigile].esente_servizi():
                continue
            num_servizi_minimi = 0
            if not self.DB[vigile].esente_sabati():
                num_servizi_minimi += _NUM_MIN_SABATI + self.DB[vigile].delta_sabati
            if not self.DB[vigile].esente_festivi():
                num_servizi_minimi += _NUM_MIN_FESTIVI + self.DB[vigile].delta_festivi
            if not self.DB[vigile].esente_notti():
                num_servizi_minimi += _NUM_MIN_NOTTI + self.DB[vigile].delta_notti
            if self.DB[vigile].grado != "Aspirante":
                c = self.solver.Constraint(num_servizi_minimi, num_servizi_minimi + 1,
                                           f"constr_servizi_totali_vigile({vigile})")
            else:
                c = self.solver.Constraint(num_servizi_minimi + 1, num_servizi_minimi + 1,
                                           f"constr_servizi_totali_vigile({vigile})")
            for collection in [self.var_notti, self.var_sabati, self.var_festivi]:
                for var in collection.values():
                    if vigile in var:
                        c.SetCoefficient(var[vigile], 1)

        # VAR: contatore servizi per mese (ausiliaria)
        for vigile in self.DB:
            self.var_cont_servizi_vigile_mese[vigile] = {}
            for mese in range(1, 13+1):
                self.var_cont_servizi_vigile_mese[vigile][mese] = \
                    self.solver.IntVar(0, self.solver.infinity(), f"var_aux_cont_servizi_vigile({vigile})_mese({mese})")
        # CONSTR: implementa quanto sopra
        for vigile in self.var_cont_servizi_vigile_mese:
            for mese in self.var_cont_servizi_vigile_mese[vigile]:
                c = self.solver.Constraint(0, 0, f"constr_cont_servizi_vigile({vigile})_mese({mese})")
                c.SetCoefficient(self.var_cont_servizi_vigile_mese[vigile][mese], 1)
                for giorno in range(len(self.var_notti)):
                    mese_srv = self._get_date_from_offset(giorno).month + (
                            self._get_date_from_offset(giorno).year - self.anno) * 12
                    if mese_srv != mese:
                        continue
                    if vigile in self.var_notti[giorno]:
                        c.SetCoefficient(self.var_notti[giorno][vigile], -1)
                        if giorno in self.var_sabati and vigile in self.var_sabati[giorno]:
                            c.SetCoefficient(self.var_sabati[giorno][vigile], -1)
                        elif giorno in self.var_festivi and vigile in self.var_festivi[giorno] \
                                and "FestiviComunque" not in self.DB[vigile].eccezioni:
                            c.SetCoefficient(self.var_festivi[giorno][vigile], -1)

        # Distribuisci servizi durante l'anno
        for vigile in self.var_cont_servizi_vigile_mese:
            num_servizi_minimi = 0
            num_servizi_per_mese = 0
            num_mesi = 13
            for mese in self.var_cont_servizi_vigile_mese[vigile]:
                if f"NoServiziMese{mese}" in self.DB[vigile].eccezioni or (
                        f"NoNottiMese{mese}" in self.DB[vigile].eccezioni and
                        f"NoSabatiMese{mese}" in self.DB[vigile].eccezioni and
                        f"NoFestiviMese{mese}" in self.DB[vigile].eccezioni
                ):
                    num_mesi -= 1
            if not self.DB[vigile].esente_sabati():
                num_servizi_minimi += _NUM_MIN_SABATI + self.DB[vigile].delta_sabati
            if not self.DB[vigile].esente_festivi():
                num_servizi_minimi += _NUM_MIN_FESTIVI + self.DB[vigile].delta_festivi
            if not self.DB[vigile].esente_notti():
                num_servizi_minimi += _NUM_MIN_NOTTI + self.DB[vigile].delta_notti
            if num_servizi_minimi > 0:
                num_servizi_per_mese = math.ceil((num_servizi_minimi + 1) / num_mesi)
            for mese in self.var_cont_servizi_vigile_mese[vigile]:
                c = self.solver.Constraint(-self.solver.infinity(), num_servizi_per_mese,
                                           f"constr_lim_servizi_vigile({vigile})_mese({mese})")
                c.SetCoefficient(self.var_cont_servizi_vigile_mese[vigile][mese], 1)

        # mesi = list(range(1, 13))
        # for vigile in self.var_cont_servizi_vigile_mese:
        #     if self.DB[vigile].esente_servizi():
        #         continue
        #     self.var_diff_servizi_vigile_mesi[vigile] = {}
        #     for i in mesi:
        #         for j in [i + 1]:
        #             # VAR: differenza numero servizi tra due mesi (ausiliaria)
        #             self.var_diff_servizi_vigile_mesi[vigile][(i, j)] = \
        #                 self.solver.NumVar(-self.solver.infinity(), self.solver.infinity(),
        #                                    f"constr_diff_servizi_vigile({vigile})_mesi({i},{j})")
        #             # CONSTR: implementa quanto sopra
        #             c_plus = self.solver.Constraint(-self.solver.infinity(), 0,
        #                                             f"constr_diff_servizi_plus_vigile({vigile})_mesi({i},{j})")
        #             c_plus.SetCoefficient(self.var_diff_servizi_vigile_mesi[vigile][(i, j)], -1)
        #             c_plus.SetCoefficient(self.var_cont_servizi_vigile_mese[vigile][i], 1)
        #             c_plus.SetCoefficient(self.var_cont_servizi_vigile_mese[vigile][j], -1)
        #             c_minus = self.solver.Constraint(-self.solver.infinity(), 0,
        #                                              f"constr_diff_servizi_minus_vigile({vigile})_mesi({i},{j})")
        #             c_minus.SetCoefficient(self.var_diff_servizi_vigile_mesi[vigile][(i, j)], -1)
        #             c_minus.SetCoefficient(self.var_cont_servizi_vigile_mese[vigile][i], -1)
        #             c_minus.SetCoefficient(self.var_cont_servizi_vigile_mese[vigile][j], 1)

        print(f"\tIl modello ha {self.solver.NumVariables()} variabili e {self.solver.NumConstraints()} vincoli.")

        print("* Fase 3: definisco l'obiettivo...")

        # OBJECTIVE
        objective = self.solver.Objective()
        # OBJ: minimizza le differenze tra servizi di ciascun vigile mese per mese
        for vigile in self.var_diff_servizi_vigile_mesi:
            for var in self.var_diff_servizi_vigile_mesi[vigile].values():
                objective.SetCoefficient(var, 1)
        # OBJ: minimizza il costo totale dei servizi
        for var in self.var_cost_servizi_vigile.values():
            objective.SetCoefficient(var, (len(self.DB) - 1) * 13)
        objective.SetMinimization()

        model_f = open("model.txt", "w")
        model_f.write(self.solver.ExportModelAsLpFormat(False))
        # model_f.write(Solver.ExportModelAsMpsFormat(True, False))
        model_f.close()

    def solve(self):
        # Solver Parameters
        self.solver.SetNumThreads(self.args.jobs)
        gap = 0.00001
        solver_params = pywraplp.MPSolverParameters()
        solver_params.SetDoubleParam(solver_params.RELATIVE_MIP_GAP, gap)
        if self.args.time_limit > 0:
            self.solver.SetTimeLimit(self.args.time_limit * 1000)  # ms
        print("* Risolvo il modello... (max {}s)".format(self.args.time_limit if self.args.time_limit > 0 else "∞"))
        if not self.solver.SetSolverSpecificParametersAsString(f"randomization/randomseedshift {self.args.seed}"):
            print("ERRORE: non sono riuscito a configurare il random seed di SCIP.")
            exit(-1)
        if self.args.verbose:
            print("SCIP output:")
            self.solver.EnableOutput()
        self.STATUS = self.solver.Solve(solver_params)
        self.print_solution()
        self.save_solution()

    def print_solution(self):
        print()
        if self.STATUS == pywraplp.Solver.NOT_SOLVED:
            print('ATTENZIONE: non sono riuscito a calcolare una soluzione nel tempo concessomi.')
            print("\tDammi più tempo e riprova.")
            exit(0)
        elif self.STATUS == pywraplp.Solver.INFEASIBLE:
            print('ATTENZIONE: Il problema non ammette soluzione.')
            print('\tRilassa i vincoli e riprova.')
            exit(0)
        else:
            if self.STATUS == pywraplp.Solver.FEASIBLE:
                print("ATTENZIONE: la soluzione trovata potrebbe non essere ottimale.")
            servizi_fuori_squadra = 0
            capodanno = "NON CALCOLATO"
            print('* Soluzione:')
            print('Funzione obiettivo: ', self.solver.Objective().Value())
            print('Servizi per vigile:')
            for vigile in self.DB:
                for giorno in self.var_notti:
                    if vigile in self.var_notti[giorno]:
                        self.DB[vigile].notti += int(self.var_notti[giorno][vigile].solution_value())
                        if giorno == self._NOTTI_ONEROSE[2] and self.var_notti[giorno][vigile].solution_value() == 1:
                            self.DB[vigile].capodanno += 1
                            capodanno = f"{ self.DB[vigile].nome} { self.DB[vigile].cognome}"
                        if self.giorno_squadra[giorno] not in self.DB[vigile].squadre and self.DB[vigile].haSquadra():
                            self.DB[vigile].notti_fuori_squadra += int(self.var_notti[giorno][vigile].solution_value())
                            servizi_fuori_squadra += int(self.var_notti[giorno][vigile].solution_value())
                for giorno in self.var_sabati:
                    if vigile in self.var_sabati[giorno]:
                        self.DB[vigile].sabati += int(self.var_sabati[giorno][vigile].solution_value())
                        if self.giorno_squadra[giorno] not in self.DB[vigile].squadre and self.DB[vigile].haSquadra():
                            self.DB[vigile].sabati_fuori_squadra += \
                                int(self.var_sabati[giorno][vigile].solution_value())
                            servizi_fuori_squadra +=  int(self.var_sabati[giorno][vigile].solution_value())
                for giorno in self.var_festivi:
                    if vigile in self.var_festivi[giorno]:
                        self.DB[vigile].festivi += int(self.var_festivi[giorno][vigile].solution_value())
                        if giorno in self._FESTIVI_ONEROSI \
                                and self.var_festivi[giorno][vigile].solution_value() == 1:
                            self.DB[vigile].festivi_onerosi += 1
                        if self.giorno_squadra[giorno] not in self.DB[vigile].squadre and self.DB[vigile].haSquadra():
                            self.DB[vigile].festivi_fuori_squadra += \
                                int(self.var_festivi[giorno][vigile].solution_value())
                            servizi_fuori_squadra += int(self.var_festivi[giorno][vigile].solution_value())
                line = str(self.DB[vigile])
                line += f": {self.DB[vigile].notti + self.DB[vigile].sabati + self.DB[vigile].festivi}"
                line += f"\n\tNotti: {self.DB[vigile].notti} ({self.DB[vigile].notti_fuori_squadra})"
                line += f"\n\tSabati: {self.DB[vigile].sabati} ({self.DB[vigile].sabati_fuori_squadra})"
                line += f"\n\tFestivi: {self.DB[vigile].festivi} ({self.DB[vigile].festivi_fuori_squadra})"
                if len(self.DB[vigile].eccezioni) > 0:
                    line += f"\n\tEccezioni: {self.DB[vigile].eccezioni}"
                print(line)
            print(f"Totale servizi assegnati fuori dalla squadra: {servizi_fuori_squadra}")
            print(f"Vigile designato per la notte di capodanno: {capodanno}")

    def save_solution(self):
        print("Salvo la soluzione trovata...")
        for vigile in self.DB:
            self.servizi_per_vigile[vigile] = []
        for giorno in range(len(self.var_notti)):
            data = self.data_inizio + dt.timedelta(giorno)
            self.solution.append({
                'data': data,
                'notte': [],
                'notte_affiancamenti': [],
                'sabato': [],
                'sabato_affiancamenti': [],
                'festivo': [],
                'festivo_affiancamenti': [],
            })
            for vigile in self.var_notti[giorno]:
                if self.var_notti[giorno][vigile].solution_value() == 1:
                    self.solution[giorno]['notte'].append(vigile)
                    self.servizi_per_vigile[vigile].append((data.strftime("%d/%m/%Y") + " notte"))
            if giorno in self.var_sabati:
                for vigile in self.var_sabati[giorno]:
                    if self.var_sabati[giorno][vigile].solution_value() == 1:
                        self.solution[giorno]['sabato'].append(vigile)
                        self.servizi_per_vigile[vigile].append((data.strftime("%d/%m/%Y") + " sabato"))
            elif giorno in self.var_festivi:
                for vigile in self.var_festivi[giorno]:
                    if self.var_festivi[giorno][vigile].solution_value() == 1:
                        self.solution[giorno]['festivo'].append(vigile)
                        self.servizi_per_vigile[vigile].append((data.strftime("%d/%m/%Y") + " festivo"))
        return

    def _compute_servizi_speciali_onerosi(self):
        pasqua = _calc_easter(self.anno)
        print(f"\tPasqua cade il {pasqua}.")
        self._FESTIVI_SPECIALI = [
            dt.date(self.anno, 1, 6),  # Epifania
            pasqua,  # Pasqua
            pasqua + dt.timedelta(days=1),  # Pasquetta
            dt.date(self.anno, 4, 25),  # 25 Aprile
            dt.date(self.anno, 5, 1),  # 1 Maggio
            dt.date(self.anno, 6, 2),  # 2 Giugno
            dt.date(self.anno, 8, 15),  # Ferragosto
            dt.date(self.anno, 11, 1),  # 1 Novembre
            dt.date(self.anno, 12, 8),  # 8 Dicembre
            dt.date(self.anno, 12, 25),  # Natale
            dt.date(self.anno, 12, 26),  # S. Stefano
            dt.date(self.anno + 1, 1, 1),  # 1 Gennaio
            dt.date(self.anno + 1, 1, 6),  # Epifania
        ]
        self._NOTTI_ONEROSE = [
            dt.date(self.anno, 12, 24),  # Natale
            dt.date(self.anno, 12, 25),  # Natale
            dt.date(self.anno, 12, 31),  # Capodanno
        ]
        self._FESTIVI_SPECIALI = list(map(self._get_offset_from_date, self._FESTIVI_SPECIALI))
        self._NOTTI_ONEROSE = list(map(self._get_offset_from_date, self._NOTTI_ONEROSE))
        self._FESTIVI_ONEROSI = [
            self._FESTIVI_SPECIALI[1],  # Pasqua
            self._FESTIVI_SPECIALI[2],  # Pasquetta
            self._FESTIVI_SPECIALI[5],  # 2 Giugno
            self._FESTIVI_SPECIALI[6],  # Ferragosto
            dt.date(self.anno, 12, 24),  # Vigilia di Natale (se festivo)
            self._FESTIVI_SPECIALI[9],  # Natale
            self._FESTIVI_SPECIALI[10],  # S. Stefano
            dt.date(self.anno, 12, 31),  # 31 Dicembre (se festivo)
            self._FESTIVI_SPECIALI[11],  # 1 Gennaio
        ]

    def _get_date_from_offset(self, offset):
        return self.data_inizio + dt.timedelta(offset)

    def _get_weekday_from_offset(self, offset):
        return self._get_date_from_offset(offset).weekday()

    def _get_offset_from_date(self, date):
        return (date - self.data_inizio).days


def _calc_easter(year):
    """Returns Easter as a date object."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return dt.date(year, month, day)


_GIORNO_TO_NUM = {
    "Lun": 0,
    "Mar": 1,
    "Mer": 2,
    "Gio": 3,
    "Ven": 4,
    "Sab": 5,
    "Dom": 6,
}

_MESE_TO_PERSONALE_FESTIVO = {
    1: 3,
    2: 3,
    3: 3,
    4: 3,
    5: 4,
    6: 4,
    7: 4,
    8: 4,
    9: 4,
    10: 4,
    11: 3,
    12: 3,
}
