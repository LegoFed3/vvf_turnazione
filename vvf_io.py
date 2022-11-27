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
	# Neo-assunti
	"NeoAssunto",
	"DaTrasferimento",
	# Esenzioni
	"Aspettativa",
	# "EsenteCP",
	"EsenteNotti",
	"EsenteSabati",
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
for i in range(1, 12+1):
	_ECCEZZIONI_VALIDE.append(f"NoNottiMese{i}")
	_ECCEZZIONI_VALIDE.append(f"NoServiziMese{i}")
	_ECCEZZIONI_VALIDE.append(f"LimiteNotti{i}")
	_ECCEZZIONI_VALIDE.append(f"ExtraNotti{i}")
	_ECCEZZIONI_VALIDE.append(f"ExtraSabati{i}")


class Vigile:
	id = 0
	nome = ""
	cognome = ""
	data_di_nascita = dt.date(1900, 1, 1)
	grado = "Vigile"
	squadre = []
	gruppo_festivo = 0
	eccezioni = set()
	notti = 0
	sabati = 0
	festivi = 0
	capodanno = 0
	festivi_onerosi = 0
	passato_festivi_onerosi = [0] * 10
	passato_sabati = [0] * 10
	passato_servizi_extra = 0
	passato_capodanni = 0
	notti_base = 9.0
	sabati_base = 1.0
	esente_cp = False
	mesi_da_vigile = 12
	notti_non_standard = False

	def __init__(self, id_vigile, params):
		self.id = id_vigile
		self.nome = params[1]
		self.cognome = params[2]
		self.data_di_nascita = dt.datetime.strptime(params[3], '%d/%m/%Y').date()
		self.grado = params[4]
		self.squadre = list(map(int, params[5].split(",")))
		self.gruppo_festivo = int(params[6])
		self.eccezioni = set(params[7].strip(" ").split(","))
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
			if "ExtraNotti" in e:
				self.notti_non_standard = True
		if "Aspettativa" in self.eccezioni and self.gruppo_festivo != 0:
			print(
				"ATTENZIONE: il vigile {} è in aspettativa ma è assegnato al gruppo festivo {}! Ignoro il gruppo festivo.".format(
					self.id, self.gruppo_festivo))
			self.gruppo_festivo = 0
		if "Aspettativa" in self.eccezioni and self.squadre != [0]:
			print("ATTENZIONE: il vigile {} è in aspettativa ma è assegnato alla squadra {}! Ignoro la squadra.".format(
				self.id, self.squadre))
			self.squadre = [0]

		# Coefficienti notti e sabati
		if self.grado == "Comandante":
			self.notti_base = 3.0
			self.sabati_base = 0.5
			self.notti_non_standard = True
		elif self.grado == "Vicecomandante":
			self.notti_base = 4.0
			self.sabati_base = 0.5
			self.notti_non_standard = True
		elif self.grado in ["Capoplotone", "Caposquadra"]:
			self.notti_base = 7.0
			self.notti_non_standard = True
		if (
				"Segretario" in self.eccezioni
				or "Cassiere" in self.eccezioni
				or "Magazziniere" in self.eccezioni
				or "Vicemagazziniere" in self.eccezioni
				or "Resp. Allievi" in self.eccezioni
		):
			self.notti_base = min(self.notti_base, 5.0)
			self.notti_non_standard = True
		if "DaTrasferimento" in self.eccezioni or "NeoAssunto" in self.eccezioni:
			self.notti_base = max(self.notti_base, 12.0)
			self.notti_non_standard = True
		# if "EsenteCP" in self.eccezioni:
		# self.notti_base = max(self.notti_base, 15.0)
		# self.notti_non_standard = True

		self.coeff_notti = 9.0 / self.notti_base
		if "LimiteNotti" in self.eccezioni:
			self.coeff_notti = 0.01  # Ignora pesi, assegnale fino a questo limite
			self.notti_non_standard = True
		self.coeff_sabati = 1.1 / self.sabati_base  # Per favorire assegnazione stesso numero

	def __str__(self):  # Called by print()
		s = "{:03d} {}".format(self.id, self.grado)
		if self.neoAssunto():
			s += "*"
		return s + " {} {}".format(self.nome, self.cognome)

	def __repr__(self):
		return self.__str__()

	def esenteServizi(self):
		return (self.grado in ["Ispettore", "Presidente", "Complemento"]
				or "Aspettativa" in self.eccezioni)

	def esenteNotti(self):
		return (self.esenteServizi()
				or self.grado == "Aspirante"
				or self.grado == "Complemento"
				or "EsenteNotti" in self.eccezioni
				or "Aspettativa" in self.eccezioni)

	def esenteSabati(self):
		return (self.esenteServizi()
				or self.grado == "Aspirante"
				or self.grado == "Complemento"
				or "Aspettativa" in self.eccezioni
				or "EsenteSabati" in self.eccezioni)

	def esenteFestivi(self):
		return (self.esenteServizi()
				or self.gruppo_festivo == 0
				or "Aspettativa" in self.eccezioni)

	def extraSabati(self):
		res = 0
		for e in self.eccezioni:
			if "ExtraSabati" in e:
				res = max(res, int(e[len("ExtraSabati"):]))
		return res

	def extraNotti(self):
		res = 0
		for e in self.eccezioni:
			if "ExtraNotti" in e:
				res = max(res, int(e[len("ExtraNotti"):]))
		return res

	def neoAssunto(self):
		return "NeoAssunto" in self.eccezioni or "DaTrasferimento" in self.eccezioni

	# def esenteCP(self):
	# return "EsenteCP" in self.eccezioni

	def graduato(self):
		return self.grado in ["Comandante", "Vicecomandante", "Capoplotone", "Caposquadra"]

	def altreCariche(self):
		return ("Segretario" in self.eccezioni
				or "Cassiere" in self.eccezioni
				or "Magazziniere" in self.eccezioni
				or "Vicemagazziniere" in self.eccezioni
				or "Resp. Allievi" in self.eccezioni)

	def offsetCompleanno(self, data_inizio):
		if (
				self.data_di_nascita.month <= data_inizio.month
				and self.data_di_nascita.day < data_inizio.day
		):
			compleanno = dt.date(data_inizio.year + 1, self.data_di_nascita.month, self.data_di_nascita.day)
		else:
			compleanno = dt.date(data_inizio.year, self.data_di_nascita.month, self.data_di_nascita.day)
		offset = (compleanno - data_inizio).days
		return offset

	def numeroServizi(self):
		return self.notti + self.sabati + self.festivi


def read_csv_vigili(filename):
	db = {}
	if not os.path.isfile(filename):
		print(f"ERRORE: il file '{filename}' che descrive i vigili non esiste!")
		print("\tImpossibile continuare senza.")
		exit(-1)
	df = pd.read_csv(filename, sep=";", dtype=str, keep_default_na=False, usecols=range(8))
	for idx, row in df.iterrows():
		if len(row) == 0:
			continue
		id_vigile = int(row[0])
		db[id_vigile] = Vigile(id_vigile, row.values)
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
