import datetime as dt
import os

GRADI_VALIDI = [
	"Comandante",
	"Vicecomandante",
	"Capoplotone",
	"Caposquadra",
	"Vigile",
	"Aspirante",
	"Segretario",
	"Cassiere",
	"Magazziniere",
	"Vicemagazziniere",
	"Resp. Allievi",
	"Ispettore",
	"Presidente",
	]

ECCEZIONI_VALIDE = [
	"", # Nessun eccezione
	"NottiSoloSabato",
	"NottiSoloSabatoFestivi",
	"NottiSoloLun",
	"NottiSoloMarVen",
	"ServiziSoloPrimi6Mesi",
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
	nome = ""
	cognome = ""
	data_di_nascita = dt.date(1900, 1, 1)
	data_passaggio_vigile = dt.date(1900, 1, 1)
	grado = "Vigile"
	autista = False
	squadra = 0
	gruppo_festivo = 0
	eccezioni = []
	notti = 0
	sabati = 0
	festivi = 0
	passato_fatto_servizio_oneroso = 0
	passato_fatto_sabato = True
	passato_servizi_extra = 0
	esente_CP = False
	aspirante_passa_a_vigile = False

	def __init__(self, *args):
		self.nome = args[0][0]
		self.cognome = args[0][1]
		self.data_di_nascita = dt.datetime.strptime(args[0][2], '%d/%m/%Y').date()
		self.grado = args[0][3]
		if self.grado not in GRADI_VALIDI:
			print("ERRORE! Grado sconosciuto: ", self.grado)
		self.squadra = int(args[0][4])
		if self.grado in ["Comandante", "Vicecomandante", "Ispettore", "Presidente"]:
			self.squadra = 0
		self.gruppo_festivo = int(args[0][5])
		if args[0][6] in ["si", "Si", "SI"]:
			self.esente_CP = True
		self.eccezioni = args[0][7].split(",")
		for e in self.eccezioni:
			if e not in ECCEZIONI_VALIDE:
				print("ERRORE: eccezione sconosciuta ", e)
		if self.grado == "Aspirante" and len(args[0][8]) > 0:
			self.data_passaggio_vigile = dt.datetime.strptime(args[0][8], '%d/%m/%Y').date()

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

	def esente_notti(self):
		if self.grado in ["Ispettore", "Presidente"]:
			return True
		return False

	def esente_sabati(self):
		if self.grado in ["Ispettore", "Presidente"]:
			return True
		return False

	def aspirante(self):
		if self.grado == "Aspirante" and not self.aspirante_passa_a_vigile:
			return True
		return False

	def graduato(self):
		if self.grado in ["Comandante", "Vicecomandante", "Capoplotone", "Caposquadra"]:
			return True
		return False

	def get_compleanno_offset(self, data_inizio):
		if self.data_di_nascita.month <= data_inizio.month and self.data_di_nascita.day < data_inizio.day:
			compleanno = dt.date(data_inizio.year + 1, self.data_di_nascita.month, self.data_di_nascita.day)
		else:
			compleanno = dt.date(data_inizio.year, self.data_di_nascita.month, self.data_di_nascita.day)
		offset = (compleanno - data_inizio).days
		return offset

	def numero_servizi(self):
		return self.notti + self.sabati + self.festivi

def read_csv_vigili(filename="./vigili.csv"):
	data = {}
	if not os.path.isfile(filename):
		print("ERRORE: il file {} che descrive i vigili non esiste!".format(filename))
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
				data[int(line[0])] = Vigile(line[1:])
	fi.close()
	return data

def read_csv_riporti(data, filename="./riporti.csv"):
	if not os.path.isfile(filename):
		print("ATTENZIONE: il file {} che descrive i riporti dello scorso anno non esiste!".format(filename))
		print("\tContinuo senza.")
		return data
	fi = open(filename, "r")
	for line in fi:
		if line[0] == "#":
			continue
		else:
			line = line.strip("\n\r").split(";")
			if len(line) > 0:
				data[int(line[0])].passato_servizi_extra = int(line[1])
				data[int(line[0])].passato_fatto_sabato = bool(int(line[2]))
				data[int(line[0])].passato_fatto_servizio_oneroso = int(line[3])
	fi.close()
	return data

def correggi_aspiranti(data, data_inizio, data_fine):
	for vigile in data.keys():
		if data[vigile].grado == "Aspirante" and data[vigile].data_passaggio_vigile > data_inizio and data[vigile].data_passaggio_vigile < data_fine:
			data[vigile].aspirante_passa_a_vigile = True
	return data
