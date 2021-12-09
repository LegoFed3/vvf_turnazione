import datetime as dt
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
	"NoNottiMese1",
	"NoNottiMese2",
	"NoNottiMese3",
	"NoNottiMese4",
	"NoNottiMese5",
	"NoNottiMese6",
	"NoNottiMese7",
	"NoNottiMese8",
	"NoNottiMese9",
	"NoNottiMese10",
	"NoNottiMese11",
	"NoNottiMese12",
	"NoNottiMese1",
	"NoNottiMese2",
	"NoNottiMese3",
	"NoNottiMese4",
	"NoNottiMese5",
	"NoNottiMese6",
	"NoNottiMese7",
	"NoNottiMese8",
	"NoNottiMese9",
	"NoNottiMese10",
	"NoNottiMese11",
	"NoNottiMese12",
	"NoServiziMese1",
	"NoServiziMese2",
	"NoServiziMese3",
	"NoServiziMese4",
	"NoServiziMese5",
	"NoServiziMese6",
	"NoServiziMese7",
	"NoServiziMese8",
	"NoServiziMese9",
	"NoServiziMese10",
	"NoServiziMese11",
	"NoServiziMese12",
	"NottiAncheFuoriSettimana",
	"FestiviComunque",
	"LimiteNotti1",
	"LimiteNotti2",
	"LimiteNotti3",
	"LimiteNotti4",
	"LimiteNotti5",
	"LimiteNotti6",
	"LimiteNotti7",
	"LimiteNotti8",
	"LimiteNotti9",
	"LimiteNotti10",
	"ExtraNotti1",
	"ExtraNotti2",
	"ExtraNotti3",
	"ExtraNotti4",
	"ExtraNotti5",
	"ExtraNotti6",
	"ExtraNotti7",
	"ExtraNotti8",
	"ExtraSabati1",
	"ExtraSabati2",
	]

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
	passato_festivi_onerosi = [0]*10
	passato_sabati = [0]*10
	passato_servizi_extra = 0
	passato_capodanni = 0
	notti_base = 9.0
	sabati_base = 1.0
	esente_cp = False
	mesi_da_vigile = 12
	notti_non_standard = False

	def __init__(self, *args):
		self.id = int(args[0][0])
		self.nome = args[0][1]
		self.cognome = args[0][2]
		self.data_di_nascita = dt.datetime.strptime(args[0][3], '%d/%m/%Y').date()
		self.grado = args[0][4]
		self.squadre = list(map(int, args[0][5].split(",")))
		self.gruppo_festivo = int(args[0][6])
		self.eccezioni = set(args[0][7].strip(" ").split(","))
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
			print("ATTENZIONE: il vigile {} è in aspettativa ma è assegnato al gruppo festivo {}! Ignoro il gruppo festivo.".format(self.id, self.gruppo_festivo))
			self.gruppo_festivo = 0
		if "Aspettativa" in self.eccezioni and self.squadre != [0]:
			print("ATTENZIONE: il vigile {} è in aspettativa ma è assegnato alla squadra {}! Ignoro la squadra.".format(self.id, self.squadre))
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
			self.coeff_notti = 0.01 # Ignora pesi, assegnale fino a questo limite
			self.notti_non_standard = True
		self.coeff_sabati = 1.1 / self.sabati_base # Per favorire assegnazione stesso numero

	def __str__(self): # Called by print()
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
		print("ERRORE: il file '{}' che descrive i vigili non esiste!".format(filename))
		print("\tImpossibile continuare senza.")
		exit(-1)
	fi = open(filename, "r")
	for line in fi:
		if line[0] == "#":
			continue
		else:
			line = line.strip("\n\r").split(";")
			# line = list(filter(lambda x: x != '', line))
			if len(line) > 0:
				db[int(line[0])] = Vigile(line[0:])
	fi.close()
	return db

def read_csv_riporti(db, filename):
	if not os.path.isfile(filename):
		print("ATTENZIONE: il file '{}' che descrive i riporti dello scorso anno non esiste!".format(filename))
		print("\tContinuo senza.")
		return db
	fi = open(filename, "r")
	for line in fi:
		if line[0] == "#":
			continue
		else:
			line = line.strip("\n\r").split(";")
			if len(line) > 0:
				id = int(line[0])
				if id in db.keys():
					db[id].passato_servizi_extra = int(line[1])
					db[id].passato_capodanni = int(line[2])
					db[id].passato_sabati = list(map(lambda x: int(x), line[3:13]))
					db[id].passato_festivi_onerosi = list(map(lambda x: int(x), line[13:23]))
	fi.close()
	return db
