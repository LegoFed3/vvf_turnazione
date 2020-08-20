from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import vvf_io

class VVF_Turnazione:
	#Collections
	giorno_squadra = {}

	var_notti = {}
	constr_notti = {}
	constr_notti_settimana_vigile = {}

	var_sabati = {}
	constr_sabati = {}
	constr_sabati_vigile = {}
	constr_sabati_notti_circostanti_vigile = {}

	var_festivi = {}
	constr_festivi = {}
	constr_festivi_vigile = {}
	constr_festivi_notti_circostanti_vigile = {}
	constr_compleanno_vigile = {}

	var_servizi_vigile = {}
	constr_servizi_vigile = {}
	var_cost_servizi_vigile = {}
	constr_cost_servizi_vigile = {}
	constr_notti_comandanti = {}
	constr_festivi_comandanti = {}
	var_differenza_servizi = {}
	constr_differenza_servizi = {}
	
	DB = {}
	vigili = []
	vigili_squadra = {}
	vigili_gruppi_festivo = {}
	num_squadre = 0
	anno = 0
	giorno_inizio = 0
	giorno_fine = 0
	num_giorni = 0
	data_inizio = 0
	data_fine = 0

	#Model
	solver = pywraplp.Solver('VVF_turni', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
	status = -1
	
	def __init__(self, data_inizio, data_fine, squadra_di_partenza, giorni_festivi_speciali, vigili_fn, loose=False):
		print("Creo il modello...")
		self.data_inizio = data_inizio
		self.data_fine = data_fine
		self.DB = vvf_io.read_csv_vigili(vigili_fn)
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

		self.num_squadre = len(self.vigili_squadra.keys())
		self.anno = data_inizio.year
		self.giorno_inizio = data_inizio.day
		self.giorno_fine = data_fine.day
		self.num_giorni = (data_fine - data_inizio).days
		giorno = 0
		curr_squadra = squadra_di_partenza
		while giorno < self.num_giorni:
			for i in range(7):
				curr_giorno = giorno + i
				curr_data = data_inizio + dt.timedelta(curr_giorno)
				
				self.giorno_squadra[curr_giorno] = curr_squadra

				#VAR: vigili di squadra candidati per la notte
				self.var_notti[curr_giorno] = {}
				for vigile in self.vigili:
					if not self.DB[vigile].esente_notti() and (self.DB[vigile].squadra == curr_squadra or self.DB[vigile].squadra == 0 or loose):
						self.var_notti[curr_giorno][vigile] = self.solver.IntVar(0, 1, "var_vigile({})_notte({})".format(vigile, curr_giorno))
					
				#CONSTR: 1 vigile per notte
				self.constr_notti[curr_giorno] = self.solver.Constraint(1, 1, "constr_notte({})".format(curr_giorno))
				for var in self.var_notti[curr_giorno].values():
					self.constr_notti[curr_giorno].SetCoefficient(var, 1)
					
				#SABATO
				if curr_data.weekday() == 5 and curr_data not in giorni_festivi_speciali:

					#VAR: vigile candidati per il sabato
					self.var_sabati[curr_giorno] = {}
					for vigile in self.vigili:
						if not self.DB[vigile].esente_sabati():
							self.var_sabati[curr_giorno][vigile] = self.solver.IntVar(0, 1, "var_vigile({})_sabato({})".format(vigile, curr_giorno))

					#CONSTR: 1 vigile per sabato
					self.constr_sabati[curr_giorno] = self.solver.Constraint(1, 1, "constr_sabato({})".format(curr_giorno))
					for vigile in self.vigili:
						if not self.DB[vigile].esente_sabati():
							self.constr_sabati[curr_giorno].SetCoefficient(self.var_sabati[curr_giorno][vigile], 1)

				#FESTIVO
				if curr_data.weekday() == 6 or curr_data in giorni_festivi_speciali:
					
					#VAR: vigili candidati per il festivo
					self.var_festivi[curr_giorno] = {}
					for gruppo in self.vigili_gruppi_festivo.keys():
						self.var_festivi[curr_giorno][gruppo] = self.solver.IntVar(0, 1, "var_gruppo({})_festivo({})".format(gruppo, curr_giorno))
						
					#CONSTR: 1 gruppo festivo a festivo
					self.constr_festivi[curr_giorno] = self.solver.Constraint(1, 1, "constr_festivo({})".format(curr_giorno))
					for gruppo in self.vigili_gruppi_festivo.keys():
						self.constr_festivi[curr_giorno].SetCoefficient(self.var_festivi[curr_giorno][gruppo], 1)
					
			#CONSTR: max 1 notte per vigile a settimana
			settimana = int(giorno / 7)
			self.constr_notti_settimana_vigile[settimana] = {}
			for vigile in self.vigili:
				if not self.DB[vigile].esente_notti() and (self.DB[vigile].squadra == curr_squadra or self.DB[vigile].squadra == 0 or loose):
					self.constr_notti_settimana_vigile[settimana][vigile] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_una_notte_settimana({})_vigile({})".format(settimana, vigile))
					for i in range(7):
						curr_giorno = giorno + i
						self.constr_notti_settimana_vigile[settimana][vigile].SetCoefficient(self.var_notti[curr_giorno][vigile], 1)

			curr_squadra = (curr_squadra % self.num_squadre) + 1
			giorno += 7

		for vigile in self.vigili:
			gruppo = self.DB[vigile].gruppo_festivo
			
			if not self.DB[vigile].esente_sabati():
				#CONSTR: max 1 sabato
				self.constr_sabati_vigile[vigile] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_un_sabato_vigile({})".format(vigile))
				for sabato in self.var_sabati.keys():
					self.constr_sabati_vigile[vigile].SetCoefficient(self.var_sabati[sabato][vigile], 1)

				#CONSTR: max 1 tra venerdì notte, sabato e sabato notte
				self.constr_sabati_notti_circostanti_vigile[vigile] = {}
				for sabato in self.var_sabati.keys():
					self.constr_sabati_notti_circostanti_vigile[vigile][sabato] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_sabato_notte_consecutivi_vigile({})_sabato({})".format(vigile, sabato))
					self.constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_sabati[sabato][vigile], 1)
					if vigile in self.var_notti[sabato].keys():
						self.constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_notti[sabato][vigile], 1)
					venerdi = sabato - 1
					if vigile in self.var_notti[venerdi].keys():
						self.constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(self.var_notti[venerdi][vigile], 1)

			#CONSTR: 3-5 festivi l'anno
			if gruppo not in self.constr_festivi_vigile.keys():
				self.constr_festivi_vigile[gruppo] = self.solver.Constraint(3, 5, "constr_festivi_annuali_vigile({})".format(gruppo))
				for festivo in self.var_festivi.keys():
					self.constr_festivi_vigile[gruppo].SetCoefficient(self.var_festivi[festivo][gruppo], 1)

			#CONSTR: max 3 notti per comandante e vice
			if self.DB[vigile].grado in ["Comandante", "Vicecomandante"]:
				self.constr_notti_comandanti[vigile] = self.solver.Constraint(0, 3, "constr_notti_comandanti({})".format(vigile))
				for giorno in range(len(self.var_notti.keys())):
					self.constr_notti_comandanti[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)

			#CONSTR: max 3 festivi per comandante e vice
			if self.DB[vigile].grado in ["Comandante", "Vicecomandante"]:
				self.constr_festivi_comandanti[vigile] = self.solver.Constraint(0, 3, "constr_festivi_comandanti({})".format(vigile))
				for festivo in self.var_festivi.keys():
					self.constr_festivi_comandanti[vigile].SetCoefficient(self.var_festivi[festivo][gruppo], 1)

			#CONSTR: max 1 tra festivo e notti circostanti
			self.constr_festivi_notti_circostanti_vigile[vigile] = {}
			for festivo in self.var_festivi.keys():
				self.constr_festivi_notti_circostanti_vigile[vigile][festivo] = self.solver.Constraint(-self.solver.infinity(), 1, "constr_festivo_notte_consecutivi_vigile({})_festivo({})".format(vigile, festivo))
				self.constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(self.var_festivi[festivo][gruppo], 1)
				if vigile in self.var_notti[festivo].keys():
					self.constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(self.var_notti[festivo][vigile], 1)
				giorno_prima = festivo - 1
				if vigile in self.var_notti[giorno_prima].keys():
					self.constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(self.var_notti[giorno_prima][vigile], 1)

			#CONSTR: no servizi il giorno di compleanno
			compleanno = self.DB[vigile].get_compleanno_offset(data_inizio)
			self.constr_compleanno_vigile[vigile] = self.solver.Constraint(-self.solver.infinity(), 0, "constr_compleanno_vigile({})".format(vigile))
			if compleanno in self.var_notti.keys():
				if vigile in self.var_notti[compleanno].keys():
					self.constr_compleanno_vigile[vigile].SetCoefficient(self.var_notti[compleanno][vigile], 1)
			if compleanno in self.var_sabati.keys() and not self.DB[vigile].esente_sabati():
				self.constr_compleanno_vigile[vigile].SetCoefficient(self.var_sabati[compleanno][vigile], 1)
			if compleanno in self.var_festivi.keys() and gruppo != 0:
				self.constr_compleanno_vigile[vigile].SetCoefficient(self.var_festivi[compleanno][gruppo], 1)

			#VAR: somma servizi per vigile (ausiliaria)
			self.var_servizi_vigile[vigile] = self.solver.NumVar(0, self.solver.infinity(), "var_aux_sum_servizi_vigile({})".format(vigile))
			self.constr_servizi_vigile[vigile] = self.solver.Constraint(0, 0, "constr_somma_servizi_vigile({})".format(vigile))
			self.constr_servizi_vigile[vigile].SetCoefficient(self.var_servizi_vigile[vigile], -1)
			for giorno in range(len(self.var_notti.keys())):
				if vigile in self.var_notti[giorno].keys():
					self.constr_servizi_vigile[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1)
				if giorno in self.var_sabati.keys() and not self.DB[vigile].esente_sabati():
					self.constr_servizi_vigile[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
				if giorno in self.var_festivi.keys() and gruppo != 0:
					self.constr_servizi_vigile[vigile].SetCoefficient(self.var_festivi[giorno][gruppo], 1)

			#VAR: costo servizi per vigile (ausiliaria)
			self.var_cost_servizi_vigile[vigile] = self.solver.NumVar(0, self.solver.infinity(), "var_aux_cost_servizi_vigile({})".format(vigile))
			self.constr_cost_servizi_vigile[vigile] = self.solver.Constraint(0, 0, "constr_costo_servizi_vigile({})".format(vigile))
			self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_cost_servizi_vigile[vigile], -1)
			for giorno in range(len(self.var_notti.keys())):
				if vigile in self.var_notti[giorno].keys():
					if self.giorno_squadra[giorno] == self.DB[vigile].squadra or self.DB[vigile].squadra == 0:
						self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_notti[giorno][vigile], 1) # Notti di squadra contano 1
					else:
						self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_notti[giorno][vigile], 2.1) # Notti NON di squadra contano il doppio
				if giorno in self.var_sabati.keys() and not self.DB[vigile].esente_sabati():
					self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_sabati[giorno][vigile], 1)
				if giorno in self.var_festivi.keys() and gruppo != 0:
					self.constr_cost_servizi_vigile[vigile].SetCoefficient(self.var_festivi[giorno][gruppo], 1.01) # Base 1.01 per evitare di scambiare notti con festivi

		for i in range(len(self.vigili)):
			v1 = self.vigili[i]
			for j in range(i+1, len(self.vigili)):
				v2 = self.vigili[j]
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

		# OBJECTIVE
		objective = self.solver.Objective()
		#OBJ: minimizza le differenze tra servizi ed il costo totale dei servizi
		for var in self.var_differenza_servizi.values():
			objective.SetCoefficient(var, 1)
		for var in self.var_cost_servizi_vigile.values():
			objective.SetCoefficient(var, 100)
		objective.SetMinimization()

		print("Il modello ha {} variabili e {} vincoli.".format(self.solver.NumVariables(), self.solver.NumConstraints()))

		model_f = open("model.txt", "w")
		model_f.write(self.solver.ExportModelAsLpFormat(False))
		# model.write(solver.ExportModelAsMpsFormat(True, False))
		model_f.close()

	def solve(self, time_limit, verbose=False):
		#Solver Parameters
		if verbose:
			self.solver.EnableOutput()
		self.solver.SetNumThreads(2)
		# TIME LIMIT
		self.solver.SetTimeLimit(time_limit) #ms
		print("Risolvo il modello... (max {}s)".format(int(float(time_limit)/1000)))
		self.status = self.solver.Solve()

	def print_solution(self):
		if self.status == pywraplp.Solver.INFEASIBLE:
			print('Il problema non ammette soluzione.')
			print('Rilassa i vincoli e riprova.')
		else:
			if self.status == pywraplp.Solver.FEASIBLE:
				print("ATTENZIONE: la soluzione trovata potrebbe non essere ottimale.")
			print('Soluzione:')
			print('* Funzione obiettivo =', self.solver.Objective().Value())
			print("* Servizi per vigile:")
			for vigile in self.vigili:
				print("Vigile {}: {}".format(vigile, int(self.var_servizi_vigile[vigile].solution_value())))

	def save_solution(self):
		if self.status == pywraplp.Solver.INFEASIBLE:
			return
		else:
			# Salva i turni calcolati in un CSV
			out = open("./turni_{}.csv".format(self.anno), "w")
			out.write("#Data;Notte;Sabato/Festivo\n")
			for giorno in range(len(self.var_notti.keys())):
				data = self.data_inizio + dt.timedelta(giorno)
				line = str(data)+";"
				for vigile in self.var_notti[giorno].keys():
					if self.var_notti[giorno][vigile].solution_value() == 1:
						line += self.DB[vigile].nome+" "+self.DB[vigile].cognome+";"
				if giorno in self.var_sabati.keys():
					for vigile in self.vigili:
						if not self.DB[vigile].esente_sabati() and self.var_sabati[giorno][vigile].solution_value() == 1:
							line += self.DB[vigile].nome+" "+self.DB[vigile].cognome+";"
				elif giorno in self.var_festivi.keys():
					for vigile in self.vigili:
						if self.var_festivi[giorno][self.DB[vigile].gruppo_festivo].solution_value() == 1:
							line += self.DB[vigile].nome+" "+self.DB[vigile].cognome+";"
				out.write(line+"\n")
			# TODO Riporta i servizi speciali
			out.close()
