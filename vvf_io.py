import datetime as dt
import os
import argparse

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
	"EsenteCP",
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
	data_passaggio_vigile = dt.date(1900, 1, 1)
	grado = "Vigile"
	squadre = []
	gruppo_festivo = 0
	eccezioni = set()
	notti = 0
	sabati = 0
	festivi = 0
	notti_base = 9.0
	sabati_base = 1.0
	capodanno = 0
	festivi_onerosi = 0
	passato_festivi_onerosi = [0]*10
	passato_sabati = [0]*10
	passato_servizi_extra = 0
	passato_capodanni = 0
	esente_cp = False
	aspirante_passa_a_vigile = False
	mesi_da_vigile = 12
	neo_vigile = False

	def __init__(self, *args):
		self.id = int(args[0][0])
		self.nome = args[0][1]
		self.cognome = args[0][2]
		self.data_di_nascita = dt.datetime.strptime(args[0][3], '%d/%m/%Y').date()
		self.grado = args[0][4]
		if self.grado not in _GRADI_VALIDI:
			print("ERRORE! Grado sconosciuto: ", self.grado)
			exit(-1)
		self.squadre = list(map(int, args[0][5].split(",")))
		if self.grado in ["Comandante", "Vicecomandante", "Ispettore", "Presidente"]:
			self.squadre = [0]
		self.gruppo_festivo = int(args[0][6])
		if len(args[0][7]) > 0:
			self.data_passaggio_vigile = dt.datetime.strptime(args[0][7], '%d/%m/%Y').date()
		self.eccezioni = set(args[0][8].split(","))
		if '' in self.eccezioni:
			self.eccezioni.remove('')

		# Verifiche
		for e in self.eccezioni:
			if e not in _ECCEZZIONI_VALIDE:
				print("ERRORE: eccezione sconosciuta ", e)
				exit(-1)
		if "Aspettativa" in self.eccezioni and self.gruppo_festivo != 0:
			print("ATTENZIONE: il vigile {} è in aspettativa ma è assegnato al gruppo festivo {}!".format(self.id, self.gruppo_festivo))
			self.gruppo_festivo = 0
			print("\tIgnoro il gruppo festivo.")
		if "Aspettativa" in self.eccezioni and self.squadre != [0]:
			print("ATTENZIONE: il vigile {} è in aspettativa ma è assegnato alla squadra {}!".format(self.id, self.squadre))
			self.squadre = [0]
			print("\tIgnoro la squadra.")

		# Coefficienti notti e sabati
		self.coeff_notti = 9.0 / self.notti_base
		if "LimiteNotti" in self.eccezioni:
			self.coeff_notti = 0.01 # Ignora pesi, assegnale fino a questo limite
		self.coeff_sabati = 1.1 / self.sabati_base # Per favorire assegnazione stesso numero

	def __str__(self): # Called by print()
		return "Vigile({}, {}, {}, {}, Squadra:{}, GruppoFestivo: {})".format(
				self.nome, 
				self.cognome, 
				self.data_di_nascita.strftime('%d/%m/%Y'), 
				self.grado, 
				self.squadre,
				self.gruppo_festivo
				)

	def __repr__(self):
		return self.__str__()

	def EsenteServizi(self):
		if (self.grado in ["Ispettore", "Presidente"]
			or "Aspettativa" in self.eccezioni
			):
			return True
		return False

	def EsenteNotti(self):
		if (self.EsenteServizi() 
			or self.Aspirante()
			or "EsenteNotti" in self.eccezioni
			or self.grado == "Complemento"
			or "Aspettativa" in self.eccezioni
			):
			return True
		return False

	def extraSabati(self):
		for e in self.eccezioni:
			if "ExtraSabati" in e:
				return int(e[len("ExtraSabati"):])
		return 0

	def extraNotti(self):
		for e in self.eccezioni:
			if "ExtraNotti" in e:
				return int(e[len("ExtraNotti"):])
		return 0

	def esenteCP(self):
		if "EsenteCP" in self.eccezioni:
			return True
		return False

	def EsenteSabati(self):
		if (self.EsenteServizi()
			or self.Aspirante()
			or self.grado == "Complemento"
			or "Aspettativa" in self.eccezioni
			or "EsenteSabati" in self.eccezioni
			):
			return True
		return False

	def EsenteFestivi(self):
		if (self.EsenteServizi()
			or self.gruppo_festivo == 0
			or "Aspettativa" in self.eccezioni
			):
			return True
		return False

	def Aspirante(self):
		if self.grado == "Aspirante" and not self.aspirante_passa_a_vigile:
			return True
		return False

	def Graduato(self):
		if self.grado in ["Comandante", "Vicecomandante", "Capoplotone", "Caposquadra"]:
			return True
		return False

	def AltreCariche(self):
		if ("Segretario" in self.eccezioni
			or "Cassiere" in self.eccezioni
			or "Magazziniere" in self.eccezioni
			or "Vicemagazziniere" in self.eccezioni
			or "Resp. Allievi" in self.eccezioni
			):
			return True
		return False

	def OffsetCompleanno(self, data_inizio):
		if (
			self.data_di_nascita.month <= data_inizio.month
			and self.data_di_nascita.day < data_inizio.day
			):
			compleanno = dt.date(data_inizio.year + 1, self.data_di_nascita.month, self.data_di_nascita.day)
		else:
			compleanno = dt.date(data_inizio.year, self.data_di_nascita.month, self.data_di_nascita.day)
		offset = (compleanno - data_inizio).days
		return offset

	def NumeroServizi(self):
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
					db[id].passato_festivi_onerosi = list(map(lambda x: int(x), line[13:17]))
	fi.close()
	return db

