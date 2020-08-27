from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import math
import vvf_io

MAX_ASPIRANTI_AFFIANCATI = 3 #2
NUM_THREADS = 3

class TurnazioneVVF:
	#Collections
	giorno_SQUADRA = {}

	VAR_NOTTI = {}
	CONSTR_NOTTI = {}
	CONSTR_NOTTI_SETTIMANA_VIGILE = {}
	VAR_NOTTI_ASPIRANTI = {}
	CONSTR_NOTTI_ASPIRANTI = {}

	VAR_SABATI = {}
	CONSTR_SABATI = {}
	CONSTR_SABATI_VIGILE = {}
	CONSTR_SABATI_NOTTI_CIRCOSTANTi_VIGILE = {}
	CONSTR_sabato_saltato_VIGILE = {}
	VAR_SABATI_ASPIRANTI = {}
	CONSTR_SABATI_ASPIRANTI = {}

	VAR_FESTIVI = {}
	CONSTR_FESTIVI = {}
	CONSTR_FESTIVI_VIGILE = {}
	CONSTR_FESTIVI_NOTTI_CIRCOSTANTi_VIGILE = {}
	CONSTR_FESTIVI_SPAZIATI = {}
	CONSTR_compleanno_VIGILE = {}

	VAR_SERVIZI_VIGILE = {}
	CONSTR_SERVIZIi_VIGILE = {}
	VAR_COST_SERVIZI_VIGILE = {}
	CONSTR_COST_SERVIZI_VIGILE = {}
	VAR_DIFFERENZA_SERVIZI = {}
	CONSTR_DIFFERENZA_SERVIZI = {}

	CONSTR_NOTTI_GRADUATI = {}
	CONSTR_FESTIVI_GRADUATI = {}
	CONSTR_SERVIZI_ASPIRANTI_PASSAGGIO_VIGILI = {}
	CONSTR_NOTTI_MINIME_ASPIRANTI = {}
	CONSTR_SABATI_MINIMI_ASPIRANTI = {}

	CONSTR_EX_NOTTI_SOLO_SABATO = {}
	CONSTR_EX_NOTTI_SOLO_SABATO_FESTIVI = {}
	CONSTR_EX_NOTTI_SOLO_LUN = {}
	CONSTR_EX_NOTTI_SOLO_MAR_VEN = {}
	CONSTR_EX_SERVIZI_PRIMI_6_MESI = {}
	CONSTR_EX_NO_SERVIZI_MESE = {}

	DB = {}
	VIGILI = []
	VIGILI_SQUADRA = {}
	VIGILI_GRUPPI_FESTIVO = {}
	ANNO = 0
	DATA_INIZIO = 0
	DATA_FINE = 0
	PRINTED_SOLUTION = False

	#Model
	Solver = pywraplp.Solver('VVF_turni', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
	STATUS = -1

	def get_data(self, offset):
		return self.DATA_INIZIO + dt.timedelta(offset)

	def get_weekday(self, offset):
		return self.get_data(offset).weekday()

	def get_offset(self, data):
		return (data - self.DATA_INIZIO).days

	def __init__(self, data_inizio, data_fine, squadra_di_partenza,
				giorni_festivi_speciali, VIGILI_fn, riporti_fn, loose=False,
				compute_aspiranti=True, no_servizi_compleanno=True):
		print("Creo il modello...")
		self.DATA_INIZIO = data_inizio
		self.DATA_FINE = data_fine
		self.DB = vvf_io.read_csv_vigili(VIGILI_fn)
		self.DB = vvf_io.read_csv_riporti(self.DB, riporti_fn)
		self.DB = vvf_io.correggi_aspiranti(self.DB, data_inizio, data_fine)
		self.VIGILI = list(self.DB.keys())
		self.VIGILI_SQUADRA = {}
		self.VIGILI_GRUPPI_FESTIVO = {}
		for vigile in self.VIGILI:
			# Squadra
			if self.DB[vigile].SQUADRA == 0:
				continue
			elif self.DB[vigile].SQUADRA not in self.VIGILI_SQUADRA.keys():
				self.VIGILI_SQUADRA[self.DB[vigile].SQUADRA] = []
			self.VIGILI_SQUADRA[self.DB[vigile].SQUADRA].append(vigile)
			# Gruppo Festivo
			if self.DB[vigile].GRUPPO_FESTIVO == 0:
				continue
			elif self.DB[vigile].GRUPPO_FESTIVO not in self.VIGILI_GRUPPI_FESTIVO.keys():
				self.VIGILI_GRUPPI_FESTIVO[self.DB[vigile].GRUPPO_FESTIVO] = []
			self.VIGILI_GRUPPI_FESTIVO[self.DB[vigile].GRUPPO_FESTIVO].append(vigile)

		num_squadre = len(self.VIGILI_SQUADRA.keys())
		self.ANNO = self.DATA_INIZIO.year
		num_giorni = self.get_offset(self.DATA_FINE)
		giorno = 0
		curr_SQUADRA = squadra_di_partenza
		while giorno < num_giorni:
			for i in range(7):
				curr_giorno = giorno + i
				curr_data = self.get_data(curr_giorno)
				
				self.giorno_SQUADRA[curr_giorno] = curr_SQUADRA

				#VAR: VIGILI di SQUADRA candidati per la notte
				self.VAR_NOTTI[curr_giorno] = {}
				self.VAR_NOTTI_ASPIRANTI[curr_giorno] = {}
				for vigile in self.VIGILI:
					if not self.DB[vigile].EsenteNotti() and not self.DB[vigile].Aspirante() and (self.DB[vigile].SQUADRA == curr_SQUADRA or self.DB[vigile].SQUADRA == 0 or loose):
						self.VAR_NOTTI[curr_giorno][vigile] = self.Solver.IntVar(0, 1, "VAR_VIGILE({})_notte({})".format(vigile, curr_giorno))
					elif self.DB[vigile].Aspirante() and compute_aspiranti:
						self.VAR_NOTTI_ASPIRANTI[curr_giorno][vigile] = self.Solver.IntVar(0, 1, "VAR_Aspirante({})_notte({})".format(vigile, curr_giorno))
					
				#CONSTR: 1 vigile per notte
				self.CONSTR_NOTTI[curr_giorno] = self.Solver.Constraint(1, 1, "CONSTR_notte({})".format(curr_giorno))
				for var in self.VAR_NOTTI[curr_giorno].values():
					self.CONSTR_NOTTI[curr_giorno].SetCoefficient(var, 1)

				#CONSTR: aspiranti solo in presenza di graduati, max 2 aspiranti affiancati per notte
				if compute_aspiranti:
					self.CONSTR_NOTTI_ASPIRANTI[curr_giorno] = self.Solver.Constraint(0, self.Solver.infinity(), "CONSTR_NOTTI_ASPIRANTI({})".format(curr_giorno))
					for vigile in self.VIGILI:
						if self.DB[vigile].Graduato() and vigile in self.VAR_NOTTI[curr_giorno].keys():
							self.CONSTR_NOTTI_ASPIRANTI[curr_giorno].SetCoefficient(self.VAR_NOTTI[curr_giorno][vigile], MAX_ASPIRANTI_AFFIANCATI)
						elif self.DB[vigile].Aspirante():
							self.CONSTR_NOTTI_ASPIRANTI[curr_giorno].SetCoefficient(self.VAR_NOTTI_ASPIRANTI[curr_giorno][vigile], -1)

				#SABATO
				if curr_data.weekday() == 5 and curr_data not in giorni_festivi_speciali:

					#VAR: vigile candidati per il sabato
					self.VAR_SABATI[curr_giorno] = {}
					self.VAR_SABATI_ASPIRANTI[curr_giorno] = {}
					for vigile in self.VIGILI:
						if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].Aspirante():
							self.VAR_SABATI[curr_giorno][vigile] = self.Solver.IntVar(0, 1, "VAR_VIGILE({})_sabato({})".format(vigile, curr_giorno))
						elif self.DB[vigile].Aspirante() and compute_aspiranti:
							self.VAR_SABATI_ASPIRANTI[curr_giorno][vigile] = self.Solver.IntVar(0, 1, "VAR_Aspirante({})_sabato({})".format(vigile, curr_giorno))

					#CONSTR: 1 vigile per sabato
					self.CONSTR_SABATI[curr_giorno] = self.Solver.Constraint(1, 1, "CONSTR_sabato({})".format(curr_giorno))
					for vigile in self.VIGILI:
						if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].Aspirante():
							self.CONSTR_SABATI[curr_giorno].SetCoefficient(self.VAR_SABATI[curr_giorno][vigile], 1)

					#CONSTR: aspiranti solo in presenza di graduati, max 2 aspiranti affiancati per sabato
					if compute_aspiranti:
						self.CONSTR_SABATI_ASPIRANTI[curr_giorno] = self.Solver.Constraint(0, self.Solver.infinity(), "CONSTR_SABATI_ASPIRANTI({})".format(curr_giorno))
						for vigile in self.VIGILI:
							if self.DB[vigile].Graduato() and vigile in self.VAR_SABATI[curr_giorno].keys():
								self.CONSTR_SABATI_ASPIRANTI[curr_giorno].SetCoefficient(self.VAR_SABATI[curr_giorno][vigile], MAX_ASPIRANTI_AFFIANCATI)
							elif self.DB[vigile].Aspirante():
								self.CONSTR_SABATI_ASPIRANTI[curr_giorno].SetCoefficient(self.VAR_SABATI_ASPIRANTI[curr_giorno][vigile], -1)

				#FESTIVO
				if curr_data.weekday() == 6 or curr_data in giorni_festivi_speciali:
					
					#VAR: VIGILI candidati per il festivo
					self.VAR_FESTIVI[curr_giorno] = {}
					for gruppo in self.VIGILI_GRUPPI_FESTIVO.keys():
						self.VAR_FESTIVI[curr_giorno][gruppo] = self.Solver.IntVar(0, 1, "VAR_gruppo({})_festivo({})".format(gruppo, curr_giorno))
						
					#CONSTR: 1 gruppo festivo a festivo
					self.CONSTR_FESTIVI[curr_giorno] = self.Solver.Constraint(1, 1, "CONSTR_festivo({})".format(curr_giorno))
					for gruppo in self.VIGILI_GRUPPI_FESTIVO.keys():
						self.CONSTR_FESTIVI[curr_giorno].SetCoefficient(self.VAR_FESTIVI[curr_giorno][gruppo], 1)
					
			#CONSTR: max 1 notte per vigile a settimana
			settimana = int(giorno / 7)
			self.CONSTR_NOTTI_SETTIMANA_VIGILE[settimana] = {}
			for vigile in self.VIGILI:
				if not self.DB[vigile].EsenteNotti() and not self.DB[vigile].Aspirante() and (self.DB[vigile].SQUADRA == curr_SQUADRA or self.DB[vigile].SQUADRA == 0 or loose):
					self.CONSTR_NOTTI_SETTIMANA_VIGILE[settimana][vigile] = self.Solver.Constraint(-self.Solver.infinity(), 1, "CONSTR_una_notte_settimana({})_VIGILE({})".format(settimana, vigile))
					for i in range(7):
						curr_giorno = giorno + i
						self.CONSTR_NOTTI_SETTIMANA_VIGILE[settimana][vigile].SetCoefficient(self.VAR_NOTTI[curr_giorno][vigile], 1)

			curr_SQUADRA = (curr_SQUADRA % num_squadre) + 1
			giorno += 7

		for vigile in self.VIGILI:
			gruppo = self.DB[vigile].GRUPPO_FESTIVO
			
			if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].Aspirante():
				#CONSTR: max 1 sabato
				self.CONSTR_SABATI_VIGILE[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 1, "CONSTR_un_sabato_VIGILE({})".format(vigile))
				for sabato in self.VAR_SABATI.keys():
					self.CONSTR_SABATI_VIGILE[vigile].SetCoefficient(self.VAR_SABATI[sabato][vigile], 1)

				#CONSTR: max 1 tra venerdì notte, sabato e sabato notte
				if "NottiSoloSabato" not in self.DB[vigile].ECCEZIONI and "NottiSoloSabatoFestivi" not in self.DB[vigile].ECCEZIONI:
					self.CONSTR_SABATI_NOTTI_CIRCOSTANTi_VIGILE[vigile] = {}
					for sabato in self.VAR_SABATI.keys():
						self.CONSTR_SABATI_NOTTI_CIRCOSTANTi_VIGILE[vigile][sabato] = self.Solver.Constraint(-self.Solver.infinity(), 1, "CONSTR_sabato_notte_consecutivi_VIGILE({})_sabato({})".format(vigile, sabato))
						self.CONSTR_SABATI_NOTTI_CIRCOSTANTi_VIGILE[vigile][sabato].SetCoefficient(self.VAR_SABATI[sabato][vigile], 1)
						if vigile in self.VAR_NOTTI[sabato].keys():
							self.CONSTR_SABATI_NOTTI_CIRCOSTANTi_VIGILE[vigile][sabato].SetCoefficient(self.VAR_NOTTI[sabato][vigile], 1)
						venerdi = sabato - 1
						if vigile in self.VAR_NOTTI[venerdi].keys():
							self.CONSTR_SABATI_NOTTI_CIRCOSTANTi_VIGILE[vigile][sabato].SetCoefficient(self.VAR_NOTTI[venerdi][vigile], 1)

				#CONSTR: almeno 1 sabato se non fatto l'anno precedente
				#Escludi aspiranti che passano dall'obbligo, mal che vada lo fanno l'anno successivo
				if not self.DB[vigile].PASSATO_SABATI and not self.DB[vigile].ASPIRANTE_PASSA_A_VIGILE:
					self.CONSTR_sabato_saltato_VIGILE[vigile] = self.Solver.Constraint(1, self.Solver.infinity(), "CONSTR_sabato_saltato_VIGILE({})".format(vigile))
					for sabato in self.VAR_SABATI.keys():
						self.CONSTR_sabato_saltato_VIGILE[vigile].SetCoefficient(self.VAR_SABATI[sabato][vigile], 1)

			#CONSTR: max 1 tra festivo e NOTTI circostanti
			self.CONSTR_FESTIVI_NOTTI_CIRCOSTANTi_VIGILE[vigile] = {}
			for festivo in self.VAR_FESTIVI.keys():
				if "NottiSoloSabato" not in self.DB[vigile].ECCEZIONI and ( "NottiSoloSabatoFestivi" not in self.DB[vigile].ECCEZIONI or self.get_weekday(festivo) not in [5, 6]):
					self.CONSTR_FESTIVI_NOTTI_CIRCOSTANTi_VIGILE[vigile][festivo] = self.Solver.Constraint(-self.Solver.infinity(), 1, "CONSTR_festivo_notte_consecutivi_VIGILE({})_festivo({})".format(vigile, festivo))
					self.CONSTR_FESTIVI_NOTTI_CIRCOSTANTi_VIGILE[vigile][festivo].SetCoefficient(self.VAR_FESTIVI[festivo][gruppo], 1)
					if vigile in self.VAR_NOTTI[festivo].keys():
						self.CONSTR_FESTIVI_NOTTI_CIRCOSTANTi_VIGILE[vigile][festivo].SetCoefficient(self.VAR_NOTTI[festivo][vigile], 1)
					giorno_prima = festivo - 1
					if vigile in self.VAR_NOTTI[giorno_prima].keys():
						self.CONSTR_FESTIVI_NOTTI_CIRCOSTANTi_VIGILE[vigile][festivo].SetCoefficient(self.VAR_NOTTI[giorno_prima][vigile], 1)

			#CONSTR: spazia i FESTIVI di almeno 5 servizi per lato
			if gruppo not in self.CONSTR_FESTIVI_SPAZIATI.keys():
				self.CONSTR_FESTIVI_SPAZIATI[gruppo] = {}
				lista_FESTIVI = list(self.VAR_FESTIVI.keys())
				guardia = 5
				for i, festivo in enumerate(lista_FESTIVI):
				# for i in range (guardia, len(lista_FESTIVI)-guardia):
					self.CONSTR_FESTIVI_SPAZIATI[gruppo][i] = self.Solver.Constraint(-self.Solver.infinity(), 1, "CONSTR_FESTIVI_SPAZIATI_gruppo({})_festivo({})".format(gruppo, festivo))
					for j in range(max(0, i-guardia), min(i+guardia, len(lista_FESTIVI))):
						self.CONSTR_FESTIVI_SPAZIATI[gruppo][i].SetCoefficient(self.VAR_FESTIVI[lista_FESTIVI[j]][gruppo], 1)

			#CONSTR: max 5 FESTIVI l'anno
			#NOTA: aggiungi un minimo di 3 per "forzare" una distribuzione più equa
			if gruppo not in self.CONSTR_FESTIVI_VIGILE.keys():
				# self.CONSTR_FESTIVI_VIGILE[gruppo] = self.Solver.Constraint(-self.Solver.infinity(), 5, "CONSTR_FESTIVI_annuali_VIGILE({})".format(gruppo))
				self.CONSTR_FESTIVI_VIGILE[gruppo] = self.Solver.Constraint(3, 5, "CONSTR_FESTIVI_annuali_VIGILE({})".format(gruppo))
				for festivo in self.VAR_FESTIVI.keys():
					self.CONSTR_FESTIVI_VIGILE[gruppo].SetCoefficient(self.VAR_FESTIVI[festivo][gruppo], 1)

			#CONSTR: max 3 NOTTI per comandante e vice
			if self.DB[vigile].GRADO in ["Comandante", "Vicecomandante"]:
				self.CONSTR_NOTTI_GRADUATI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 3, "CONSTR_NOTTI_GRADUATI_comandanti({})".format(vigile))
				for giorno in range(len(self.VAR_NOTTI.keys())):
					self.CONSTR_NOTTI_GRADUATI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

			#CONSTR: max 3 FESTIVI per comandante e vice
			if self.DB[vigile].GRADO in ["Comandante", "Vicecomandante"]:
				self.CONSTR_FESTIVI_GRADUATI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 3, "CONSTR_FESTIVI_GRADUATI_comandanti({})".format(vigile))
				for festivo in self.VAR_FESTIVI.keys():
					self.CONSTR_FESTIVI_GRADUATI[vigile].SetCoefficient(self.VAR_FESTIVI[festivo][gruppo], 1)

			#CONSTR: max 5 NOTTI per capiplotone
			if self.DB[vigile].GRADO=="Capoplotone":
				self.CONSTR_NOTTI_GRADUATI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 5, "CONSTR_NOTTI_GRADUATI_capiplotone({})".format(vigile))
				for giorno in range(len(self.VAR_NOTTI.keys())):
					if vigile in self.VAR_NOTTI[giorno].keys():
						self.CONSTR_NOTTI_GRADUATI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

			#CONSTR: max 4 FESTIVI per direttivo e graduati
			if self.DB[vigile].GRADO in ["Capoplotone", "CapoSQUADRA", "Segretario", "Cassiere", "Magazziniere"]:
				self.CONSTR_FESTIVI_GRADUATI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 4, "CONSTR_FESTIVI_GRADUATI_direttivo_capisquadra({})".format(vigile))
				for festivo in self.VAR_FESTIVI.keys():
					self.CONSTR_FESTIVI_GRADUATI[vigile].SetCoefficient(self.VAR_FESTIVI[festivo][gruppo], 1)

			#CONSTR: max 6 NOTTI per capiSQUADRA
			if self.DB[vigile].GRADO=="CapoSQUADRA":
				self.CONSTR_NOTTI_GRADUATI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 6, "CONSTR_NOTTI_GRADUATI_capisquadra({})".format(vigile))
				for giorno in range(len(self.VAR_NOTTI.keys())):
					if vigile in self.VAR_NOTTI[giorno].keys():
						self.CONSTR_NOTTI_GRADUATI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

			#CONSTR: max 3 NOTTI per direttivo
			if self.DB[vigile].GRADO in ["Segretario", "Cassiere", "Magazziniere"]:
				self.CONSTR_NOTTI_GRADUATI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 3, "CONSTR_NOTTI_GRADUATI_direttivo({})".format(vigile))
				for giorno in range(len(self.VAR_NOTTI.keys())):
					if vigile in self.VAR_NOTTI[giorno].keys():
						self.CONSTR_NOTTI_GRADUATI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

			#CONSTR: max 6 NOTTI per resp. allievi e vicemagazziniere
			if self.DB[vigile].GRADO in ["Resp. Allievi", "Vicemagazziniere"]:
				self.CONSTR_NOTTI_GRADUATI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 6, "CONSTR_NOTTI_GRADUATI_respallie_vivicemagazziniere({})".format(vigile))
				for giorno in range(len(self.VAR_NOTTI.keys())):
					if vigile in self.VAR_NOTTI[giorno].keys():
						self.CONSTR_NOTTI_GRADUATI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

			#CONSTR: aspiranti che diventano VIGILI, no servizi prima del passaggio
			if self.DB[vigile].ASPIRANTE_PASSA_A_VIGILE:
				limite = self.get_offset(self.DB[vigile].DATA_PASSAGGIO_VIGILE)
				self.CONSTR_SERVIZI_ASPIRANTI_PASSAGGIO_VIGILI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_SERVIZI_ASPIRANTI_PASSAGGIO_VIGILI({})".format(vigile))
				for giorno in range(limite):
					if vigile in self.VAR_NOTTI[giorno].keys():
						self.CONSTR_SERVIZI_ASPIRANTI_PASSAGGIO_VIGILI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)
					if giorno in self.VAR_SABATI.keys():
						self.CONSTR_SERVIZI_ASPIRANTI_PASSAGGIO_VIGILI[vigile].SetCoefficient(self.VAR_SABATI[giorno][vigile], 1)
					#No FESTIVI, li fa comunque
					# if giorno in self.VAR_FESTIVI.keys():
						# self.CONSTR_SERVIZI_ASPIRANTI_PASSAGGIO_VIGILI[vigile].SetCoefficient(self.VAR_FESTIVI[giorno][gruppo], 1)

			#CONSTR: 15 NOTTI per aspirante
			if self.DB[vigile].Aspirante() and compute_aspiranti:
				self.CONSTR_NOTTI_MINIME_ASPIRANTI[vigile] = self.Solver.Constraint(15, self.Solver.infinity(), "CONSTR_NOTTI_MINIME_ASPIRANTI({})".format(vigile))
				for notte in self.VAR_NOTTI_ASPIRANTI.keys():
					self.CONSTR_NOTTI_MINIME_ASPIRANTI[vigile].SetCoefficient(self.VAR_NOTTI_ASPIRANTI[notte][vigile], 1)

			#CONSTR: 1 sabato per aspirante
			if self.DB[vigile].Aspirante() and compute_aspiranti:
				self.CONSTR_SABATI_MINIMI_ASPIRANTI[vigile] = self.Solver.Constraint(1, 1, "CONSTR_SABATI_MINIMI_ASPIRANTI({})".format(vigile))
				for sabato in self.VAR_SABATI_ASPIRANTI.keys():
					self.CONSTR_SABATI_MINIMI_ASPIRANTI[vigile].SetCoefficient(self.VAR_SABATI_ASPIRANTI[sabato][vigile], 1)

			#ECCEZIONI alle regole usuali
			if len(self.DB[vigile].ECCEZIONI) > 0:

				#CONSTR_EX: NOTTI solo il sabato
				if "NottiSoloSabato" in self.DB[vigile].ECCEZIONI:
					self.CONSTR_EX_NOTTI_SOLO_SABATO[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_EX_NOTTI_SOLO_SABATO_VIGILE({})".format(vigile))
					for giorno in self.VAR_NOTTI.keys():
						if vigile in self.VAR_NOTTI[giorno] and self.get_weekday(giorno) != 5:
							self.CONSTR_EX_NOTTI_SOLO_SABATO[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

				#CONSTR_EX: NOTTI solo il sabato o FESTIVI
				if "NottiSoloSabatoFestivi" in self.DB[vigile].ECCEZIONI:
					self.CONSTR_EX_NOTTI_SOLO_SABATO_FESTIVI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_EX_NOTTI_SOLO_SABATO_FESTIVI_VIGILE({})".format(vigile))
					for giorno in self.VAR_NOTTI.keys():
						if vigile in self.VAR_NOTTI[giorno] and self.get_weekday(giorno) != 5 and giorno not in self.VAR_FESTIVI.keys():
							self.CONSTR_EX_NOTTI_SOLO_SABATO_FESTIVI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

				#CONSTR_EX: NOTTI solo il lunedì
				if "NottiSoloLun" in self.DB[vigile].ECCEZIONI:
					self.CONSTR_EX_NOTTI_SOLO_LUN[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_EX_NOTTI_SOLO_LUN_VIGILE({})".format(vigile))
					for giorno in self.VAR_NOTTI.keys():
						if vigile in self.VAR_NOTTI[giorno] and self.get_weekday(giorno) != 0:
							self.CONSTR_EX_NOTTI_SOLO_LUN[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

				#CONSTR_EX: NOTTI solo il martedì o venerdì
				if "NottiSoloMarVen" in self.DB[vigile].ECCEZIONI:
					self.CONSTR_EX_NOTTI_SOLO_MAR_VEN[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_EX_NOTTI_SOLO_MAR_VEN_VIGILE({})".format(vigile))
					for giorno in self.VAR_NOTTI.keys():
						if vigile in self.VAR_NOTTI[giorno] and self.get_weekday(giorno) not in [1, 4]:
							self.CONSTR_EX_NOTTI_SOLO_MAR_VEN[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)

				#CONSTR_EX: servizi solo i primi 6 mesi
				if "ServiziSoloPrimi6Mesi" in self.DB[vigile].ECCEZIONI:
					self.CONSTR_EX_SERVIZI_PRIMI_6_MESI[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_EX_SERVIZI_PRIMI_6_MESI_VIGILE({})".format(vigile))
					limite = self.get_offset(dt.date(self.ANNO, 6, 30))
					for giorno in range(limite, num_giorni):
						if vigile in self.VAR_NOTTI[giorno]:
							self.CONSTR_EX_SERVIZI_PRIMI_6_MESI[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)
						if giorno in self.VAR_SABATI.keys():
							if vigile in self.VAR_SABATI[giorno]:
								self.CONSTR_EX_SERVIZI_PRIMI_6_MESI[vigile].SetCoefficient(self.VAR_SABATI[giorno][vigile], 1)
						elif giorno in self.VAR_FESTIVI.keys():
							self.CONSTR_EX_SERVIZI_PRIMI_6_MESI[vigile].SetCoefficient(self.VAR_FESTIVI[giorno][gruppo], 1)

				#CONSTR_EX: no servizi specifico mese
				mesi_da_saltare = []
				for e in self.DB[vigile].ECCEZIONI:
					if "NoServiziMese" in e:
						mesi_da_saltare.append(int(e[len("NoServiziMese"):]))
				if len(mesi_da_saltare) > 0:
					self.CONSTR_EX_NO_SERVIZI_MESE[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_EX_NO_SERVIZI_MESE_VIGILE({})".format(vigile))
					for giorno in self.VAR_NOTTI[giorno]:
						if self.get_data(giorno).month in mesi_da_saltare:
							if vigile in self.VAR_NOTTI[giorno]:
								self.CONSTR_EX_NO_SERVIZI_MESE[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)
							if giorno in self.VAR_SABATI.keys():
								if vigile in self.VAR_SABATI[giorno]:
									self.CONSTR_EX_NO_SERVIZI_MESE[vigile].SetCoefficient(self.VAR_SABATI[giorno][vigile], 1)
							elif giorno in self.VAR_FESTIVI.keys():
								self.CONSTR_EX_NO_SERVIZI_MESE[vigile].SetCoefficient(self.VAR_FESTIVI[giorno][gruppo], 1)

			#CONSTR: no servizi il giorno di compleanno
			if no_servizi_compleanno:
				compleanno = self.DB[vigile].OffsetCompleanno(self.DATA_INIZIO)
				self.CONSTR_compleanno_VIGILE[vigile] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_compleanno_VIGILE({})".format(vigile))
				if compleanno in self.VAR_NOTTI.keys():
					if vigile in self.VAR_NOTTI[compleanno].keys():
						self.CONSTR_compleanno_VIGILE[vigile].SetCoefficient(self.VAR_NOTTI[compleanno][vigile], 1)
				if compleanno in self.VAR_SABATI.keys() and not (self.DB[vigile].EsenteSabati() or self.DB[vigile].Aspirante()):
					self.CONSTR_compleanno_VIGILE[vigile].SetCoefficient(self.VAR_SABATI[compleanno][vigile], 1)
				if compleanno in self.VAR_FESTIVI.keys() and gruppo != 0:
					self.CONSTR_compleanno_VIGILE[vigile].SetCoefficient(self.VAR_FESTIVI[compleanno][gruppo], 1)

			#VAR: somma servizi per vigile (ausiliaria)
			self.VAR_SERVIZI_VIGILE[vigile] = self.Solver.NumVar(0, self.Solver.infinity(), "VAR_aux_sum_servizi_VIGILE({})".format(vigile))
			#CONSTR: implementa quanto sopra
			self.CONSTR_SERVIZIi_VIGILE[vigile] = self.Solver.Constraint(0, 0, "CONSTR_somma_servizi_VIGILE({})".format(vigile))
			self.CONSTR_SERVIZIi_VIGILE[vigile].SetCoefficient(self.VAR_SERVIZI_VIGILE[vigile], -1)
			for giorno in range(len(self.VAR_NOTTI.keys())):
				if vigile in self.VAR_NOTTI[giorno].keys():
					self.CONSTR_SERVIZIi_VIGILE[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1)
				elif vigile in self.VAR_NOTTI_ASPIRANTI[giorno].keys() and compute_aspiranti:
					self.CONSTR_SERVIZIi_VIGILE[vigile].SetCoefficient(self.VAR_NOTTI_ASPIRANTI[giorno][vigile], 1)
				if giorno in self.VAR_SABATI.keys():
					if vigile in self.VAR_SABATI[giorno].keys():
						self.CONSTR_SERVIZIi_VIGILE[vigile].SetCoefficient(self.VAR_SABATI[giorno][vigile], 1)
					elif vigile in self.VAR_SABATI_ASPIRANTI[giorno].keys() and compute_aspiranti:
						self.CONSTR_SERVIZIi_VIGILE[vigile].SetCoefficient(self.VAR_SABATI_ASPIRANTI[giorno][vigile], 1)
				if giorno in self.VAR_FESTIVI.keys() and gruppo != 0:
					self.CONSTR_SERVIZIi_VIGILE[vigile].SetCoefficient(self.VAR_FESTIVI[giorno][gruppo], 1.01) # 1.01 per favorire l'assegnazione dello stesso numero di FESTIVI

			#VAR: costo servizi per vigile (ausiliaria)
			self.VAR_COST_SERVIZI_VIGILE[vigile] = self.Solver.NumVar(0, self.Solver.infinity(), "VAR_aux_COST_SERVIZI_VIGILE({})".format(vigile))
			#CONSTR: implementa quanto sopra
			#Il target è 0 se il vigile non ha fatto più servizi della media
			self.CONSTR_COST_SERVIZI_VIGILE[vigile] = self.Solver.Constraint(-2*self.DB[vigile].PASSATO_SERVIZI_EXTRA, -2*self.DB[vigile].PASSATO_SERVIZI_EXTRA, "CONSTR_costo_servizi_VIGILE({})".format(vigile))
			self.CONSTR_COST_SERVIZI_VIGILE[vigile].SetCoefficient(self.VAR_COST_SERVIZI_VIGILE[vigile], -1)
			mul_NOTTI = 1
			mul_SABATI = 1
			if self.DB[vigile].ESENTE_CP:
				mul_NOTTI *= 10.0/15.0
			if self.DB[vigile].ASPIRANTE_PASSA_A_VIGILE:
				mul_NOTTI *= float(num_giorni)/(num_giorni - self.get_offset(self.DB[vigile].DATA_PASSAGGIO_VIGILE))
				mul_SABATI *= float(num_giorni)/(num_giorni - self.get_offset(self.DB[vigile].DATA_PASSAGGIO_VIGILE))
			compleanno = self.DB[vigile].OffsetCompleanno(self.DATA_INIZIO)
			for giorno in range(len(self.VAR_NOTTI.keys())):
				mul_compleanno = 1
				if giorno == compleanno:
					mul_compleanno = 2
				if vigile in self.VAR_NOTTI[giorno].keys():
					if self.giorno_SQUADRA[giorno] == self.DB[vigile].SQUADRA or self.DB[vigile].SQUADRA == 0:
						self.CONSTR_COST_SERVIZI_VIGILE[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 1 * mul_compleanno * mul_NOTTI) # Notti di SQUADRA contano 1
					else:
						self.CONSTR_COST_SERVIZI_VIGILE[vigile].SetCoefficient(self.VAR_NOTTI[giorno][vigile], 2.1 * mul_compleanno * mul_NOTTI) # Notti NON di SQUADRA contano il doppio
				elif vigile in self.VAR_NOTTI_ASPIRANTI[giorno].keys() and compute_aspiranti:
					self.CONSTR_COST_SERVIZI_VIGILE[vigile].SetCoefficient(self.VAR_NOTTI_ASPIRANTI[giorno][vigile], 1 * mul_compleanno)
				if giorno in self.VAR_SABATI.keys():
					if vigile in self.VAR_SABATI[giorno].keys():
						self.CONSTR_COST_SERVIZI_VIGILE[vigile].SetCoefficient(self.VAR_SABATI[giorno][vigile], 1 * mul_compleanno * mul_SABATI)
					elif vigile in self.VAR_SABATI_ASPIRANTI[giorno].keys() and compute_aspiranti:
						self.CONSTR_COST_SERVIZI_VIGILE[vigile].SetCoefficient(self.VAR_SABATI_ASPIRANTI[giorno][vigile], 1 * mul_compleanno)
				if giorno in self.VAR_FESTIVI.keys() and gruppo != 0:
					self.CONSTR_COST_SERVIZI_VIGILE[vigile].SetCoefficient(self.VAR_FESTIVI[giorno][gruppo], 1 * mul_compleanno)

		for i in range(len(self.VIGILI)):
			v1 = self.VIGILI[i]
			for j in range(i+1, len(self.VIGILI)):
				v2 = self.VIGILI[j]
				#VAR: differenza numero servizi tra due VIGILI (ausiliaria)
				self.VAR_DIFFERENZA_SERVIZI[(v1, v2)] = self.Solver.NumVar(-self.Solver.infinity(), self.Solver.infinity(), "VAR_aux_diff_servizi({},{})".format(v1, v2))
				#CONSTR: implementa quanto sopra
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '+')] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_diff_servizi_plus_VIGILI({},{})".format(v1, v2))
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '+')].SetCoefficient(self.VAR_DIFFERENZA_SERVIZI[(v1, v2)], -1)
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '+')].SetCoefficient(self.VAR_SERVIZI_VIGILE[v1], 1)
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '+')].SetCoefficient(self.VAR_SERVIZI_VIGILE[v2], -1)
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '-')] = self.Solver.Constraint(-self.Solver.infinity(), 0, "CONSTR_diff_servizi_minus_VIGILI({},{})".format(v1, v2))
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '-')].SetCoefficient(self.VAR_DIFFERENZA_SERVIZI[(v1, v2)], -1)
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '-')].SetCoefficient(self.VAR_SERVIZI_VIGILE[v1], -1)
				self.CONSTR_DIFFERENZA_SERVIZI[(v1, v2, '-')].SetCoefficient(self.VAR_SERVIZI_VIGILE[v2], 1)

		# OBJECTIVE
		objective = self.Solver.Objective()
		#OBJ: minimizza le differenze tra servizi ed il costo totale dei servizi
		for var in self.VAR_DIFFERENZA_SERVIZI.values():
			objective.SetCoefficient(var, 1)
		for var in self.VAR_COST_SERVIZI_VIGILE.values():
			objective.SetCoefficient(var, (len(self.VIGILI) - 1))
		objective.SetMinimization()

		print("Il modello ha {} variabili e {} vincoli.".format(self.Solver.NumVariables(), self.Solver.NumConstraints()))

		model_f = open("model.txt", "w")
		model_f.write(self.Solver.ExportModelAsLpFormat(False))
		# model.write(Solver.ExportModelAsMpsFormat(True, False))
		model_f.close()

	def Solve(self, time_limit, verbose=False):
		#Solver Parameters
		if verbose:
			self.Solver.EnableOutput()
		self.Solver.SetNumThreads(NUM_THREADS)
		self.Solver.SetTimeLimit(time_limit) #ms
		print("Risolvo il modello... (max {}s)".format(int(float(time_limit)/1000)))
		self.STATUS = self.Solver.Solve()

	def PrintSolution(self):
		self.PRINTED_SOLUTION = True
		if self.STATUS == pywraplp.Solver.INFEASIBLE:
			print('Il problema non ammette soluzione.')
			print('Rilassa i vincoli e riprova.')
		else:
			if self.STATUS == pywraplp.Solver.FEASIBLE:
				print("ATTENZIONE: la soluzione trovata potrebbe non essere ottimale.")
			print('Soluzione:')
			print('* Funzione obiettivo: ', self.Solver.Objective().Value())
			print("* Servizi per vigile:")
			for vigile in self.VIGILI:
				for giorno in self.VAR_NOTTI.keys():
					if vigile in self.VAR_NOTTI[giorno].keys():
						self.DB[vigile].NOTTI += int(self.VAR_NOTTI[giorno][vigile].solution_value())
				for giorno in self.VAR_SABATI.keys():
					if vigile in self.VAR_SABATI[giorno].keys():
						self.DB[vigile].SABATI += int(self.VAR_SABATI[giorno][vigile].solution_value())
				for giorno in self.VAR_FESTIVI.keys():
					gruppo = self.DB[vigile].GRUPPO_FESTIVO
					if gruppo in self.VAR_FESTIVI[giorno].keys():
						self.DB[vigile].FESTIVI += int(self.VAR_FESTIVI[giorno][gruppo].solution_value())
				line = "Vigile {} ({} {}, {}".format(vigile, self.DB[vigile].NOME, self.DB[vigile].COGNOME, self.DB[vigile].GRADO)
				if self.DB[vigile].ASPIRANTE_PASSA_A_VIGILE:
					line += "*"
				line += "): {}".format(int(self.VAR_SERVIZI_VIGILE[vigile].solution_value()))
				line += "\n\tNotti: {}\n\tSabati: {}\n\tFestivi: {}".format(self.DB[vigile].NOTTI, self.DB[vigile].SABATI, self.DB[vigile].FESTIVI)
				print(line)

	def SaveSolution(self):
		if not self.PRINTED_SOLUTION:
			self.PrintSolution() #Necessaria per calcolare i numeri di servizi di ogni vigile
		if self.STATUS == pywraplp.Solver.INFEASIBLE:
			return
		else:
			# Salva i turni calcolati in un CSV
			out = open("./turni_{}.csv".format(self.ANNO), "w")
			out.write("#Data;Notte;Sabato/Festivo;;;;Affiancamento\n")
			for giorno in range(len(self.VAR_NOTTI.keys())):
				data = self.DATA_INIZIO + dt.timedelta(giorno)
				line = str(data)+";"
				for vigile in self.VAR_NOTTI[giorno].keys():
					if self.VAR_NOTTI[giorno][vigile].solution_value() == 1:
						line += self.DB[vigile].NOME+" "+self.DB[vigile].COGNOME+";"
				if giorno in self.VAR_SABATI.keys():
					for vigile in self.VIGILI:
						if not self.DB[vigile].EsenteSabati() and not self.DB[vigile].Aspirante() and self.VAR_SABATI[giorno][vigile].solution_value() == 1:
							line += self.DB[vigile].NOME+" "+self.DB[vigile].COGNOME+";"
					for aspirante in self.VAR_SABATI_ASPIRANTI[giorno].keys():
						if self.VAR_SABATI_ASPIRANTI[giorno][aspirante].solution_value() == 1:
							line += self.DB[aspirante].NOME+" "+self.DB[aspirante].COGNOME+";"
					line += ";" * (4 - len(line.split(";")))
				elif giorno in self.VAR_FESTIVI.keys():
					for vigile in self.VIGILI:
						if self.VAR_FESTIVI[giorno][self.DB[vigile].GRUPPO_FESTIVO].solution_value() == 1:
							line += self.DB[vigile].NOME+" "+self.DB[vigile].COGNOME+";"
					line += ";" * (4 - len(line.split(";")))
				else:
					line += ";;;;"
				for aspirante in self.VAR_NOTTI_ASPIRANTI[giorno].keys():
					if self.VAR_NOTTI_ASPIRANTI[giorno][aspirante].solution_value() == 1 and compute_aspiranti:
						line += self.DB[aspirante].NOME+" "+self.DB[aspirante].COGNOME+";"
				out.write(line+"\n")
			out.close()
			# Calcola il numero medio di servizi svolti dai VIGILI senza vincoli
			s = 0
			i = 0
			for vigile in self.VIGILI:
				if (
					self.DB[vigile].GRADO == "Vigile" #Escludi altri gradi che hanno limitazioni
					and not self.DB[vigile].ESENTE_CP #Gli esenti fanno più servizi
					and self.DB[vigile].ECCEZIONI == ['']
					):
					s += self.DB[vigile].NumeroServizi()
					i += 1
			media_servizi = float(s)/i
			# Riporta il numero di servizi extra ed i servizi speciali
			out = open("./riporti_{}.csv".format(self.ANNO), "w")
			out.write("#Vigile;FattoServiziExtra;FattoSabato;FattoServiziOnerosi\n")
			for vigile in self.VIGILI:
				out.write("{};".format(vigile))
				servizi_extra = 0
				if (
					self.DB[vigile].GRADO == "Vigile" #Escludi altri gradi che hanno limitazioni
					and not self.DB[vigile].ESENTE_CP #Gli esenti fanno più servizi
					and self.DB[vigile].ECCEZIONI == ['']
					):
					servizi_extra = math.ceil(self.DB[vigile].NumeroServizi() - media_servizi)
				out.write("{};".format(servizi_extra))
				out.write("{};".format(self.DB[vigile].SABATI))
				out.write("{}\n".format(0)) #TODO
			out.close()