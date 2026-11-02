from ortools.sat.python import cp_model
import csv
import logging
import datetime as dt
import math
import re
import time
import vvf_io

logger = logging.getLogger(__name__)

# Pesi dei servizi nel costo (penalità) da minimizzare
_MUL_NOTTI = 1
_MUL_SABATI = 2
_MUL_FESTIVI = 1.5
# CP-SAT richiede coefficienti interi: tutti i costi sono multipli di 0.5, quindi si moltiplicano per 2
_SCALA_COSTI = 2


class Turnazione:
    def __init__(self, args):
        self.args = args
        self.data_inizio = args.data_di_inizio
        self.data_fine = args.data_di_fine
        self.anno = self.data_inizio.year
        if self.data_inizio.weekday() != 0:
            logger.error("il giorno di inizio non è un lunedì!")
            exit(-1)
        if self.data_fine.weekday() != 6:
            logger.error("il giorno di fine non è una domenica!")
            exit(-1)
        if (self.data_fine - self.data_inizio).days > 400:
            logger.error(f"il periodo dal {self.data_inizio} al {self.data_fine} è troppo lungo, sicuri sia giusto?")
            exit(-1)
        elif (self.data_fine - self.data_inizio).days < 350:
            logger.error(f"il periodo dal {self.data_inizio} al {self.data_fine} è troppo corto, sicuri sia giusto?")
            exit(-1)

        self.giorno_squadra = {}
        self.giorno_squadra_festivo = {}
        self.var_notti = {}
        self.var_sabati = {}
        self.var_festivi = {}
        self.DB: dict[int, vvf_io.Vigile] = {}
        self.solution = []
        self.servizi_per_vigile = {}
        self.model = cp_model.CpModel()
        self.cp_solver = None
        self.STATUS = None
        self._termini_costo = []  # (coefficiente, variabile)
        self._costo_costante = 0

        logger.info("* Creo il modello per la turnazione...")
        self._build_model()

    # ------------------------------------------------------------------------------------------------------------
    # Costruzione del modello
    # ------------------------------------------------------------------------------------------------------------

    def _add_constraint(self, name, terms, lb=None, ub=None):
        """Aggiunge il vincolo lb <= somma(termini) <= ub (None = illimitato)."""
        terms = [t for t in terms if t is not None]
        if terms:
            ct = self.model.AddLinearConstraint(sum(terms), cp_model.INT_MIN if lb is None else lb,
                                                cp_model.INT_MAX if ub is None else ub)
        elif (lb is None or lb <= 0) and (ub is None or 0 <= ub):
            return  # Vincolo vuoto e banalmente soddisfatto
        else:
            ct = self.model.AddBoolOr([])  # Vincolo vuoto e impossibile (e.g. nessun candidato per una notte)
        ct.WithName(name)

    def _build_model(self):
        args = self.args
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
            logger.error(f"squadra iniziale {curr_squadra} inesistente!")
            exit(-1)

        # Dal 2027 i graduati che coprono le domeniche non fanno sabati (compensati con festivi, vedi sotto)
        for v in self.DB.values():
            if v.graduato_per_festivo() and not v.esente_festivi() and not v.esente_sabati():
                v.cede_sabati = True

        logger.info("* Fase 1: creo possibilità...")

        zero_vars = []
        giorno = 0
        settimana = 0
        pers_festivo = set()
        pers_sabato = set()
        pers_notte = set()
        giorni_settimana = list(range(7))
        while giorno < num_giorni:

            for i in giorni_settimana:
                curr_giorno = giorno + i
                curr_data = self._get_date_from_offset(curr_giorno)
                self.giorno_squadra[curr_giorno] = curr_squadra
                self.giorno_squadra_festivo[curr_giorno] = curr_squadra
                # Se lunedì è squadra precedente
                if self._get_weekday_from_offset(curr_giorno) == 0:
                    self.giorno_squadra_festivo[curr_giorno] = (curr_squadra - 2) % num_squadre + 1

                # NOTTI

                # VAR: vigili di squadra candidati per la notte
                self.var_notti[curr_giorno] = {}
                for vigile in self.DB:
                    if (
                            not self.DB[vigile].esente_notti()
                            and f"NoServiziMese{curr_data.month}" not in self.DB[vigile].eccezioni
                            and f"NoNottiMese{curr_data.month}" not in self.DB[vigile].eccezioni
                            and (curr_squadra in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre
                                 or curr_data == dt.date(self.anno, 12, 31)  # Tutti candidati per capodanno
                                 or "NottiAncheFuoriSettimana" in self.DB[vigile].eccezioni or loose)
                    ):
                        self.var_notti[curr_giorno][vigile] = \
                            self.model.NewBoolVar(f"var_vigile({vigile})_notte({curr_giorno})")
                        if curr_squadra not in self.DB[vigile].squadre and self.DB[vigile].haSquadra():
                            zero_vars.append(self.var_notti[curr_giorno][vigile])
                        pers_notte.add(vigile)

                # CONSTR: 1 vigile per notte
                self._add_constraint(f"constr_notte({curr_giorno})", self.var_notti[curr_giorno].values(), 1, 1)

                # SABATO
                if curr_data.weekday() == 5 and curr_giorno not in self._FESTIVI_SPECIALI:

                    # VAR: vigili candidati per il sabato
                    self.var_sabati[curr_giorno] = {}
                    for vigile in self.DB:
                        if (
                                not self.DB[vigile].esente_sabati()
                                and f"NoServiziMese{curr_data.month}" not in self.DB[vigile].eccezioni
                                and (curr_squadra in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre
                                     or loose)
                        ):
                            self.var_sabati[curr_giorno][vigile] = \
                                self.model.NewBoolVar(f"var_vigile({vigile})_sabato({curr_giorno})")
                            pers_sabato.add(vigile)

                    # CONSTR: 1 vigile per sabato
                    self._add_constraint(f"constr_sabato({curr_giorno})", self.var_sabati[curr_giorno].values(), 1, 1)

                # FESTIVO
                if curr_data.weekday() == 6 or curr_giorno in self._FESTIVI_SPECIALI:

                    # VAR: vigili candidati per il festivo
                    self.var_festivi[curr_giorno] = {}
                    squadra_festivo = self.giorno_squadra_festivo[curr_giorno]
                    for vigile in self.DB:
                        if (
                                not self.DB[vigile].esente_festivi()
                                and f"NoServiziMese{curr_data.month}" not in self.DB[vigile].eccezioni
                                and (squadra_festivo in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre
                                     or loose)
                        ):
                            self.var_festivi[curr_giorno][vigile] = \
                                self.model.NewBoolVar(f"var_vigile({vigile})_festivo({curr_giorno})")
                            if squadra_festivo not in self.DB[vigile].squadre and self.DB[vigile].haSquadra():
                                zero_vars.append(self.var_festivi[curr_giorno][vigile])
                            pers_festivo.add(vigile)
                    candidati = self.var_festivi[curr_giorno]

                    # CONSTR: 3 vigili non aspiranti
                    self._add_constraint(f"constr_festivo({curr_giorno})_personale_non_aspirante",
                                  [x for v, x in candidati.items()
                                   if self.DB[v].grado not in ["Aspirante", "Allievo"]], 3, 3)

                    # CONSTR: almeno 1 autista per festivo
                    self._add_constraint(f"constr_festivo({curr_giorno})_autista",
                                  [x for v, x in candidati.items() if self.DB[v].autista], 1)

                    # CONSTR: dal 2027 se domenica (non festivo speciale) un graduato (vicecomandante, capo*)
                    if self._richiede_graduato(curr_giorno):
                        self._add_constraint(f"constr_festivo({curr_giorno})_graduato_domenica",
                                      [x for v, x in candidati.items() if self.DB[v].graduato_per_festivo()], 1)

            # CONSTR: max 1 notte per vigile a settimana
            # Max 2+ se fa notti extra o solo in alcuni giorni
            # Tutti i candidati ad almeno una notte della settimana (ordine deterministico)
            candidati_settimana = dict.fromkeys(v for i in giorni_settimana for v in self.var_notti[giorno + i])
            for vigile in candidati_settimana:
                max_notti_settimana = 1
                if self.DB[vigile].delta_notti > 0:
                    max_notti_settimana = 2
                lim_giorni = len([e for e in self.DB[vigile].eccezioni if "NoNottiGiorno" in e])
                lim_mesi = len([e for e in self.DB[vigile].eccezioni if "NoNottiMese" in e])
                if lim_mesi >= 8:
                    max_notti_settimana = 3
                elif (
                        "NottiSoloSabatoFestivi" in self.DB[vigile].eccezioni
                        or lim_giorni >= 4
                        or lim_mesi >= 4
                ):
                    max_notti_settimana = 2
                self._add_constraint(f"constr_notti_settimana({settimana})_vigile({vigile})",
                              [self._notte(giorno + i, vigile) for i in giorni_settimana], ub=max_notti_settimana)

            curr_squadra = (curr_squadra % num_squadre) + 1
            giorno += len(giorni_settimana)
            settimana += 1

        if args.partenza:
            self._carica_soluzione_di_partenza(args.partenza)
        else:
            # Suggerisci al solver una soluzione senza servizi fuori squadra
            for var in zero_vars:
                self.model.AddHint(var, 0)

        # Numero di notti, sabati e festivi
        logger.info(f"\tL'anno avrà {len(self.var_notti)} notti, {len(self.var_sabati)} sabati "
              f"e {len(self.var_festivi)} festivi.")

        sabati_extra_tot = sum([v.extra_sabati() for v in self.DB.values()])
        _NUM_PERS_SABATI = len(pers_sabato)
        _NUM_MEDIO_SABATI = (len(self.var_sabati) - sabati_extra_tot) / _NUM_PERS_SABATI
        _NUM_MIN_SABATI = math.floor(_NUM_MEDIO_SABATI)
        _NUM_MAX_SABATI = math.ceil(_NUM_MEDIO_SABATI)

        self._imponi_festivi_forzati()
        self._calcola_scambio_graduati(pers_festivo, _NUM_MEDIO_SABATI)

        notti_extra_tot = sum([v.extra_notti() for v in self.DB.values()])
        _NUM_PERS_NOTTI = len(pers_notte)
        _NUM_MEDIO_NOTTI = (len(self.var_notti) - notti_extra_tot) / _NUM_PERS_NOTTI
        _NUM_MIN_NOTTI = math.floor(_NUM_MEDIO_NOTTI)
        _NUM_MAX_NOTTI = math.ceil(_NUM_MEDIO_NOTTI)

        logger.info(f"\tCon {_NUM_PERS_NOTTI} vigili che svolgono notti ({notti_extra_tot:g} extra) "
              f"assegnerò {_NUM_MIN_NOTTI}-{_NUM_MAX_NOTTI} notti a testa.")

        logger.info(f"\tCon {_NUM_PERS_SABATI} vigili che svolgono sabati ({sabati_extra_tot} extra) "
              f"assegnerò {_NUM_MIN_SABATI}-{_NUM_MAX_SABATI} sabati a testa.")

        festivi_extra_tot = sum([v.extra_festivi() for v in self.DB.values()])
        _NUM_PERS_FESTIVI = len(pers_festivo)
        _NUM_MEDIO_FESTIVI = (len(self.var_festivi) * 3 - festivi_extra_tot) / _NUM_PERS_FESTIVI
        _NUM_MIN_FESTIVI = math.floor(_NUM_MEDIO_FESTIVI)
        _NUM_MAX_FESTIVI = math.ceil(_NUM_MEDIO_FESTIVI)

        logger.info(f"\tCon {_NUM_PERS_FESTIVI} vigili che svolgono festivi ({festivi_extra_tot:g} extra) "
              f"assegnerò {_NUM_MIN_FESTIVI}-{_NUM_MAX_FESTIVI} festivi a testa.")

        self._SERVIZI_MINIMI = _NUM_MIN_NOTTI + _NUM_MIN_SABATI + _NUM_MIN_FESTIVI

        logger.info("* Fase 2: aggiungo vincoli...")

        for vigile in self.DB:
            if self.DB[vigile].esente_servizi():
                continue
            v = self.DB[vigile]

            # CONSTR: numero notti
            if not v.esente_notti():
                self._add_constraint(f"constr_notti_totali({vigile})", self._tutti(self.var_notti, vigile),
                              _floor(_NUM_MEDIO_NOTTI + v.extra_notti()), _ceil(_NUM_MEDIO_NOTTI + v.extra_notti()))

            # CONSTR: numero sabati
            if not v.esente_sabati():
                self._add_constraint(f"constr_sabati_vigile({vigile})", self._tutti(self.var_sabati, vigile),
                              _floor(_NUM_MEDIO_SABATI + v.extra_sabati()),
                              _ceil(_NUM_MEDIO_SABATI + v.extra_sabati()))

            # CONSTR: numero festivi
            if not v.esente_festivi():
                self._add_constraint(f"constr_festivi_vigile({vigile})", self._tutti(self.var_festivi, vigile),
                              _floor(_NUM_MEDIO_FESTIVI + v.extra_festivi()),
                              _ceil(_NUM_MEDIO_FESTIVI + v.extra_festivi()))

            # CONSTR: max 1 tra venerdì notte, sabato e sabato notte + giovedì notte, domenica notte
            if not v.esente_sabati() and "NottiSoloSabatoFestivi" not in v.eccezioni:
                for sabato in self.var_sabati:
                    if vigile not in self.var_sabati[sabato]:
                        continue
                    self._add_constraint(f"constr_no_sabato_notte_consec_vigile({vigile})_sabato({sabato})",
                                  [self.var_sabati[sabato][vigile]]
                                  + [self._notte(sabato + d, vigile) for d in (0, -1, 1, -2)], ub=1)

            # CONSTR: max 1 tra sabato e festivi circostanti
            if not v.esente_sabati() and not v.esente_festivi():
                for sabato in self.var_sabati:
                    if vigile not in self.var_sabati[sabato]:
                        continue
                    self._add_constraint(f"constr_sabato_festivi_circostanti_vigile({vigile})_sabato({sabato})",
                                  [self.var_sabati[sabato][vigile]]
                                  + [self._festivo(sabato + d, vigile) for i in range(1, 8) for d in (-i, i)], ub=1)

            # CONSTR: max 1 tra festivo e notti circostanti + venerdì, lunedì
            if not v.esente_notti() and not v.esente_festivi():
                for festivo in self.var_festivi:
                    if (
                        ("NottiSoloSabatoFestivi" not in v.eccezioni
                         or self._get_weekday_from_offset(festivo) not in [5, 6])
                        and vigile in self.var_festivi[festivo]
                    ):
                        self._add_constraint(f"constr_no_festivo_notte_consec_vigile({vigile})_festivo({festivo})",
                                      [self.var_festivi[festivo][vigile]]
                                      + [self._notte(festivo + d, vigile) for d in (0, -1, -2, 1)], ub=1)

            # CONSTR: max 1 notte in 4 giorni consecutivi
            for notte in self.var_notti:
                if vigile in self.var_notti[notte]:
                    self._add_constraint(f"constr_notti_consec_vigile({vigile})_giorno({notte}-{notte + 3})",
                                  [self._notte(notte + d, vigile) for d in range(4)], ub=1)

            # CONSTR: no festivi in settimane adiacenti - mesi adiacenti per chi non ha richieste
            ha_richieste_speciali = any("NoFestiviMese" in e or "NoServiziMese" in e for e in v.eccezioni)
            distanza = 8 if ha_richieste_speciali else 30
            for festivo in self.var_festivi:
                next_festivi = [(festivo + i) for i in range(1, distanza) if festivo + i in self.var_festivi]
                if len(next_festivi) == 0 or vigile not in self.var_festivi[festivo]:
                    continue
                self._add_constraint(f"constr_festivi_consec_vigile({vigile})_giorno({festivo})",
                              [self.var_festivi[festivo][vigile]] + [self._festivo(f, vigile) for f in next_festivi],
                              ub=1)

            # CONSTR: max 1 servizio oneroso l'anno
            self._add_constraint(f"constr_servizi_onerosi_vigile({vigile})",
                          [self._festivo(f, vigile) for f in self.var_festivi if f in self._FESTIVI_ONEROSI]
                          + [self._notte(n, vigile) for n in self.var_notti if n in self._NOTTI_ONEROSE], ub=1)

            # ECCEZIONI alle regole usuali

            # CONSTR_EX: notti solo il sabato o festivi
            if "NottiSoloSabatoFestivi" in v.eccezioni:
                self._add_constraint(f"constr_ex_notti_solo_sabato_festivi_vigile({vigile})",
                              [self._notte(g, vigile) for g in self.var_notti
                               if self._get_weekday_from_offset(g) != 5 and g not in self.var_festivi], ub=0)

            # CONSTR_EX: no notti in specifici giorni della settimana
            giorni_da_saltare = [_GIORNO_TO_NUM[e[len("NoNottiGiorno"):]] for e in v.eccezioni
                                 if "NoNottiGiorno" in e]
            if len(giorni_da_saltare) > 0:
                self._add_constraint(f"constr_ex_no_notti_giornosettimana_vigile({vigile})",
                              [self._notte(g, vigile) for g in self.var_notti
                               if self._get_weekday_from_offset(g) in giorni_da_saltare], ub=0)

            # CONSTR_EX: no notti / sabati / festivi in specifici mesi
            for prefisso, collezione, nome in [("NoNottiMese", self.var_notti, "constr_ex_no_notti_mese_vigile"),
                                               ("NoSabatiMese", self.var_sabati, "constr_ex_no_sabati_mese_vigile"),
                                               ("NoFestiviMese", self.var_festivi, "constr_ex_no_festivi_mese_vigile")]:
                mesi_da_saltare = [int(e[len(prefisso):]) for e in v.eccezioni if prefisso in e]
                if len(mesi_da_saltare) > 0:
                    self._add_constraint(f"{nome}({vigile})",
                                  [collezione[g].get(vigile) for g in collezione
                                   if self._mese(g) in mesi_da_saltare], ub=0)

            # CONSTR_EX: no servizi specifico mese
            mesi_da_saltare = [int(e[len("NoServiziMese"):]) for e in v.eccezioni if "NoServiziMese" in e]
            if len(mesi_da_saltare) > 0:
                self._add_constraint(f"constr_ex_no_servizi_mese_vigile({vigile})",
                              [x for g in self.var_notti if self._mese(g) in mesi_da_saltare
                               for x in self._servizi_del_giorno(g, vigile)], ub=0)

            # CONSTR: no servizi il giorno di compleanno
            if not args.servizi_compleanno:
                compleanno = v.offset_compleanno(self.data_inizio)
                self._add_constraint(f"constr_compleanno_vigile({vigile})",
                              [self._notte(compleanno, vigile), self._sabato(compleanno, vigile),
                               self._festivo(compleanno, vigile)], ub=0)

            # Costo servizi per calcolo distribuzione equa
            self._aggiungi_costo_vigile(vigile)

        # CONSTR: numero servizi uguale per tutti +/- 1
        for vigile in self.DB:
            v = self.DB[vigile]
            if v.esente_servizi() or v.grado == "Aspirante":
                continue
            num_servizi_medi = 0
            if not v.esente_notti():
                num_servizi_medi += _NUM_MEDIO_NOTTI + v.extra_notti()
            if not v.esente_sabati():
                num_servizi_medi += _NUM_MEDIO_SABATI + v.extra_sabati()
            if not v.esente_festivi():
                num_servizi_medi += _NUM_MEDIO_FESTIVI + v.extra_festivi()
            self._add_constraint(f"constr_servizi_totali_vigile({vigile})",
                          self._tutti(self.var_notti, vigile) + self._tutti(self.var_sabati, vigile)
                          + self._tutti(self.var_festivi, vigile),
                          _floor(num_servizi_medi), _ceil(num_servizi_medi))

        # CONSTR: distribuisci servizi durante l'anno (max servizi per mese)
        for vigile in self.DB:
            v = self.DB[vigile]
            minimi = {
                "Notti": 0 if v.esente_notti() else _floor(_NUM_MEDIO_NOTTI + v.extra_notti()),
                "Sabati": 0 if v.esente_sabati() else _floor(_NUM_MEDIO_SABATI + v.extra_sabati()),
                "Festivi": 0 if v.esente_festivi() else _floor(_NUM_MEDIO_FESTIVI + v.extra_festivi()),
            }
            num_servizi_minimi = sum(minimi.values())
            num_servizi_per_mese = 0
            # Mesi "effettivi": ogni mese conta per la quota dei servizi del vigile che vi si possono svolgere
            # (e.g. un mese in cui può fare solo notti conta circa 0.6), così chi concentra i servizi in pochi
            # mesi con eccezioni NoNotti/NoSabati/NoFestiviMese ha un limite mensile proporzionalmente più alto
            num_mesi = 0
            if num_servizi_minimi > 0:
                for mese in range(1, 13 + 1):
                    if f"NoServiziMese{mese}" not in v.eccezioni:
                        num_mesi += sum(n for tipo, n in minimi.items()
                                        if f"No{tipo}Mese{mese}" not in v.eccezioni) / num_servizi_minimi
            if num_servizi_minimi > 0 and num_mesi > 0:
                num_servizi_per_mese = _ceil((num_servizi_minimi + 1) / num_mesi)
                num_servizi_per_mese = max(num_servizi_per_mese, 2)  # At least a couple...
            for mese in range(1, 13 + 1):
                self._add_constraint(f"constr_lim_servizi_vigile({vigile})_mese({mese})",
                              [x for g in self.var_notti if self._mese(g) == mese
                               for x in self._servizi_del_giorno(g, vigile)], ub=num_servizi_per_mese)

        proto = self.model.Proto()
        logger.info(f"\tIl modello ha {len(proto.variables)} variabili e {len(proto.constraints)} vincoli.")

        logger.info("* Fase 3: definisco l'obiettivo...")
        # OBJ: minimizza il costo totale dei servizi
        self.model.Minimize(sum(c * x for c, x in self._termini_costo))
        self.model.ExportToFile("model.txt")

    def _carica_soluzione_di_partenza(self, filename):
        """Suggerisce al solver la turnazione di un file turni_<anno>.csv (e.g. di un'esecuzione precedente):
        con gli stessi input il solver riparte da quella soluzione, e se era ottima la ritrova."""
        logger.info(f"\tLeggo la soluzione di partenza {filename}...")
        per_nome = {}
        for vigile, v in self.DB.items():
            if v.get_full_name() in per_nome:
                logger.error(f"due vigili si chiamano {v.get_full_name()}, impossibile leggere {filename}.")
                exit(-1)
            per_nome[v.get_full_name()] = vigile
        assegnati = set()
        ignorati = []
        with open(filename, newline='') as f:
            for riga in list(csv.reader(f, delimiter=';'))[1:]:
                if not riga or not riga[0].strip():
                    continue
                giorno = self._get_offset_from_date(dt.date.fromisoformat(riga[0].strip()))
                # Colonne: data, notte, 4 posti per sabato/festivo, poi gli affiancamenti (ignorati)
                for colonna, nome in enumerate(riga[1:6], start=1):
                    nome = nome.strip()
                    if not nome:
                        continue
                    var = None
                    if nome in per_nome:
                        vigile = per_nome[nome]
                        if colonna == 1:
                            var = self._notte(giorno, vigile)
                        elif self._sabato(giorno, vigile) is not None:
                            var = self._sabato(giorno, vigile)
                        else:
                            var = self._festivo(giorno, vigile)
                    if var is None:
                        ignorati.append(f"{riga[0]} {nome}")
                    else:
                        assegnati.add(var.Index())
        for collezione in (self.var_notti, self.var_sabati, self.var_festivi):
            for d in collezione.values():
                for var in d.values():
                    self.model.AddHint(var, 1 if var.Index() in assegnati else 0)
        logger.info(f"\tSoluzione di partenza: {len(assegnati)} servizi suggeriti, {len(ignorati)} ignorati.")
        if ignorati:
            logger.warning(f"servizi non applicabili (vigile sconosciuto o non candidato): "
                  + ", ".join(ignorati[:10]) + (" ..." if len(ignorati) > 10 else ""))

    def _aggiungi_costo_vigile(self, vigile):
        """Aggiunge all'obiettivo il costo dei servizi del vigile. Costo totale = somma dei coefficienti dei
        servizi assegnati - costo dei servizi extra (Delta e scambi), che non contano ai fini dell'equità."""
        v = self.DB[vigile]
        self._costo_costante += (v.extra_notti() * _MUL_NOTTI + v.extra_sabati() * _MUL_SABATI
                                 + v.extra_festivi() * _MUL_FESTIVI)
        mul_sabati = 1 + sum(v.passato_sabati)  # Sabati più probabili se pochi in anni recenti
        compleanno = v.offset_compleanno(self.data_inizio)
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
                pen_festivi_onerosi = 2 + sum(v.passato_festivi_onerosi)
            if not (self.giorno_squadra[giorno] in v.squadre or 0 in v.squadre):
                mul_squadra = 2  # Servizi NON di squadra costano di più
            if self._sabato(giorno, vigile) is not None:
                self._costo(_MUL_SABATI * mul_bday * mul_squadra ** 2 * mul_sabati, self.var_sabati[giorno][vigile])
            if self._festivo(giorno, vigile) is not None:
                mul_squadra_festivo = 1
                # Se lunedì è squadra precedente
                if not (self.giorno_squadra_festivo[giorno] in v.squadre or 0 in v.squadre):
                    mul_squadra_festivo = 2  # Servizi NON di squadra costano di più
                if v.grado == "Aspirante":
                    self._costo(mul_bday * mul_squadra_festivo ** 2 - 1, self.var_festivi[giorno][vigile])
                else:
                    # Base 1.5 per incoraggiare massima equità
                    self._costo(_MUL_FESTIVI * mul_bday * mul_squadra_festivo ** 2 + pen_festivi_onerosi,
                                self.var_festivi[giorno][vigile])
            if self._notte(giorno, vigile) is not None:
                if giorno == self._NOTTE_CAPODANNO:
                    self._costo(1 * mul_bday + 100 * v.passato_capodanni, self.var_notti[giorno][vigile])
                else:
                    if mul_squadra > 1 and (v.delta_notti > 0 or "NottiAncheFuoriSettimana" in v.eccezioni):
                        mul_squadra = 1.5  # con notti in più paga meno a metterle fuori settimana
                    self._costo(_MUL_NOTTI * mul_bday * mul_squadra + pen_notti_onerose,
                                self.var_notti[giorno][vigile])

    def _costo(self, coefficiente, var):
        scalato = coefficiente * _SCALA_COSTI
        if scalato != int(scalato):
            raise ValueError(f"Coefficiente di costo {coefficiente} non multiplo di 1/{_SCALA_COSTI}")
        if scalato != 0:
            self._termini_costo.append((int(scalato), var))

    def costo_totale(self):
        """Costo totale dei servizi della soluzione trovata (nella stessa scala dei coefficienti)."""
        return self._costo_di(self.cp_solver)

    def _costo_di(self, solver):
        return solver.ObjectiveValue() / _SCALA_COSTI - self._costo_costante

    # Accesso alle variabili: None se il vigile non è candidato per quel servizio
    def _notte(self, giorno, vigile):
        return self.var_notti.get(giorno, {}).get(vigile)

    def _sabato(self, giorno, vigile):
        return self.var_sabati.get(giorno, {}).get(vigile)

    def _festivo(self, giorno, vigile):
        return self.var_festivi.get(giorno, {}).get(vigile)

    @staticmethod
    def _tutti(collezione, vigile):
        return [d[vigile] for d in collezione.values() if vigile in d]

    def _servizi_del_giorno(self, giorno, vigile):
        """Notte, sabato o festivo del giorno (i festivi non contano per chi ha FestiviComunque)."""
        servizi = [self._notte(giorno, vigile)]
        if self._sabato(giorno, vigile) is not None:
            servizi.append(self._sabato(giorno, vigile))
        elif "FestiviComunque" not in self.DB[vigile].eccezioni:
            servizi.append(self._festivo(giorno, vigile))
        return [x for x in servizi if x is not None]

    def _mese(self, giorno):
        """Mese del giorno, contando 13 per il gennaio dell'anno successivo."""
        data = self._get_date_from_offset(giorno)
        return data.month + (data.year - self.anno) * 12

    # ------------------------------------------------------------------------------------------------------------
    # Soluzione
    # ------------------------------------------------------------------------------------------------------------

    def _solve(self):
        # Con una soluzione di partenza, valutala prima (tutte le variabili fissate ai valori suggeriti)
        partenza = None
        if self.args.partenza:
            partenza = cp_model.CpSolver()
            partenza.parameters.num_workers = self.args.jobs
            partenza.parameters.fix_variables_to_their_hinted_value = True
            if partenza.Solve(self.model) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                logger.info(f"\tLa soluzione di partenza è valida, con costo {self._costo_di(partenza):g}.")
            else:
                logger.warning("la soluzione di partenza non rispetta i vincoli attuali, la uso solo come spunto.")
                partenza = None

        solver = cp_model.CpSolver()
        p = solver.parameters
        p.num_workers = self.args.jobs
        p.relative_gap_limit = 0.00001
        if self.args.time_limit > 0:
            p.max_time_in_seconds = self.args.time_limit
        if self.args.verbose:
            # Log del solver attraverso logging (quindi anche sul file di log, se richiesto)
            p.log_search_progress = True
            p.log_to_stdout = False
            solver.log_callback = logger.info
        self.cp_solver = solver
        self.STATUS = solver.Solve(self.model)

        # A parità di costo tieni la soluzione di partenza, così da riprodurla esattamente
        if partenza is not None and self.STATUS in (cp_model.OPTIMAL, cp_model.FEASIBLE) \
                and solver.ObjectiveValue() >= partenza.ObjectiveValue():
            logger.info("\tNessuna soluzione migliore di quella di partenza: la mantengo.")
            self.cp_solver = partenza
        return self.STATUS

    def solve(self):
        logger.info("* Risolvo il modello... (max {}s)".format(self.args.time_limit if self.args.time_limit > 0 else "∞"))
        self._solve()
        self.print_solution()
        self.save_solution()

    def _val(self, var):
        return self.cp_solver.Value(var)

    def print_solution(self):
        if self.STATUS == cp_model.UNKNOWN:
            logger.warning('non sono riuscito a calcolare una soluzione nel tempo concessomi.')
            logger.info("\tDammi più tempo e riprova.")
            exit(1)
        elif self.STATUS == cp_model.INFEASIBLE:
            logger.warning('Il problema non ammette soluzione.')
            self.analizza_infeasibilita()
            logger.info('\tRilassa i vincoli e riprova.')
            exit(1)
        elif self.STATUS not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            logger.error(f'il solver ha terminato con stato inatteso {self.cp_solver.StatusName(self.STATUS)}.')
            exit(1)
        if self.STATUS == cp_model.FEASIBLE:
            logger.warning("la soluzione trovata potrebbe non essere ottimale.")
        servizi_fuori_squadra = 0
        capodanno = "NON CALCOLATO"
        logger.info('* Soluzione:')
        logger.info(f'Costo totale dei servizi: {self.costo_totale():g}')
        srv_lines = []
        for vigile in self.DB:
            v = self.DB[vigile]
            for giorno in self.var_notti:
                if vigile in self.var_notti[giorno] and self._val(self.var_notti[giorno][vigile]):
                    v.notti += 1
                    if giorno == self._NOTTE_CAPODANNO:
                        v.capodanno += 1
                        capodanno = f"{v.nome} {v.cognome} ({v.passato_capodanni} precedenti)"
                    if self.giorno_squadra[giorno] not in v.squadre and v.haSquadra():
                        v.notti_fuori_squadra += 1
                        servizi_fuori_squadra += 1
            for giorno in self.var_sabati:
                if vigile in self.var_sabati[giorno] and self._val(self.var_sabati[giorno][vigile]):
                    v.sabati += 1
                    if self.giorno_squadra[giorno] not in v.squadre and v.haSquadra():
                        v.sabati_fuori_squadra += 1
                        servizi_fuori_squadra += 1
            for giorno in self.var_festivi:
                if vigile in self.var_festivi[giorno] and self._val(self.var_festivi[giorno][vigile]):
                    v.festivi += 1
                    if giorno in self._FESTIVI_ONEROSI:
                        v.festivi_onerosi += 1
                    if self.giorno_squadra_festivo[giorno] not in v.squadre and v.haSquadra():
                        v.festivi_fuori_squadra += 1
                        servizi_fuori_squadra += 1
            line = str(v)
            line += f": {v.notti + v.sabati + v.festivi}"
            line += f"\n\tNotti: {v.notti} ({v.notti_fuori_squadra})"
            if v.delta_notti != 0:
                line += f" [Delta: {v.delta_notti}]"
            if v.scambio_notti != 0:
                line += f" [Scambio: {v.scambio_notti:+.3g}]"
            line += f"\n\tSabati: {v.sabati} ({v.sabati_fuori_squadra})"
            if v.delta_sabati != 0:
                line += f" [Delta: {v.delta_sabati}]"
            line += f"\n\tFestivi: {v.festivi} ({v.festivi_fuori_squadra})"
            if v.delta_festivi != 0:
                line += f" [Delta: {v.delta_festivi}]"
            if v.scambio_festivi != 0:
                line += f" [Scambio: {v.scambio_festivi:+.3g}]"
            if v.cede_sabati:
                line += " [Sabati ceduti]"
            if len(v.eccezioni) > 0:
                line += f"\n\tEccezioni: {v.eccezioni}"
            srv_lines.append(line)
        logger.info('Servizi per vigile:\n' + '\n'.join(srv_lines))
        logger.info(f"Totale servizi assegnati fuori dalla squadra: {servizi_fuori_squadra}")
        logger.info(f"Vigile designato per la notte di capodanno: {capodanno}")

    def save_solution(self):
        logger.info("Salvo la soluzione trovata...")
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
            for tipo, collezione in [('notte', self.var_notti), ('sabato', self.var_sabati),
                                     ('festivo', self.var_festivi)]:
                for vigile, var in collezione.get(giorno, {}).items():
                    if self._val(var):
                        self.solution[giorno][tipo].append(vigile)
                        self.servizi_per_vigile[vigile].append(f"{data.strftime('%d/%m/%Y')} {tipo}")

    # ------------------------------------------------------------------------------------------------------------
    # Diagnostica: insieme irriducibile di vincoli incompatibili (IIS)
    # ------------------------------------------------------------------------------------------------------------

    def analizza_infeasibilita(self, tempo_max=None, tempo_prova=60):
        """Cerca un insieme irriducibile di vincoli incompatibili (IIS): vincoli che insieme non ammettono
        soluzione, ma tali che rimuovendone uno qualsiasi il resto è risolvibile.
        Prima riduce le famiglie di vincoli (e.g. tutti i "numero di festivi del vigile"), poi i singoli vincoli
        delle famiglie rimaste, rimuovendo blocchi sempre più piccoli finché il modello resta irrisolvibile."""
        if tempo_max is None:
            tempo_max = self.args.time_limit if self.args.time_limit > 0 else 600
        logger.info(f"* Cerco un insieme minimo di vincoli incompatibili (max {tempo_max}s)...")
        t0 = time.time()
        base = self.model.Proto()
        incerti = set()  # Vincoli tenuti perché la prova senza di loro non ha dato risposta nel tempo
        stato_ricerca = {'completa': True}

        def irrisolvibile(attivi):
            modello = cp_model.CpModel()
            proto = modello.Proto()
            proto.copy_from(base)
            proto.clear_objective()
            proto.constraints.clear()
            proto.constraints.extend(base.constraints[i] for i in sorted(attivi))
            solver = cp_model.CpSolver()
            solver.parameters.num_workers = self.args.jobs
            solver.parameters.max_time_in_seconds = max(1.0, min(tempo_prova, tempo_max - (time.time() - t0)))
            stato = solver.Solve(modello)
            return stato == cp_model.INFEASIBLE, stato == cp_model.UNKNOWN

        def riduci(gruppi, altri):
            """Restituisce i gruppi (liste di indici di vincoli) indispensabili, dato che i vincoli `altri`
            restano sempre attivi."""
            attivi = list(range(len(gruppi)))
            coda = [list(attivi)]
            while coda:
                if time.time() - t0 > tempo_max:
                    stato_ricerca['completa'] = False
                    break
                blocco = coda.pop(0)
                da_togliere = set(blocco)
                resto = [g for g in attivi if g not in da_togliere]
                infeasible, ignoto = irrisolvibile(altri + [i for g in resto for i in gruppi[g]])
                if infeasible:
                    attivi = resto  # Il blocco non serve
                elif len(blocco) > 1:
                    coda += [blocco[:len(blocco) // 2], blocco[len(blocco) // 2:]]
                elif ignoto:
                    incerti.update(gruppi[blocco[0]])
            return [gruppi[g] for g in attivi]

        famiglie = {}
        for i, c in enumerate(base.constraints):
            famiglie.setdefault(c.name.split('(')[0], []).append(i)
        famiglie = riduci(list(famiglie.values()), [])
        logger.info(f"\tFamiglie di vincoli coinvolte ({time.time() - t0:.0f}s): "
              + ", ".join(sorted(base.constraints[f[0]].name.split('(')[0] for f in famiglie)))

        # Riduci ogni famiglia ai singoli vincoli, tenendo attive le altre
        ridotte = []
        for k, famiglia in enumerate(famiglie):
            altri = [i for f in ridotte for i in f] + [i for f in famiglie[k + 1:] for i in f]
            ridotte.append([g[0] for g in riduci([[i] for i in famiglia], altri)])
        iis = sorted(((base.constraints[i].name, i) for f in ridotte for i in f),
                     key=lambda x: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', x[0])])

        logger.info(f"\tInsieme di {len(iis)} vincoli incompatibili ({time.time() - t0:.0f}s):")
        for nome, i in iis:
            logger.info(f"\t- {self._descrivi_vincolo(nome)}" + (" (non verificato)" if i in incerti else ""))
        if not stato_ricerca['completa'] or incerti:
            logger.warning("tempo insufficiente, l'insieme è incompatibile ma potrebbe non essere minimo: "
                  "aumenta il tempo con -t.")

    def _descrivi_vincolo(self, nome):
        """Rende leggibile il nome di un vincolo: date al posto degli offset, nomi al posto degli ID."""
        def data(g):
            d = self._get_date_from_offset(int(g))
            return f"{_NOMI_GIORNI[d.weekday()]} {d.strftime('%d/%m/%Y')}"

        nome = re.sub(r'vigile\((\d+)\)',
                      lambda m: f"vigile({self.DB[int(m[1])].get_full_name() if int(m[1]) in self.DB else m[1]})",
                      nome)
        nome = re.sub(r'(notte|sabato|festivo|giorno)\((\d+)-(\d+)\)',
                      lambda m: f"{m[1]}({data(m[2])} - {data(m[3])})", nome)
        nome = re.sub(r'(notte|sabato|festivo|giorno)\((\d+)\)', lambda m: f"{m[1]}({data(m[2])})", nome)
        nome = re.sub(r'settimana\((\d+)\)', lambda m: f"settimana({data(int(m[1]) * 7)})", nome)
        famiglia = nome.split('(')[0]
        return f"{nome}  [{_DESCRIZIONE_VINCOLI[famiglia]}]" if famiglia in _DESCRIZIONE_VINCOLI else nome

    # ------------------------------------------------------------------------------------------------------------
    # Calendario e regole speciali
    # ------------------------------------------------------------------------------------------------------------

    def _compute_servizi_speciali_onerosi(self):
        pasqua = _calc_easter(self.anno)
        logger.info(f"\tPasqua cade il {pasqua}.")
        anno = self.anno
        festivi_speciali = [
            dt.date(anno, 1, 6),  # Epifania
            pasqua,  # Pasqua
            pasqua + dt.timedelta(days=1),  # Pasquetta
            dt.date(anno, 4, 25),  # 25 Aprile
            dt.date(anno, 5, 1),  # 1 Maggio
            dt.date(anno, 6, 2),  # 2 Giugno
            dt.date(anno, 8, 15),  # Ferragosto
            dt.date(anno, 10, 4),  # 4 Ottobre
            dt.date(anno, 11, 1),  # 1 Novembre
            dt.date(anno, 12, 8),  # 8 Dicembre
            dt.date(anno, 12, 25),  # Natale
            dt.date(anno, 12, 26),  # S. Stefano
            dt.date(anno + 1, 1, 1),  # 1 Gennaio
            dt.date(anno + 1, 1, 6),  # Epifania
        ]
        notti_onerose = [
            dt.date(anno, 12, 24),  # Natale
            dt.date(anno, 12, 25),  # Natale
            dt.date(anno, 12, 31),  # Capodanno
        ]
        # Onerosi solo se festivi (i.e. 24 e 31 dicembre solo se cadono di domenica)
        festivi_onerosi = [
            pasqua,  # Pasqua
            pasqua + dt.timedelta(days=1),  # Pasquetta
            dt.date(anno, 6, 2),  # 2 Giugno
            dt.date(anno, 8, 15),  # Ferragosto
            dt.date(anno, 12, 24),  # Vigilia di Natale
            dt.date(anno, 12, 25),  # Natale
            dt.date(anno, 12, 26),  # S. Stefano
            dt.date(anno, 12, 31),  # 31 Dicembre
            dt.date(anno + 1, 1, 1),  # 1 Gennaio
        ]
        self._FESTIVI_SPECIALI = list(map(self._get_offset_from_date, festivi_speciali))
        self._NOTTI_ONEROSE = list(map(self._get_offset_from_date, notti_onerose))
        self._NOTTE_CAPODANNO = self._get_offset_from_date(dt.date(anno, 12, 31))
        self._FESTIVI_ONEROSI = list(map(self._get_offset_from_date, festivi_onerosi))

    def _calcola_scambio_graduati(self, pers_festivo, medio_sabati):
        """Dal 2027 ogni domenica non festiva richiede un graduato (vedi graduato_per_festivo).
        I graduati che coprono le domeniche non fanno sabati: ricevono in cambio tanti festivi quanti sabati
        avrebbero fatto in media (più eventuali DeltaSabati), così il numero totale di servizi resta equo.
        Se nemmeno così bastano a coprire tutte le domeniche, scambiano anche k notti con k festivi (k minimo)."""
        domeniche = sum(1 for g in self.var_festivi if self._richiede_graduato(g))
        graduati = [self.DB[v] for v in pers_festivo if self.DB[v].graduato_per_festivo()]
        if domeniche == 0 or len(graduati) == 0:
            return
        for v in graduati:
            if v.cede_sabati:
                v.scambio_festivi = medio_sabati + v.delta_sabati
        # Può scambiare notti solo chi le fa
        scambiabili = [v for v in graduati if not v.esente_notti()]
        posti_festivi = len(self.var_festivi) * 3
        extra_festivi_tot = sum(v.extra_festivi() for v in self.DB.values())

        for k in range(0, 53):
            medio = (posti_festivi - extra_festivi_tot - k * len(scambiabili)) / len(pers_festivo)
            capacita = sum(_ceil(medio + v.extra_festivi() + (k if v in scambiabili else 0)) for v in graduati)
            if capacita >= domeniche:
                break
        else:
            logger.warning(f"{len(graduati)} graduati non bastano a coprire {domeniche} domeniche "
                  f"nemmeno scambiando festivi e notti.")
            return
        for v in scambiabili:
            v.scambio_festivi += k
            v.scambio_notti = -k
        ceduti = sum(v.cede_sabati for v in graduati)
        logger.info(f"\t{len(graduati)} graduati per {domeniche} domeniche (capacità {capacita}): "
              f"{ceduti} cedono i sabati per {medio_sabati:.2f} festivi in più"
              + (f", {len(scambiabili)} scambiano anche {k} notti con {k} festivi." if k > 0 else "."))

    def _imponi_festivi_forzati(self):
        """FestivoForzatoAAAAMMGG: il vigile deve essere assegnato al festivo indicato."""
        for vigile, v in self.DB.items():
            for data in v.festivi_forzati:
                giorno = self._get_offset_from_date(data)
                if giorno not in self.var_festivi:
                    logger.error(f"il {data} (FestivoForzato del vigile {v}) non è un festivo del periodo!")
                    exit(-1)
                if vigile not in self.var_festivi[giorno]:
                    logger.error(f"il vigile {v} non può essere assegnato al festivo forzato del {data} "
                          f"(esenzioni o altre eccezioni lo escludono).")
                    exit(-1)
                self._add_constraint(f"constr_ex_festivo_forzato_vigile({vigile})_giorno({giorno})",
                              [self.var_festivi[giorno][vigile]], 1, 1)

    def _richiede_graduato(self, giorno):
        """Dal 2027 le domeniche che non sono anche festivi speciali (e.g. Pasqua) richiedono un graduato."""
        return self._get_weekday_from_offset(giorno) == 6 and giorno not in self._FESTIVI_SPECIALI

    def _get_date_from_offset(self, offset):
        return self.data_inizio + dt.timedelta(offset)

    def _get_weekday_from_offset(self, offset):
        return self._get_date_from_offset(offset).weekday()

    def _get_offset_from_date(self, date):
        return (date - self.data_inizio).days


def _floor(x):
    """floor tollerante agli errori di arrotondamento (e.g. 6.9999999 -> 7)"""
    return math.floor(x + 1e-9)


def _ceil(x):
    """ceil tollerante agli errori di arrotondamento (e.g. 7.0000001 -> 7)"""
    return math.ceil(x - 1e-9)


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

_NOMI_GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

_DESCRIZIONE_VINCOLI = {
    "constr_notte": "esattamente 1 vigile per notte",
    "constr_sabato": "esattamente 1 vigile per sabato",
    "constr_festivo": "composizione del festivo",
    "constr_notti_settimana": "max notti a settimana",
    "constr_notti_totali": "numero di notti del vigile",
    "constr_sabati_vigile": "numero di sabati del vigile",
    "constr_festivi_vigile": "numero di festivi del vigile",
    "constr_no_sabato_notte_consec_vigile": "max 1 tra sabato e notti da giovedì a domenica",
    "constr_sabato_festivi_circostanti_vigile": "max 1 tra sabato e festivi entro 7 giorni",
    "constr_no_festivo_notte_consec_vigile": "max 1 tra festivo e notti circostanti",
    "constr_notti_consec_vigile": "max 1 notte in 4 giorni",
    "constr_festivi_consec_vigile": "distanza minima tra festivi",
    "constr_servizi_onerosi_vigile": "max 1 servizio oneroso l'anno",
    "constr_servizi_totali_vigile": "numero totale di servizi (media +/- 1)",
    "constr_lim_servizi_vigile": "max servizi al mese",
    "constr_compleanno_vigile": "nessun servizio al compleanno",
    "constr_ex_festivo_forzato_vigile": "eccezione FestivoForzato",
    "constr_ex_notti_solo_sabato_festivi_vigile": "eccezione NottiSoloSabatoFestivi",
    "constr_ex_no_notti_giornosettimana_vigile": "eccezione NoNottiGiorno",
    "constr_ex_no_notti_mese_vigile": "eccezione NoNottiMese",
    "constr_ex_no_sabati_mese_vigile": "eccezione NoSabatiMese",
    "constr_ex_no_festivi_mese_vigile": "eccezione NoFestiviMese",
    "constr_ex_no_servizi_mese_vigile": "eccezione NoServiziMese",
}