def correggi_aspiranti(db, data_inizio, data_fine):
	for vigile in db.keys():
		if (
			db[vigile].grado == "Aspirante"
			and db[vigile].data_passaggio_vigile > data_inizio
			and db[vigile].data_passaggio_vigile < data_fine
			):
			db[vigile].aspirante_passa_a_vigile = True
			db[vigile].mesi_da_vigile = round((data_fine - db[vigile].data_passaggio_vigile).days / 30.0)
		if db[vigile].data_passaggio_vigile + dt.timedelta(365*2) > data_inizio:
			db[vigile].neo_vigile = True
	return db

def calcola_coefficienti(db):
	for vigile in db.keys():
		if db[vigile].grado == "Comandante":
			db[vigile].notti_base = 3.0
			db[vigile].sabati_base = 0.5
		elif db[vigile].grado == "Vicecomandante":
			db[vigile].notti_base = 4.0
			db[vigile].sabati_base = 0.5
		elif db[vigile].grado in ["Capoplotone", "Caposquadra"]:
			db[vigile].notti_base = 7.0
		if (
			"Segretario" in db[vigile].eccezioni
			or "Cassiere" in db[vigile].eccezioni
			or "Magazziniere" in db[vigile].eccezioni
			or "Vicemagazziniere" in db[vigile].eccezioni
			or "Resp. Allievi" in db[vigile].eccezioni
			):
			db[vigile].notti_base = min(db[vigile].notti_base, 5.0)
		if "DaTrasferimento" in db[vigile].eccezioni:
			db[vigile].notti_base = max(db[vigile].notti_base, 12.0)
		if "EsenteCP" in db[vigile].eccezioni:
			db[vigile].notti_base = max(db[vigile].notti_base, 15.0)
		if db[vigile].neo_vigile:
			db[vigile].notti_base = max(db[vigile].notti_base, 12.0)

		db[vigile].coeff_notti = 9.0 / db[vigile].notti_base
		if "LimiteNotti" in db[vigile].eccezioni:
			db[vigile].coeff_notti = 0.01 # Ignora pesi, assegnale fino a questo limite
		db[vigile].coeff_sabati = 1.1 / db[vigile].sabati_base # Per favorire assegnazione stesso numero
	return db

def date(string):
	try:
		date = list(map(int, string.split("-")))
		date = dt.date(date[0], date[1], date[2])
		return date
	except:
		msg = "{} is not a valid date string (expected format: YYYY-MM-DD)".format(string)
		raise argparse.ArgumentTypeError(msg)

class VVFParser(argparse.ArgumentParser):
	def __init__(self):
		super().__init__(description="Compute yearly shifts for volunteer firefighters")

		#Positional Arguments
		self.add_argument("data_di_inizio", type=date, help="start date, which must be a Friday")
		self.add_argument("data_di_fine", type=date, help="end date, which must be a Friday")
		self.add_argument("squadra_di_partenza", type=int, help="starting squad for weekly availability")

		#Optional Arguments
		self.add_argument("-c", "--servizi-compleanno",
							help="enable assigning shifts on firefighter's birthdays",
							action="store_true")
		self.add_argument("-j", "--jobs", type=int,
							help="number of parallel threads to solve the model (Default: 1)",
							default=1)
		self.add_argument("-l", "--loose",
							help="enable assigning night shifts outside weekly availability",
							action="store_true")
		self.add_argument("-m", "--media-notti-festivi", type=int, action='store',
							help="average number of night shifts for regular firefighters, if set enables the 'PocheManovre' exception",
							default=-1) #nargs=2, default=[-1, -1]
		self.add_argument("-o", "--organico-fn", type=str,
							help="path to CSV containing the available firefigthers (Default: organico.csv)",
							default="./organico.csv")
		self.add_argument("-r", "--riporti-fn", type=str,
							help="path to CSV containing last year's extra and onerous shifts (Default: riporti.csv)",
							default="./riporti.csv")
		self.add_argument("-t", "--time-limit", type=int,
							help="time limit in seconds (Default: no limit)", default=0)
		self.add_argument("-v", "--verbose", help="enable verbose solver output",
							action="store_true")
