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
	"NottiSoloSabatoFestivi",
	"NoNottiLun",
	"NoNottiMar",
	"NoNottiMer",
	"NoNottiGio",
	"NoNottiVen",
	"NoNottiSab",
	"NoNottiDom",
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
	]

class Vigile:
	id = 0
	nome = ""
	cognome = ""
	data_di_nascita = dt.date(1900, 1, 1)
	data_passaggio_vigile = dt.date(1900, 1, 1)
	grado = "Vigile"
	squadra = 0
	gruppo_festivo = 0
	eccezzioni = set()
	notti = 0
	sabati = 0
	festivi = 0
	capodanno = 0
	festivi_onerosi = 0
	passato_festivi_onerosi = [0]*5
	passato_sabati = [0]*5
	passato_servizi_extra = 0
	passato_capodanni = 0
	esente_cp = False
	aspirante_passa_a_vigile = False

	def __init__(self, *args):
		self.id = int(args[0][0])
		self.nome = args[0][1]
		self.cognome = args[0][2]
		self.data_di_nascita = dt.datetime.strptime(args[0][3], '%d/%m/%Y').date()
		self.grado = args[0][4]
		if self.grado not in _GRADI_VALIDI:
			print("ERRORE! Grado sconosciuto: ", self.grado)
			exit(-1)
		self.squadra = int(args[0][5])
		if self.grado in ["Comandante", "Vicecomandante", "Ispettore", "Presidente"]:
			self.squadra = 0
		self.gruppo_festivo = int(args[0][6])
		if self.grado == "Aspirante" and len(args[0][7]) > 0:
			self.data_passaggio_vigile = dt.datetime.strptime(args[0][7], '%d/%m/%Y').date()
		self.eccezzioni = set(args[0][8].split(","))
		if '' in self.eccezzioni:
			self.eccezzioni.remove('')
		# Verifiche
		for e in self.eccezzioni:
			if e not in _ECCEZZIONI_VALIDE:
				print("ERRORE: eccezione sconosciuta ", e)
				exit(-1)
			elif e == "EsenteCP":
				self.esente_cp = True
		if "Aspettativa" in self.eccezzioni and self.gruppo_festivo != 0:
			print("ATTENZIONE: il vigile {} è in aspettativa ma è assegnato al gruppo festivo {}!".format(self.id, self.gruppo_festivo))
		if "Aspettativa" in self.eccezzioni and self.squadra != 0:
			print("ATTENZIONE: il vigile {} è in aspettativa ma è assegnato alla squadra {}!".format(self.id, self.squadra))

	def __str__(self): # Called by print()
		return "Vigile({}, {}, {}, {}, Squadra:{}, GruppoFestivo: {})".format(
				self.nome, 
				self.cognome, 
				self.data_di_nascita.strftime('%d/%m/%Y'), 
				self.grado, 
				self.squadra,
				self.gruppo_festivo
				)

	def __repr__(self):
		return self.__str__()

	def EsenteServizi(self):
		if (self.grado in ["Ispettore", "Presidente"]
			or "Aspettativa" in self.eccezzioni
			):
			return True
		return False

	def EsenteNotti(self):
		if self.EsenteServizi() or self.Aspirante():
			return True
		return False

	def EsenteSabati(self):
		if self.EsenteServizi() or self.Aspirante():
			return True
		return False

	def EsenteFestivi(self):
		if self.EsenteServizi() or self.gruppo_festivo == 0:
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
		if ("Segretario" in self.eccezzioni
			or "Cassiere" in self.eccezzioni
			or "Magazziniere" in self.eccezzioni
			or "Vicemagazziniere" in self.eccezzioni
			or "Resp. Allievi" in self.eccezzioni
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
				db[int(line[0])].passato_servizi_extra = int(line[1])
				db[int(line[0])].passato_capodanni = int(line[2])
				db[int(line[0])].passato_sabati = list(map(lambda x: int(x), line[3:8]))
				db[int(line[0])].passato_festivi_onerosi = list(map(lambda x: int(x), line[8:12]))
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
	return db

def date(string):
	try:
		date = list(map(int, string.split("-")))
		date = dt.date(date[0], date[1], date[2])
		return date
	except:
		msg = "{} is not a valid date string (expected format: YYYY-MM-DD)".format(string)
		raise argparse.ArgumentTypeError(msg)
