from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import math
import vvf_io

class TurnazioneVVF:
	#Collections
	giorno_squadra = {}

	var_notti = {}
	constr_notti = {}
	constr_notti_settimana_vigile = {}

	var_sabati = {}
	constr_sabati = {}
	constr_sabati_vigile = {}
	constr_sabati_notti_circostanti_vigile = {}

	var_festivi_gruppo = {}
	var_festivi_vigile = {}
	constr_festivi = {}
	constr_festivi_vigili_gruppo = {}
	constr_festivi_vigile = {}
	constr_festivi_num_vigili = {}
	constr_festivi_notti_circostanti_vigile = {}
	constr_festivi_spaziati = {}
	
	constr_servizi_onerosi_vigile = {}
	constr_compleanno_vigile = {}

	var_servizi_vigile = {}
	constr_servizi_vigile = {}
	var_cost_servizi_vigile = {}
	constr_cost_servizi_vigile = {}
	var_differenza_servizi = {}
	constr_differenza_servizi = {}

	constr_notti_graduati = {}
	constr_sabati_graduati = {}
	constr_festivi_graduati = {}
	constr_servizi_aspiranti_passaggio_vigile = {}

	constr_ex_notti_direttivo = {}
	constr_ex_sabati_direttivo = {}
	constr_ex_festivi_direttivo = {}

	constr_ex_notti_minime_esenti_CP = {}
	constr_ex_sabati_minimi_esenti_CP = {}
	constr_ex_festivi_minimi_esenti_CP = {}

	constr_ex_notti_solo_sabato_festivi = {}
	constr_ex_no_notti_giornosettimana = {}
	constr_ex_no_servizi_mese = {}
	constr_ex_no_servizi_aspettativa = {}

	DB = {}
	vigili = []
	vigili_squadra = {}
	vigili_gruppi_festivo = {}
	anno = 0
	data_inizio = 0
	data_fine = 0
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
			dt.date(self.anno,12,31),	#Capodanno
			]
		self._FESTIVI_SPECIALI = list(map(self._getOffsetFromDate, self._FESTIVI_SPECIALI))
		self._NOTTI_ONEROSE = list(map(self._getOffsetFromDate, self._NOTTI_ONEROSE))
		self._FESTIVI_ONEROSI = [
			self._FESTIVI_SPECIALI[1], #Pasqua
			self._FESTIVI_SPECIALI[6], #Ferragosto
			self._FESTIVI_SPECIALI[9], #Natale
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
			print("ERRORE: il periodo dal {} al {} è troppo lungo, sei sicuro sia giusto?".format(self.data_inizio, self.data_fine))
			exit(-1)
		elif (self.data_fine - self.data_inizio).days < 350:
			print("ERRORE: il periodo dal {} al {} è troppo lungo, sei sicuro sia giusto?".format(self.data_inizio, self.data_fine))
			exit(-1)
		loose = args.loose
		servizi_compleanno = args.servizi_compleanno
		self._computeServiziSpecialiOnerosi()
		self.DB = vvf_io.read_csv_vigili(args.organico_fn)
		self.DB = vvf_io.read_csv_riporti(self.DB, args.riporti_fn)
		self.DB = vvf_io.correggi_aspiranti(self.DB, self.data_inizio, self.data_fine)
		self.vigili = list(self.DB.keys())
		self.vigili_squadra = {}
		self.vigili_gruppi_festivo = {}
		for vigile in self.vigili:
			# Squadra
			if self.DB[vigile].squadra == 0:
				continue
			elif self.DB[vigile].squadra not in self.vigili_squadra.keys():
				self.vigili_squadra[self.DB[vigile].squadra] = []
			self.vigili_squadra[self.DB[vigile].squadra].append(vigile)
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
						and (self.DB[vigile].squadra == curr_squadra
						or self.DB[vigile].squadra == 0
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
						if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].Aspirante():
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
						
					#CONSTR: gruppo implica vigile
					self.constr_festivi_vigili_gruppo[curr_giorno] = {}
					for gruppo in self.vigili_gruppi_festivo.keys():
						self.constr_festivi_vigili_gruppo[curr_giorno][gruppo] = self.solver.Constraint(0, self.solver.infinity(), "constr_festivo_vigili_gruppo({})_festivo({})".format(gruppo, curr_giorno))
						self.constr_festivi_vigili_gruppo[curr_giorno][gruppo].SetCoefficient(self.var_festivi_gruppo[curr_giorno][gruppo], -1)
						for vigile in self.vigili_gruppi_festivo[gruppo]:
							self.constr_festivi_vigili_gruppo[curr_giorno][gruppo].SetCoefficient(self.var_festivi_vigile[curr_giorno][vigile], 1)

					#CONSTR: 3-5 vigili a festivo
					self.constr_festivi_num_vigili[curr_giorno] = self.solver.Constraint(3, 5, "constr_festivi_num_vigili({})".format(curr_giorno))
					for vigile in self.var_festivi_vigile[curr_giorno].keys():
						self.constr_festivi_num_vigili[curr_giorno].SetCoefficient(self.var_festivi_vigile[curr_giorno][vigile], 1)
					
			#CONSTR: max 1 notte per vigile a settimana
			settimana = int(giorno / 7)
			self.constr_notti_settimana_vigile[settimana] = {}
			for vigile in self.var_notti[curr_giorno].keys():
				max_notti_settimana = 1
				#Max 2 notti a settimana se esente CP o fa notti solo in alcuni giorni
				lim_giorni = len([e for e in self.DB[vigile].eccezioni if "NoNotti" in e])
				lim_mesi = len([e for e in self.DB[vigile].eccezioni if "NoNotti" in e])
				if (
					self.DB[vigile].esente_cp
					or "NottiSoloSabatoFestivi" in self.DB[vigile].eccezioni
					or lim_giorni >= 5
					or lim_mesi >= 5
					):
					max_notti_settimana = 2
				elif lim_mesi >= 9:
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
		sabati_minimi = 0
		if num_vigili_per_sabati < num_sabati:
			sabati_minimi = math.floor(num_sabati/float(num_vigili_per_sabati))
			print("ATTENZIONE: {} vigili insufficienti per coprire {} sabati con un solo servizio a testa.".format(num_vigili_per_sabati, num_sabati))
			print("\tNe assegnerò {}-{}.".format(sabati_minimi, sabati_minimi+1))

		for vigile in self.vigili:
			gruppo = self.DB[vigile].gruppo_festivo
			
			if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].Aspirante():
				#CONSTR: max 1 sabato, se possibile
				if sabati_minimi == 0:
					self.constr_sabati_vigile[vigile] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_un_sabato_vigile({})".format(vigile))
				else:
					self.constr_sabati_vigile[vigile] = self.solver.Constraint(sabati_minimi, sabati_minimi+1, "constr_un_sabato_vigile({})".format(vigile))
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

			#CONSTR: spazia i festivi (di gruppo) di almeno 5 servizi per lato
			if (gruppo not in self.constr_festivi_spaziati.keys()
				and gruppo != 0):
				self.constr_festivi_spaziati[gruppo] = {}
				lista_FESTIVI = list(self.var_festivi_gruppo.keys())
				guardia = 5
				for i, festivo in enumerate(lista_FESTIVI):
					self.constr_festivi_spaziati[gruppo][i] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_festivi_spaziati_gruppo({})_festivo({})".format(gruppo, festivo))
					for j in range(max(0, i-guardia), min(i+guardia, len(lista_FESTIVI))):
						self.constr_festivi_spaziati[gruppo][i].SetCoefficient(self.var_festivi_gruppo[lista_FESTIVI[j]][gruppo], 1)

			#CONSTR: max 5 festivi l'anno
			#NOTA: aggiunto un minimo di 3 per "forzare" il calcolo di una distribuzione più equa più rapidamente
			if ("Aspettativa" not in self.DB[vigile].eccezioni and not self.DB[vigile].EsenteFestivi()):
				self.constr_festivi_vigile[vigile] = self.solver.Constraint(3, 5, "constr_festivi_vigile({})".format(vigile))
				for festivo in self.var_festivi_vigile.keys():
					if vigile in self.var_festivi_vigile[festivo].keys():
						self.constr_festivi_vigile[vigile].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)

			#CONSTR: max 3 notti per comandante
			if self.DB[vigile].grado in ["Comandante"]:
				self.constr_notti_graduati[vigile] = self.solver.Constraint(-self.solver.infinity(), 3, "constr_notti_graduati_comandante({})".format(vigile))
				for giorno in range(len(self.var_notti.keys())):
					self.constr_notti_graduati[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

			#CONSTR: max 4 notti per vicecomandante
			if self.DB[vigile].grado in ["Viceomandante"]:
				self.constr_notti_graduati[vigile] = self.solver.Constraint(-self.solver.infinity(), 4, "constr_notti_graduati_vicecomandante({})".format(vigile))
				for giorno in range(len(self.var_notti.keys())):
					self.constr_notti_graduati[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

			#CONSTR: max 3 festivi per comandante e vice
			if self.DB[vigile].grado in ["Comandante", "Vicecomandante"]:
				self.constr_festivi_graduati[vigile] = self.solver.Constraint(-self.solver.infinity(), 3, "constr_festivi_graduati_comandanti({})".format(vigile))
				for festivo in self.var_festivi_vigile.keys():
					self.constr_festivi_graduati[vigile].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)

			#CONSTR: max 7 notti per capiplotone e capisquadra
			if self.DB[vigile].grado in ["Capoplotone", "Caposquadra"]:
				self.constr_notti_graduati[vigile] = self.solver.Constraint(-self.solver.infinity(), 7, "constr_notti_graduati_capi({})".format(vigile))
				for giorno in range(len(self.var_notti.keys())):
					if vigile in self.var_notti[giorno].keys():
						self.constr_notti_graduati[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

			#CONSTR: max 4 festivi per capiplotone e capisquadra
			if self.DB[vigile].grado in ["Capoplotone", "Caposquadra"]:
				self.constr_festivi_graduati[vigile] = self.solver.Constraint(-self.solver.infinity(), 4, "constr_festivi_graduati_capi({})".format(vigile))
				for festivo in self.var_festivi_vigile.keys():
					self.constr_festivi_graduati[vigile].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)

			#CONSTR: max 1 sabato per graduati
			if self.DB[vigile].Graduato():
				self.constr_sabati_graduati[vigile] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_sabati_graduati({})".format(vigile))
				for sabato in self.var_sabati.keys():
					self.constr_sabati_graduati[vigile].SetCoefficient(self.var_sabati[sabato][vigile], 1)

			#CONSTR: aspiranti che diventano vigili, no servizi prima del passaggio
			if self.DB[vigile].aspirante_passa_a_vigile:
				limite = self._getOffsetFromDate(self.DB[vigile].data_passaggio_vigile)
				self.constr_servizi_aspiranti_passaggio_vigile[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_servizi_aspirante_passaggio_vigile({})".format(vigile))
				for giorno in range(limite):
					if vigile in self.var_notti[giorno].keys():
						self.constr_servizi_aspiranti_passaggio_vigile[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)
					if giorno in self.var_sabati.keys():
						self.constr_servizi_aspiranti_passaggio_vigile[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
					#No festivi, li fa comunque

			#ECCEZIONI alle regole usuali
			if len(self.DB[vigile].eccezioni) > 0:

				#CONSTR_EX: max 5 notti per direttivo, altre cariche:
				carica_direttivo_altro = [c for c in self.DB[vigile].eccezioni if c in ["Segretario", "Cassiere", "Magazziniere", "Resp. Allievi", "Vicemagazziniere"]] #TODO: check vicemagazziniere
				if len(carica_direttivo_altro) > 0:
					self.constr_ex_notti_direttivo[vigile] = self.solver.Constraint(-self.solver.infinity(), 5, "constr_ex_notti_direttivo({})".format(vigile))
					for giorno in range(len(self.var_notti.keys())):
						if vigile in self.var_notti[giorno].keys():
							self.constr_ex_notti_direttivo[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

				#CONSTR_EX: max 1 sabato per direttivo, altre cariche:
				carica_direttivo_altro = [c for c in self.DB[vigile].eccezioni if c in ["Segretario", "Cassiere", "Magazziniere", "Resp. Allievi", "Vicemagazziniere"]] #TODO: check vicemagazziniere
				if len(carica_direttivo_altro) > 0:
					self.constr_ex_sabati_direttivo[vigile] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_ex_sabati_direttivo({})".format(vigile))
					for sabato in self.var_sabati.keys():
						if vigile in self.var_sabati[sabato].keys():
							self.constr_ex_sabati_direttivo[vigile].SetCoefficient(self.var_sabati[sabato][vigile], 1)

				#CONSTR_EX: max 4 festivi per altre cariche direttivo
				carica_direttivo = [c for c in self.DB[vigile].eccezioni if c in ["Segretario", "Cassiere", "Magazziniere"]]
				if len(carica_direttivo) > 0:
					self.constr_ex_festivi_direttivo[vigile] = self.solver.Constraint(-self.solver.infinity(), 4, "constr_ex_festivi_direttivo({})".format(vigile))
					for festivo in self.var_festivi_vigile.keys():
						self.constr_ex_festivi_direttivo[vigile].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)

				#CONSTR_EX: almeno 15 notti per esenti CP
				if self.DB[vigile].esente_cp and not self.DB[vigile].EsenteNotti():
					self.constr_ex_notti_minime_esenti_CP[vigile] = self.solver.Constraint(15, self.solver.infinity(), "constr_ex_notti_minime_esenti_CP_vigile({})".format(vigile))
					for giorno in range(len(self.var_notti.keys())):
						if vigile in self.var_notti[giorno].keys():
							self.constr_ex_notti_minime_esenti_CP[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

				#CONSTR_EX: almeno 1 sabato per esenti CP
				if self.DB[vigile].esente_cp and not self.DB[vigile].EsenteSabati():
					self.constr_ex_sabati_minimi_esenti_CP[vigile] = self.solver.Constraint(1, self.solver.infinity(), "constr_ex_sabati_minimi_esenti_CP_vigile({})".format(vigile))
					for sabato in self.var_sabati.keys():
						if vigile in self.var_sabati[sabato].keys():
							self.constr_ex_sabati_minimi_esenti_CP[vigile].SetCoefficient(self.var_sabati[sabato][vigile], 1)

				#CONSTR_EX: almeno 5 festivi per esenti CP
				if self.DB[vigile].esente_cp and not self.DB[vigile].EsenteFestivi():
					self.constr_ex_festivi_minimi_esenti_CP[vigile] = self.solver.Constraint(5, self.solver.infinity(), "constr_ex_festivi_minimi_esenti_CP({})".format(vigile))
					for festivo in self.var_festivi_vigile.keys():
						if vigile in self.var_festivi_vigile[festivo].keys():
							self.constr_ex_festivi_minimi_esenti_CP[vigile].SetCoefficient(self.var_festivi_vigile[festivo][vigile], 1)

				#CONSTR_EX: notti solo il sabato o festivi
				if "NottiSoloSabatoFestivi" in self.DB[vigile].eccezioni:
					self.constr_ex_notti_solo_sabato_festivi[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_notti_solo_sabato_festivi_vigile({})".format(vigile))
					for giorno in self.var_notti.keys():
						if vigile in self.var_notti[giorno] and self._getWeekdayFromOffset(giorno) != 5 and giorno not in self.var_festivi_vigile.keys():
							self.constr_ex_notti_solo_sabato_festivi[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

				#CONSTR_EX: no notti in specifici giorni della settimana
				giorni_da_saltare = [_GIORNO_TO_NUM[e[len("NoNotti"):]] for e in self.DB[vigile].eccezioni if "NoNotti" in e]
				if len(giorni_da_saltare) > 0:
					self.constr_ex_no_notti_giornosettimana[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_no_notti_giornosettimana_vigile({})".format(vigile))
					for giorno in self.var_notti.keys():
						if self._getWeekdayFromOffset(giorno) in giorni_da_saltare:
							if vigile in self.var_notti[giorno]:
								self.constr_ex_no_notti_giornosettimana[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

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
							elif giorno in self.var_festivi_vigile.keys() and "FestiviComunque" not in self.DB[vigile].eccezioni:
								self.constr_ex_no_servizi_mese[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1)

				#CONSTR_EX: no servizi se in aspettativa
				if "Aspettativa" in self.DB[vigile].eccezioni:
					self.constr_ex_no_servizi_aspettativa[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_ex_no_servizi_aspettativa_vigile({})".format(vigile))
					for giorno in self.var_notti.keys():
						if vigile in self.var_notti[giorno]:
							self.constr_ex_no_servizi_aspettativa[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)
						if giorno in self.var_sabati.keys():
							if vigile in self.var_sabati[giorno]:
								self.constr_ex_no_servizi_aspettativa[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
						elif giorno in self.var_festivi_vigile.keys():
							if vigile in self.var_festivi_vigile[festivo].keys():
								self.constr_ex_no_servizi_aspettativa[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1)

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
						self.constr_servizi_vigile[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1.1) # 1.1 per favorire l'assegnazione dello stesso numero di sabati
				if giorno in self.var_festivi_vigile.keys() and gruppo != 0:
					if vigile in self.var_festivi_vigile[festivo].keys():
						self.constr_servizi_vigile[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1.01) # 1.01 per favorire l'assegnazione dello stesso numero di festivi

			#VAR: costo servizi per vigile (ausiliaria)
			self.var_cost_servizi_vigile[vigile] = self.solver.NumVar(0, self.solver.infinity(), "var_aux_cost_servizi_vigile({})".format(vigile))
			#CONSTR: implementa quanto sopra
			#Il target è 0 se il vigile non ha fatto più servizi della media
			self.constr_cost_servizi_vigile[vigile] = self.solver.Constraint(-2*self.DB[vigile].passato_servizi_extra, -2*self.DB[vigile].passato_servizi_extra, "constr_costo_servizi_vigile({})".format(vigile))
			self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_cost_servizi_vigile[vigile], -1)
			mul_notti = 1
			mul_sabati = 1 + sum(self.DB[vigile].passato_sabati) #Sabati più probabili se fatti pochi negli anni recenti
			if self.DB[vigile].aspirante_passa_a_vigile:
				mul_notti *= float(num_giorni)/(num_giorni - self._getOffsetFromDate(self.DB[vigile].data_passaggio_vigile))
				mul_sabati *= float(num_giorni)/(num_giorni - self._getOffsetFromDate(self.DB[vigile].data_passaggio_vigile))
			# if self.DB[vigile].esente_cp:
				 # *= 0.5
			compleanno = self.DB[vigile].OffsetCompleanno(self.data_inizio)
			for giorno in range(len(self.var_notti.keys())):
				mul_notte_squadra = 1
				mul_compleanno = 1
				pen_notti_onerose = 1
				mul_festivi_onerosi = 1
				if giorno == compleanno:
					mul_compleanno = 2
				if giorno in self._NOTTI_ONEROSE:
					pen_notti_onerose += 1000 * self.DB[vigile].passato_capodanni
				if giorno in self._FESTIVI_ONEROSI:
					mul_festivi_onerosi = 1 + sum(self.DB[vigile].passato_festivi_onerosi)
				if vigile in self.var_notti[giorno].keys():
					if not (self.giorno_squadra[giorno] == self.DB[vigile].squadra or self.DB[vigile].squadra == 0):
						mul_notte_squadra = 2 # Notti NON di squadra costano il doppio
					self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1 * mul_compleanno * mul_notti * mul_notte_squadra + pen_notti_onerose)
				if giorno in self.var_sabati.keys():
					if vigile in self.var_sabati[giorno].keys():
						self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1.5 * mul_compleanno * mul_sabati) # Base 1.5 perchè se ne assegna due almeno cerca di assegnare una notte in meno...
				if giorno in self.var_festivi_vigile.keys() and gruppo != 0:
					if vigile in self.var_festivi_vigile[giorno].keys():
						self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_festivi_vigile[giorno][vigile], 1 * mul_compleanno * mul_festivi_onerosi)

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
		self.solver.SetTimeLimit(time_limit) #ms
		print("Risolvo il modello... (max {}s)".format(int(float(time_limit)/1000)))
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
				line = "{:03d}-{}".format(vigile, self.DB[vigile].grado)
				if self.DB[vigile].aspirante_passa_a_vigile:
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
					and not self.DB[vigile].esente_cp #Gli esenti fanno più servizi
					and not self.DB[vigile].AltreCariche() #Hanno meno servizi
					and "Aspettativa" not in self.DB[vigile].eccezioni
					):
					s += self.DB[vigile].NumeroServizi()
					i += 1
			media_servizi = float(s)/i
			# print("INFO: la media dei servizi dei vigili è ", media_servizi)

			# Riporta il numero di servizi extra ed i servizi speciali
			out = open("./riporti_{}.csv".format(self.anno), "w")
			out.write("#Vigile;Servizi Extra Media;Capodanni;Sabati;;;;;Festivi Onerosi\n")
			for vigile in self.vigili:
				line = "{};".format(vigile)
				servizi_extra = 0
				if (
					self.DB[vigile].grado == "Vigile"
					and not self.DB[vigile].esente_cp
					and not self.DB[vigile].AltreCariche()
					and "Aspettativa" not in self.DB[vigile].eccezioni
					):
					servizi_extra = round(self.DB[vigile].NumeroServizi() - media_servizi)
				line += "{};".format(servizi_extra)
				line += "{};".format(self.DB[vigile].passato_capodanni + self.DB[vigile].capodanno)
				line += "{};".format(self.DB[vigile].sabati)
				for sabati in self.DB[vigile].passato_sabati[0:4]:
					line += "{};".format(sabati)
				line += "{};".format(self.DB[vigile].festivi_onerosi)
				for festivi in self.DB[vigile].passato_festivi_onerosi[0:4]:
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