from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import math
import vvf_io

_NUM_MIN_FESTIVI = 5 #0
_NUM_MAX_FESTIVI = 6 #5
_SPAZIATORE_FESTIVI = 4 #5

class TurnazioneVVF:
	#Collections
	giorno_squadra = {}

	var_notti = {}
	constr_notti = {}
	constr_notti_settimana_vigile = {}
	constr_notti_consecutive_vigile = {}

	var_sabati = {}
	constr_sabati = {}
	constr_sabati_vigile = {}
	constr_sabati_notti_circostanti_vigile = {}

	var_festivi_gruppo = {}
	var_festivi_vigile = {}
	constr_festivi = {}
	constr_festivi_vigili_gruppo = {}
	constr_festivi_vigile = {}
	constr_festivi_notti_circostanti_vigile = {}
	constr_sabato_festivi_circostanti_vigile = {}
	constr_festivi_spaziati = {}
	
	constr_servizi_onerosi_vigile = {}
	constr_compleanno_vigile = {}

	var_servizi_vigile = {}
	constr_servizi_vigile = {}
	var_cost_servizi_vigile = {}
	constr_cost_servizi_vigile = {}
	var_differenza_servizi = {}
	constr_differenza_servizi = {}

	constr_notti_non_standard = {}

	constr_ex_limite_notti = {}
	constr_ex_sabati_minimi_esenti_CP = {}
	constr_ex_notti_solo_sabato_festivi = {}
	constr_ex_no_notti_giornosettimana = {}
	constr_ex_no_notti_mese = {}
	constr_ex_no_servizi_mese = {}
	constr_ex_aspettativa = {}
	constr_ex_extra_festivi = {}

	DB = {}
	vigili = []
	vigili_squadra = {}
	vigili_gruppi_festivo = {}
	anno = 0
	data_inizio = 0
	data_fine = 0
	num_medio_notti = -1
	_printed_solution = False
	_FESTIVI_SPECIALI = []
	_FESTIVI_ONEROSI = []
	_NOTTI_ONEROSE = []

	#Model
	solver = pywraplp.Solver('Turnazione_VVF', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
	STATUS = -1

	def _computeServiziSpecialiOnerosi(self):
		pasqua = _calc_easter(self.anno)
		print("* Pasqua cade il {}.".format(pasqua))
		self._FESTIVI_SPECIALI = [
			dt.date(self.anno,1,6),		#Epifania
			pasqua,						#Pasqua
			pasqua + dt.timedelta(1),	#Pasquetta
			dt.date(self.anno,4,25),	#25 Aprile
			dt.date(self.anno,5,1),		#1 Maggio
			dt.date(self.anno,6,2),		#2 Giugno
			dt.date(self.anno,8,15),	#Ferragosto
			dt.date(self.anno,11,1),	#1 Novembre
			dt.date(self.anno,12,8),	#8 Dicembre
			dt.date(self.anno,12,25),	#Natale
			dt.date(self.anno,12,26),	#S. Stefano
			dt.date(self.anno+1,1,1),	#1 Gennaio
			dt.date(self.anno+1,1,6),	#Epifania
			]
		self._NOTTI_ONEROSE = [
			dt.date(self.anno,12,24),	#Natale
			dt.date(self.anno,12,25),	#Natale
			dt.date(self.anno,12,31),	#Capodanno
			]
		self._FESTIVI_SPECIALI = list(map(self._getOffsetFromDate, self._FESTIVI_SPECIALI))
		self._NOTTI_ONEROSE = list(map(self._getOffsetFromDate, self._NOTTI_ONEROSE))
		self._FESTIVI_ONEROSI = [
			self._FESTIVI_SPECIALI[1], #Pasqua
			self._FESTIVI_SPECIALI[6], #Ferragosto
			self._FESTIVI_SPECIALI[9], #Natale
			self._FESTIVI_SPECIALI[11], #1 Gennaio
			]

	def __init__(self, args):
		print("Creo il modello...")
		self.data_inizio = args.data_di_inizio
		self.data_fine = args.data_di_fine
		self.anno = self.data_inizio.year
		if self.data_inizio.weekday() != 4:
			print("ERRORE: il giorno di inizio non è un venerdì!")
			exit(-1)
		elif self.data_fine.weekday() != 4:
			print("ERRORE: il giorno di fine non è un venerdì!")
			exit(-1)
		if (self.data_fine - self.data_inizio).days > 400:
			print("ERRORE: il periodo dal {} al {} è troppo lungo, sicuri sia giusto?".format(self.data_inizio, self.data_fine))
			exit(-1)
		elif (self.data_fine - self.data_inizio).days < 350:
			print("ERRORE: il periodo dal {} al {} è troppo lungo, sicuri sia giusto?".format(self.data_inizio, self.data_fine))
			exit(-1)
		loose = args.loose
		servizi_compleanno = args.servizi_compleanno
		num_medio_notti = args.media_notti_festivi[0]
		self._computeServiziSpecialiOnerosi()
		self.DB = vvf_io.read_csv_vigili(args.organico_fn)
		self.DB = vvf_io.read_csv_riporti(self.DB, args.riporti_fn)
		self.DB = vvf_io.correggi_aspiranti(self.DB, self.data_inizio, self.data_fine)
		self.DB = vvf_io.calcola_coefficienti(self.DB)
		self.vigili = list(self.DB.keys())
		self.vigili_squadra = {}
		self.vigili_gruppi_festivo = {}
		for vigile in self.vigili:
			# Squadra
			for squadra in self.DB[vigile].squadre:
				if squadra == 0:
					continue
				elif squadra not in self.vigili_squadra.keys():
					self.vigili_squadra[squadra] = []
				self.vigili_squadra[squadra].append(vigile)
			# Gruppo Festivo
			if self.DB[vigile].gruppo_festivo == 0:
				continue
			elif self.DB[vigile].gruppo_festivo not in self.vigili_gruppi_festivo.keys():
				self.vigili_gruppi_festivo[self.DB[vigile].gruppo_festivo] = []
			self.vigili_gruppi_festivo[self.DB[vigile].gruppo_festivo].append(vigile)

		num_squadre = len(self.vigili_squadra.keys())
		num_giorni = self._getOffsetFromDate(self.data_fine)
		giorno = 0
		curr_squadra = args.squadra_di_partenza
		if curr_squadra not in self.vigili_squadra.keys():
			print ("ERRORE: squadra iniziale {} inesistente!".format(curr_squadra))
			exit(-1)

		### FASE 1 ###
		print("* Fase 1: creo possibilità...")

		while giorno < num_giorni:
			for i in range(7):
				curr_giorno = giorno + i
				curr_data = self._getDateFromOffset(curr_giorno)
				
				self.giorno_squadra[curr_giorno] = curr_squadra

				#VAR: vigili di squadra candidati per la notte
				self.var_notti[curr_giorno] = {}
				for vigile in self.vigili:
					if (not self.DB[vigile].EsenteNotti()
						and (curr_squadra in self.DB[vigile].squadre
						or 0 in self.DB[vigile].squadre
						or curr_data == dt.date(self.anno,12,31) # Tutti candidati per capodanno
						or "NottiAncheFuoriSettimana" in self.DB[vigile].eccezioni
						or loose)
						):
						self.var_notti[curr_giorno][vigile] = self.solver.IntVar(0, 1, "var_vigile({})_notte({})".format(vigile, curr_giorno))
					
				#CONSTR: 1 vigile per notte
				self.constr_notti[curr_giorno] = self.solver.Constraint(1, 1, "constr_notte({})".format(curr_giorno))
				for var in self.var_notti[curr_giorno].values():
					self.constr_notti[curr_giorno].SetCoefficient(var, 1)

				#SABATO
				if curr_data.weekday() == 5 and curr_giorno not in self._FESTIVI_SPECIALI:

					#VAR: vigile candidati per il sabato
					self.var_sabati[curr_giorno] = {}
					for vigile in self.vigili:
						if not self.DB[vigile].EsenteSabati():
							self.var_sabati[curr_giorno][vigile] = self.solver.IntVar(0, 1, "var_vigile({})_sabato({})".format(vigile, curr_giorno))

					#CONSTR: 1 vigile per sabato
					self.constr_sabati[curr_giorno] = self.solver.Constraint(1, 1, "constr_sabato({})".format(curr_giorno))
					for vigile in self.vigili:
						if vigile in self.var_sabati[curr_giorno].keys():
							self.constr_sabati[curr_giorno].SetCoefficient(self.var_sabati[curr_giorno][vigile], 1)

				#FESTIVO
				if curr_data.weekday() == 6 or curr_giorno in self._FESTIVI_SPECIALI:
					
					#VAR: vigili candidati per il festivo
					self.var_festivi_gruppo[curr_giorno] = {}
					for gruppo in self.vigili_gruppi_festivo.keys():
						self.var_festivi_gruppo[curr_giorno][gruppo] = self.solver.IntVar(0, 1, "var_gruppo({})_festivo({})".format(gruppo, curr_giorno))
					self.var_festivi_vigile[curr_giorno] = {}
					for vigile in self.vigili:
						if not self.DB[vigile].EsenteFestivi():
							self.var_festivi_vigile[curr_giorno][vigile] = self.solver.IntVar(0, 1, "var_vigile({})_festivo({})".format(vigile, curr_giorno))
						
					#CONSTR: 1 gruppo festivo a festivo
					self.constr_festivi[curr_giorno] = self.solver.Constraint(1, 1, "constr_festivo({})".format(curr_giorno))
					for gruppo in self.vigili_gruppi_festivo.keys():
						self.constr_festivi[curr_giorno].SetCoefficient(self.var_festivi_gruppo[curr_giorno][gruppo], 1)
						
					#CONSTR: gruppo coiimplica vigile
					self.constr_festivi_vigili_gruppo[curr_giorno] = {}
					for gruppo in self.vigili_gruppi_festivo.keys():
						self.constr_festivi_vigili_gruppo[curr_giorno][gruppo] = self.solver.Constraint(0, 0, "constr_festivo_vigili_gruppo({})_festivo({})".format(gruppo, curr_giorno))
						self.constr_festivi_vigili_gruppo[curr_giorno][gruppo].SetCoefficient(self.var_festivi_gruppo[curr_giorno][gruppo], -1*len(self.vigili_gruppi_festivo[gruppo]))
						for vigile in self.vigili_gruppi_festivo[gruppo]:
							self.constr_festivi_vigili_gruppo[curr_giorno][gruppo].SetCoefficient(self.var_festivi_vigile[curr_giorno][vigile], 1)
					
			#CONSTR: max 1 notte per vigile a settimana
			settimana = int(giorno / 7)
			self.constr_notti_settimana_vigile[settimana] = {}
			for vigile in self.var_notti[curr_giorno].keys():
				max_notti_settimana = 1
				#Max 2 notti a settimana se esente CP o fa notti solo in alcuni giorni
				lim_giorni = len([e for e in self.DB[vigile].eccezioni if "NoNottiGiorno" in e])
				lim_mesi = len([e for e in self.DB[vigile].eccezioni if "NoNottiMese" in e])
				if (
					self.DB[vigile].esenteCP()
					or "NottiSoloSabatoFestivi" in self.DB[vigile].eccezioni
					or lim_giorni >= 4
					or lim_mesi >= 4
					):
					max_notti_settimana = 2
				elif lim_mesi >= 8:
					max_notti_settimana = 3
				self.constr_notti_settimana_vigile[settimana][vigile] = self.solver.Constraint(-self.solver.infinity(), max_notti_settimana, "constr_notti_settimana({})_vigile({})".format(settimana, vigile))
				for i in range(7):
					self.constr_notti_settimana_vigile[settimana][vigile].SetCoefficient(self.var_notti[giorno + i][vigile], 1)

			curr_squadra = (curr_squadra % num_squadre) + 1
			giorno += 7

		### FASE 2###
		print("* Fase 2: aggiungo vincoli...")

		#Controlla di avere abbastanza vigili per max 1 sabato
		num_sabati = len(self.var_sabati.keys())
		num_vigili_per_sabati = len(self.var_sabati[1]) #Giorno 1 è sabato perchè 0 è venerdì
		sabati_extra_tot = sum([v.extraSabati() for v in self.DB.values()])
		sabati_minimi = 0
		if num_vigili_per_sabati + sabati_extra_tot < num_sabati:
			sabati_minimi = math.floor(num_sabati/float(num_vigili_per_sabati))
			print("ATTENZIONE: {} vigili (+{} sabati extra) insufficienti per coprire {} sabati con un solo servizio a testa.".format(num_vigili_per_sabati, sabati_extra_tot, num_sabati))
			print("\tNe assegnerò {}-{}.".format(sabati_minimi, sabati_minimi+1))

		for vigile in self.vigili:
			gruppo = self.DB[vigile].gruppo_festivo

			# Notti non standard
			if num_medio_notti > 0:
				notti_attese = round(num_medio_notti / self.DB[vigile].coeff_notti)
				notti_attese += self.DB[vigile].extraNotti()
				if notti_attese > 9: # Notti extra
					self.constr_notti_non_standard[vigile] = self.solver.Constraint(notti_attese, self.solver.infinity(), "constr_notti_non_standard({})".format(vigile))
					for notte in self.var_notti.keys():
						if vigile in self.var_notti[notte].keys():
							self.constr_notti_non_standard[vigile].SetCoefficient(self.var_notti[notte][vigile], 1)
				elif notti_attese < 8: # Notti in meno
					self.constr_notti_non_standard[vigile] = self.solver.Constraint(-self.solver.infinity(), notti_attese, "constr_notti_non_standard({})".format(vigile))
					for notte in self.var_notti.keys():
						if vigile in self.var_notti[notte].keys():
							self.constr_notti_non_standard[vigile].SetCoefficient(self.var_notti[notte][vigile], 1)

			#Sabati
			if not self.DB[vigile].EsenteSabati():
				sabati_extra = self.DB[vigile].extraSabati()

				#CONSTR: max 1 sabato, se possibile
				if (sabati_minimi + sabati_extra) == 0:
					self.constr_sabati_vigile[vigile] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_un_sabato_vigile({})".format(vigile))
				else:
					self.constr_sabati_vigile[vigile] = self.solver.Constraint(sabati_minimi+sabati_extra, sabati_minimi+sabati_extra+1, "constr_un_sabato_vigile({})".format(vigile))
				for sabato in self.var_sabati.keys():
					self.constr_sabati_vigile[vigile].SetCoefficient(self.var_sabati[sabato][vigile], 1)

				#CONSTR: max 1 tra venerdì notte, sabato e sabato notte
				if "NottiSoloSabato" not in self.DB[vigile].eccezioni and "NottiSoloSabatoFestivi" not in self.DB[vigile].eccezioni:
					self.constr_sabati_notti_circostanti_vigile[vigile] = {}
					for sabato in self.var_sabati.keys():
						self.constr_sabati_notti_circostanti_vigile[vigile][sabato] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_no_sabato_notte_consecutivi_vigile({})_sabato({})".format(vigile, sabato))
						self.constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_sabati[sabato][vigile], 1)
						if vigile in self.var_notti[sabato].keys():
							self.constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_notti[sabato][vigile], 1)
						venerdi = sabato - 1
						if vigile in self.var_notti[venerdi].keys():
							self.constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_notti[venerdi][vigile], 1)

			#CONSTR: max 1 tra sabato e festivi circostanti
			if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].EsenteFestivi():
				self.constr_sabato_festivi_circostanti_vigile[vigile] = {}
				for sabato in self.var_sabati.keys():
					self.constr_sabato_festivi_circostanti_vigile[vigile][sabato] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_sabato_festivi_circostanti_vigile({})_sabato({})".format(vigile, sabato))
					self.constr_sabato_festivi_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_sabati[sabato][vigile], 1)
					for i in range(1, 8):
						if (sabato-i) in self.var_festivi_vigile.keys():
							self.constr_sabato_festivi_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_festivi_vigile[sabato-i][vigile], 1)
						if (sabato+i) in self.var_festivi_vigile.keys():
							self.constr_sabato_festivi_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_festivi_vigile[sabato+i][vigile], 1)

			#CONSTR: max 1 tra festivo e notti circostanti
			self.constr_festivi_notti_circostanti_vigile[vigile] = {}
			for festivo in self.var_festivi_vigile.keys():
				if (
					"NottiSoloSabato" not in self.DB[vigile].eccezioni
					and ("NottiSoloSabatoFestivi" not in self.DB[vigile].eccezioni or self._getWeekdayFromOffset(festivo) not in [5, 6])
					and not self.DB[vigile].EsenteNotti()
					and not self.DB[vigile].EsenteFestivi()
					):
					self.constr_festivi_notti_circostanti_vigile[vigile][festivo] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_no_festivo_notte_consecutivi_vigile({})_festivo({})".format(vigile, festivo))
					self.constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)
					if vigile in self.var_notti[festivo].keys():
						self.constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(self.var_notti[festivo][vigile], 1)
					giorno_prima = festivo - 1
					if vigile in self.var_notti[giorno_prima].keys():
						self.constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(self.var_notti[giorno_prima][vigile], 1)

			#CONSTR: max 1 notte in 3 giorni consecutivi
			self.constr_notti_consecutive_vigile[vigile] = {}
			for notte in self.var_notti.keys():
				if vigile in self.var_notti[notte].keys():
					self.constr_notti_consecutive_vigile[vigile][notte] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_notti_consecutive_vigile({})_giorno({}-{})".format(vigile, notte, notte+3))
					self.constr_notti_consecutive_vigile[vigile][notte].SetCoefficient(self.var_notti[notte][vigile], 1)
					if (notte+1 in self.var_notti.keys()
						and vigile in self.var_notti[notte+1].keys()
						):
						self.constr_notti_consecutive_vigile[vigile][notte].SetCoefficient(self.var_notti[notte+1][vigile], 1)
					if (notte+2 in self.var_notti.keys()
						and vigile in self.var_notti[notte+2].keys()
						):
						self.constr_notti_consecutive_vigile[vigile][notte].SetCoefficient(self.var_notti[notte+2][vigile], 1)
					if (notte+3 in self.var_notti.keys()
						and vigile in self.var_notti[notte+3].keys()
						):
						self.constr_notti_consecutive_vigile[vigile][notte].SetCoefficient(self.var_notti[notte+3][vigile], 1)

			#CONSTR: max 1 servizio oneroso l'anno
			self.constr_servizi_onerosi_vigile[vigile] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_servizi_onerosi_vigile({})".format(vigile))
			for festivo in self.var_festivi_vigile.keys():
				if festivo in self._FESTIVI_ONEROSI:
					if vigile in self.var_festivi_vigile[festivo].keys():
						self.constr_servizi_onerosi_vigile[vigile].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)
			for notte in self.var_notti.keys():
				if notte in self._NOTTI_ONEROSE:
					if vigile in self.var_notti[notte].keys():
						self.constr_servizi_onerosi_vigile[vigile].SetCoefficient(self.var_notti[notte][vigile], 1)

			#CONSTR: spazia i festivi di almeno 5 servizi per lato
			if (gruppo not in self.constr_festivi_spaziati.keys()
				and gruppo != 0):
				self.constr_festivi_spaziati[gruppo] = {}
				lista_FESTIVI = list(self.var_festivi_gruppo.keys())
				guardia = _SPAZIATORE_FESTIVI
				for i, festivo in enumerate(lista_FESTIVI):
					self.constr_festivi_spaziati[gruppo][i] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_festivi_spaziati_gruppo({})_festivo({})".format(gruppo, festivo))
					for j in range(max(0, i-guardia), min(i+guardia, len(lista_FESTIVI))):
						self.constr_festivi_spaziati[gruppo][i].SetCoefficient(self.var_festivi_gruppo[lista_FESTIVI[j]][gruppo], 1)

			#CONSTR: max 5 festivi l'anno
			#NOTA: aggiunto un minimo di 3 per "forzare" il calcolo di una distribuzione più equa più rapidamente
			if not self.DB[vigile].EsenteFestivi():
				self.constr_festivi_vigile[vigile] = self.solver.Constraint(_NUM_MIN_FESTIVI, _NUM_MAX_FESTIVI, "constr_festivi_vigile({})".format(vigile))
				for festivo in self.var_festivi_vigile.keys():
					if vigile in self.var_festivi_vigile[festivo].keys():
						self.constr_festivi_vigile[vigile].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)

			limite_notti = [int(e[len("LimiteNotti"):]) for e in self.DB[vigile].eccezioni if "LimiteNotti" in e]

			#CONSTR: aspiranti che diventano vigili, no servizi prima del passaggio
			if self.DB[vigile].aspirante_passa_a_vigile:
				limite = self._getOffsetFromDate(self.DB[vigile].data_passaggio_vigile)

				self.constr_servizi_aspiranti[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_servizi_aspiranti({})".format(vigile))
				for giorno in range(limite):
					if vigile in self.var_notti[giorno].keys():
						self.constr_servizi_aspiranti[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)
					if giorno in self.var_sabati.keys():
						self.constr_servizi_aspiranti[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
					#No festivi, li fa comunque

			#ECCEZIONI alle regole usuali
			if len(self.DB[vigile].eccezioni) > 0:

				#CONSTR_EX: max notti se limite specificato
				if len(limite_notti) > 0:
					self.constr_ex_limite_notti[vigile] = self.solver.Constraint(-self.solver.infinity(), limite_notti[0], "constr_ex_limite_notti({})".format(vigile))
					for giorno in range(len(self.var_notti.keys())):
						if vigile in self.var_notti[giorno].keys():
							self.constr_ex_limite_notti[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

				#CONSTR_EX: almeno 1 sabato per esenti CP
				if self.DB[vigile].esenteCP() and not self.DB[vigile].EsenteSabati():
					self.constr_ex_sabati_minimi_esenti_CP[vigile] = self.solver.Constraint(1, self.solver.infinity(), "constr_ex_sabati_minimi_esenti_CP_vigile({})".format(vigile))
					for sabato in self.var_sabati.keys():
						if vigile in self.var_sabati[sabato].keys():
							self.constr_ex_sabati_minimi_esenti_CP[vigile].SetCoefficient(self.var_sabati[sabato][vigile], 1)

				#CONSTR_EX: notti solo il sabato o festivi
				if "NottiSoloSabatoFestivi" in self.DB[vigile].eccezioni:
					self.constr_ex_notti_solo_sabato_festivi[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_notti_solo_sabato_festivi_vigile({})".format(vigile))
					for giorno in self.var_notti.keys():
						if vigile in self.var_notti[giorno] and self._getWeekdayFromOffset(giorno) != 5 and giorno not in self.var_festivi_vigile.keys():
							self.constr_ex_notti_solo_sabato_festivi[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

				#CONSTR_EX: no notti in specifici giorni della settimana
				giorni_da_saltare = [_GIORNO_TO_NUM[e[len("NoNottiGiorno"):]] for e in self.DB[vigile].eccezioni if "NoNottiGiorno" in e]
				if len(giorni_da_saltare) > 0:
					self.constr_ex_no_notti_giornosettimana[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_no_notti_giornosettimana_vigile({})".format(vigile))
					for giorno in self.var_notti.keys():
						if self._getWeekdayFromOffset(giorno) in giorni_da_saltare:
							if vigile in self.var_notti[giorno]:
								self.constr_ex_no_notti_giornosettimana[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

				#CONSTR_EX: no notti specifico mese
				mesi_da_saltare = [int(e[len("NoNottiMese"):]) for e in self.DB[vigile].eccezioni if "NoNottiMese" in e]
				if len(mesi_da_saltare) > 0:
					self.constr_ex_no_notti_mese[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_no_notti_mese({})".format(vigile))
					for giorno in self.var_notti.keys():
						if self._getDateFromOffset(giorno).month in mesi_da_saltare:
							if vigile in self.var_notti[giorno]:
								self.constr_ex_no_notti_mese[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

				#CONSTR_EX: no servizi specifico mese
				mesi_da_saltare = [int(e[len("NoServiziMese"):]) for e in self.DB[vigile].eccezioni if "NoServiziMese" in e]
				if len(mesi_da_saltare) > 0:
					self.constr_ex_no_servizi_mese[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_no_servizi_mese_vigile({})".format(vigile))
					for giorno in self.var_notti.keys():
						if self._getDateFromOffset(giorno).month in mesi_da_saltare:
							if vigile in self.var_notti[giorno]:
								self.constr_ex_no_servizi_mese[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)
							if giorno in self.var_sabati.keys():
								if vigile in self.var_sabati[giorno]:
									self.constr_ex_no_servizi_mese[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
							elif giorno in self.var_festivi_vigile.keys() and vigile in self.var_festivi_vigile[giorno].keys() and "FestiviComunque" not in self.DB[vigile].eccezioni:
								self.constr_ex_no_servizi_mese[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1)

				#CONSTR_EX: no servizi se in aspettativa
				if "Aspettativa" in self.DB[vigile].eccezioni:
					self.constr_ex_aspettativa[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_aspettativa_vigile({})".format(vigile))
					for giorno in self.var_notti.keys():
						if vigile in self.var_notti[giorno]:
							self.constr_ex_aspettativa[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)
						if giorno in self.var_sabati.keys():
							if vigile in self.var_sabati[giorno]:
								self.constr_ex_aspettativa[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
						elif giorno in self.var_festivi_vigile.keys():
							if vigile in self.var_festivi_vigile[festivo].keys():
								self.constr_ex_aspettativa[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1)

			#CONSTR: no servizi il giorno di compleanno
			if not servizi_compleanno:
				compleanno = self.DB[vigile].OffsetCompleanno(self.data_inizio)
				self.constr_compleanno_vigile[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_compleanno_vigile({})".format(vigile))
				if compleanno in self.var_notti.keys():
					if vigile in self.var_notti[compleanno].keys():
						self.constr_compleanno_vigile[vigile].SetCoefficient(self.var_notti[compleanno][vigile], 1)
				if compleanno in self.var_sabati.keys() and not (self.DB[vigile].EsenteSabati() or self.DB[vigile].Aspirante()):
					self.constr_compleanno_vigile[vigile].SetCoefficient(self.var_sabati[compleanno][vigile], 1)
				if compleanno in self.var_festivi_vigile.keys() and gruppo != 0:
					self.constr_compleanno_vigile[vigile].SetCoefficient(self.var_festivi_vigile[compleanno][vigile], 1)

			#VAR: somma servizi per vigile (ausiliaria)
			self.var_servizi_vigile[vigile] = self.solver.NumVar(0, self.solver.infinity(), "var_aux_sum_servizi_vigile({})".format(vigile))
			#CONSTR: implementa quanto sopra
			self.constr_servizi_vigile[vigile] = self.solver.Constraint(0, 0, "constr_somma_servizi_vigile({})".format(vigile))
			self.constr_servizi_vigile[vigile].SetCoefficient(self.var_servizi_vigile[vigile], -1)
			for giorno in range(len(self.var_notti.keys())):
				if vigile in self.var_notti[giorno].keys():
					self.constr_servizi_vigile[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)
				if giorno in self.var_sabati.keys():
					if vigile in self.var_sabati[giorno].keys():
						self.constr_servizi_vigile[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
				if giorno in self.var_festivi_vigile.keys() and gruppo != 0:
					if vigile in self.var_festivi_vigile[festivo].keys():
						self.constr_servizi_vigile[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1)

			#VAR: costo servizi per vigile (ausiliaria)
			self.var_cost_servizi_vigile[vigile] = self.solver.NumVar(0, self.solver.infinity(), "var_aux_cost_servizi_vigile({})".format(vigile))
			#CONSTR: implementa quanto sopra
			#Il target è 0 se il vigile non ha fatto più servizi della media
			self.constr_cost_servizi_vigile[vigile] = self.solver.Constraint(-2*self.DB[vigile].passato_servizi_extra, -2*self.DB[vigile].passato_servizi_extra, "constr_costo_servizi_vigile({})".format(vigile))
			self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_cost_servizi_vigile[vigile], -1)
			mul_notti = 1
			mul_sabati = 1 + sum(self.DB[vigile].passato_sabati) #Sabati più probabili se fatti pochi negli anni recenti
			compleanno = self.DB[vigile].OffsetCompleanno(self.data_inizio)
			for giorno in range(len(self.var_notti.keys())):
				mul_notte_squadra = 1
				mul_compleanno = 1
				pen_notti_onerose = 1
				mul_festivi_onerosi = 2
				if giorno == compleanno:
					mul_compleanno = 2
				if giorno in self._NOTTI_ONEROSE:
					pen_notti_onerose += 100 * self.DB[vigile].passato_capodanni
				if giorno in self._FESTIVI_ONEROSI:
					mul_festivi_onerosi = 1 + sum(self.DB[vigile].passato_festivi_onerosi)
				if vigile in self.var_notti[giorno].keys():
					if not (self.giorno_squadra[giorno] in self.DB[vigile].squadre or 0 in self.DB[vigile].squadre):
						mul_notte_squadra = 1.3 # Notti NON di squadra costano di più
					self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1 * mul_compleanno * mul_notti * mul_notte_squadra + pen_notti_onerose)
				if giorno in self.var_sabati.keys():
					if vigile in self.var_sabati[giorno].keys():
						self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 2 * mul_compleanno * mul_sabati)
				if giorno in self.var_festivi_vigile.keys() and gruppo != 0:
					if vigile in self.var_festivi_vigile[giorno].keys():
						self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1.2 * mul_compleanno * mul_festivi_onerosi) # Base 1.2 per forzare massima equità

		for i in range(len(self.vigili)):
			v1 = self.vigili[i]
			if not self.DB[v1].EsenteServizi():
				for j in range(i+1, len(self.vigili)):
					v2 = self.vigili[j]
					if not self.DB[v2].EsenteServizi():
						#VAR: differenza numero servizi tra due vigili (ausiliaria)
						self.var_differenza_servizi[(v1, v2)] = self.solver.NumVar(-self.solver.infinity(), self.solver.infinity(), "var_aux_diff_servizi({},{})".format(v1, v2))
						#CONSTR: implementa quanto sopra
						self.constr_differenza_servizi[(v1, v2, '+')] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_diff_servizi_plus_vigili({},{})".format(v1, v2))
						self.constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(self.var_differenza_servizi[(v1, v2)], -1)
						self.constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(self.var_servizi_vigile[v1], 1)
						self.constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(self.var_servizi_vigile[v2], -1)
						self.constr_differenza_servizi[(v1, v2, '-')] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_diff_servizi_minus_vigili({},{})".format(v1, v2))
						self.constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(self.var_differenza_servizi[(v1, v2)], -1)
						self.constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(self.var_servizi_vigile[v1], -1)
						self.constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(self.var_servizi_vigile[v2], 1)

		### FASE 3 ###
		print("* Fase 3: definisco l'obiettivo...")

		# OBJECTIVE
		objective = self.solver.Objective()
		#OBJ: minimizza le differenze tra servizi ed il costo totale dei servizi
		for var in self.var_differenza_servizi.values():
			objective.SetCoefficient(var, 1)
		for var in self.var_cost_servizi_vigile.values():
			objective.SetCoefficient(var, (len(self.vigili) - 1))
		objective.SetMinimization()
		#TODO: add -distance between selected services component?
		#Quadratic term, e.g. 136 notte_136_vigile_1 - max(2 notte_2_vigile_1, 76 notte_76_vigile_1) * notte_136_vigile_1

		print("* Il modello ha {} variabili e {} vincoli.".format(self.solver.NumVariables(), self.solver.NumConstraints()))

		model_f = open("model.txt", "w")
		model_f.write(self.solver.ExportModelAsLpFormat(False))
		# model_f.write(Solver.ExportModelAsMpsFormat(True, False))
		model_f.close()

	def Solve(self, time_limit, verbose=False, num_threads=1):
		#Solver Parameters
		if verbose:
			self.solver.EnableOutput()
		self.solver.SetNumThreads(num_threads)
		if time_limit > 0:
			self.solver.SetTimeLimit(time_limit * 1000) #ms
		print("Risolvo il modello... (max {}s)".format(time_limit if time_limit > 0 else "∞"))
		self.STATUS = self.solver.Solve()

	def PrintSolution(self):
		self._printed_solution = True
		if self.STATUS == pywraplp.Solver.INFEASIBLE:
			print('Il problema non ammette soluzione.')
			print('Rilassa i vincoli e riprova.')
		else:
			if self.STATUS == pywraplp.Solver.FEASIBLE:
				print("ATTENZIONE: la soluzione trovata potrebbe non essere ottimale.")
			print('Soluzione:')
			print('* Funzione obiettivo: ', self.solver.Objective().Value())
			print("* Servizi per vigile:")
			for vigile in self.vigili:
				for giorno in self.var_notti.keys():
					if vigile in self.var_notti[giorno].keys():
						self.DB[vigile].notti += int(self.var_notti[giorno][vigile].solution_value())
						if giorno in self._NOTTI_ONEROSE and self.var_notti[giorno][vigile].solution_value() == 1:
							self.DB[vigile].capodanno += 1
				for giorno in self.var_sabati.keys():
					if vigile in self.var_sabati[giorno].keys():
						self.DB[vigile].sabati += int(self.var_sabati[giorno][vigile].solution_value())
				for giorno in self.var_festivi_vigile.keys():
					if vigile in self.var_festivi_vigile[giorno].keys():
						self.DB[vigile].festivi += int(self.var_festivi_vigile[giorno][vigile].solution_value())
						if giorno in self._FESTIVI_ONEROSI and self.var_festivi_vigile[giorno][vigile].solution_value() == 1:
							self.DB[vigile].festivi_onerosi += 1
				line = "{:03d} {}".format(vigile, self.DB[vigile].grado)
				if self.DB[vigile].neo_vigile:
					line += "*"
				line += " {} {}".format(self.DB[vigile].nome, self.DB[vigile].cognome)
				line += ": {}".format(int(self.var_servizi_vigile[vigile].solution_value()))
				line += "\n\tNotti: {}\n\tSabati: {}\n\tFestivi: {}".format(self.DB[vigile].notti, self.DB[vigile].sabati, self.DB[vigile].festivi)
				if len(self.DB[vigile].eccezioni) > 0:
					line += "\n\tEccezioni: {}".format(self.DB[vigile].eccezioni)
				print(line)

	def SaveSolution(self):
		if not self._printed_solution:
			self.PrintSolution() #Necessaria per precalcolare i numeri di servizi di ogni vigile
		if self.STATUS == pywraplp.Solver.INFEASIBLE:
			return
		else:
			# Salva i turni calcolati in un CSV
			print("Salvo la soluzione...")
			out = open("./turni_{}.csv".format(self.anno), "w")
			out.write("#Data;Notte;Sabato/Festivo;;;;;Affiancamento\n")
			for giorno in range(len(self.var_notti.keys())):
				data = self.data_inizio + dt.timedelta(giorno)
				line = str(data)+";"
				for vigile in self.var_notti[giorno].keys():
					if self.var_notti[giorno][vigile].solution_value() == 1:
						line += self.DB[vigile].nome+" "+self.DB[vigile].cognome+";"
				if giorno in self.var_sabati.keys():
					frag = ""
					for vigile in self.vigili:
						if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].Aspirante() and self.var_sabati[giorno][vigile].solution_value() == 1:
							frag += self.DB[vigile].nome+" "+self.DB[vigile].cognome+";"
					line += frag
					line += ";" * (5 - len(frag.split(";")))
				elif giorno in self.var_festivi_vigile.keys():
					frag = ""
					for vigile in self.vigili:
						if vigile in self.var_festivi_vigile[giorno].keys():
							if self.var_festivi_vigile[giorno][vigile].solution_value() == 1:
								frag += self.DB[vigile].nome+" "+self.DB[vigile].cognome+";"
					line += frag
					line += ";" * (5 - len(frag.split(";")))
				else:
					line += ";;;;;"
				out.write(line+"\n")
			out.close()

			# Calcola il numero medio di servizi svolti dai vigili senza vincoli
			s = 0
			i = 0
			for vigile in self.vigili:
				if (
					self.DB[vigile].grado == "Vigile" #Escludi altri gradi che hanno limitazioni # Inserire capisquadra?
					and not self.DB[vigile].esenteCP() #Gli esenti fanno più servizi
					and not self.DB[vigile].AltreCariche() #Hanno meno servizi
					and "Aspettativa" not in self.DB[vigile].eccezioni
					):
					s += self.DB[vigile].NumeroServizi()
					i += 1
			media_servizi = float(s)/i
			print("Media servizi per vigile: ", media_servizi)

			# Riporta il numero di servizi extra ed i servizi speciali
			out = open("./riporti_{}.csv".format(self.anno), "w")
			out.write("#Vigile;Differenza vs. Media;Capodanno;Sabati;;;;;;;;;;Festivi Onerosi\n")
			for vigile in self.vigili:
				line = "{};".format(vigile)
				servizi_extra = 0
				if (
					self.DB[vigile].grado == "Vigile"
					and not self.DB[vigile].esenteCP()
					and not self.DB[vigile].AltreCariche()
					and "Aspettativa" not in self.DB[vigile].eccezioni
					and not self.DB[vigile].neo_vigile
					):
					servizi_extra = round(self.DB[vigile].NumeroServizi() - media_servizi)
				line += "{};".format(servizi_extra)
				line += "{};".format(self.DB[vigile].passato_capodanni + self.DB[vigile].capodanno)
				line += "{};".format(self.DB[vigile].sabati)
				for sabati in self.DB[vigile].passato_sabati[0:9]:
					line += "{};".format(sabati)
				line += "{};".format(self.DB[vigile].festivi_onerosi)
				for festivi in self.DB[vigile].passato_festivi_onerosi[0:9]:
					line += "{};".format(festivi)
				out.write(line+"\n")
			out.close()

	def _getDateFromOffset(self, offset):
		return self.data_inizio + dt.timedelta(offset)

	def _getWeekdayFromOffset(self, offset):
		return self._getDateFromOffset(offset).weekday()

	def _getOffsetFromDate(self, date):
		return (date - self.data_inizio).days

def _calc_easter(year):
    "Returns Easter as a date object."
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