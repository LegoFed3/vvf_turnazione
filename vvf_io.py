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
	"EsenteCP",
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
	NOME = ""
	COGNOME = ""
	DATA_DI_NASCITA = dt.date(1900, 1, 1)
	DATA_PASSAGGIO_VIGILE = dt.date(1900, 1, 1)
	GRADO = "Vigile"
	SQUADRA = 0
	GRUPPO_FESTIVO = 0
	ECCEZIONI = []
	NOTTI = 0
	SABATI = 0
	FESTIVI = 0
	PASSATO_SERVIZI_ONEROSI = [0]*5
	PASSATO_SABATI = [0]*5
	PASSATO_SERVIZI_EXTRA = 0
	ESENTE_CP = False
	ASPIRANTE_PASSA_A_VIGILE = False

	def __init__(self, *args):
		self.NOME = args[0][0]
		self.COGNOME = args[0][1]
		self.DATA_DI_NASCITA = dt.datetime.strptime(args[0][2], '%d/%m/%Y').date()
		self.GRADO = args[0][3]
		if self.GRADO not in GRADI_VALIDI:
			print("ERRORE! Grado sconosciuto: ", self.GRADO)
			exit(-1)
		self.SQUADRA = int(args[0][4])
		if self.GRADO in ["Comandante", "Vicecomandante", "Ispettore", "Presidente"]:
			self.SQUADRA = 0
		self.GRUPPO_FESTIVO = int(args[0][5])
		if self.GRADO == "Aspirante" and len(args[0][6]) > 0:
			self.DATA_PASSAGGIO_VIGILE = dt.datetime.strptime(args[0][6], '%d/%m/%Y').date()
		self.ECCEZIONI = args[0][7].split(",")
		if '' in self.ECCEZIONI:
			self.ECCEZIONI.remove('')
		for e in self.ECCEZIONI:
			if e not in ECCEZIONI_VALIDE:
				print("ERRORE: eccezione sconosciuta ", e)
				exit(-1)
			elif e == "EsenteCP":
				self.ESENTE_CP = True

	def __str__(self): # Called by print()
		return "Vigile({}, {}, {}, {}, Squadra:{}, GruppoFestivo: {})".format(
				self.NOME, 
				self.COGNOME, 
				self.DATA_DI_NASCITA.strftime('%d/%m/%Y'), 
				self.GRADO, 
				self.SQUADRA,
				self.GRUPPO_FESTIVO
				)

	def __repr__(self):
		return self.__str__()

	def EsenteNotti(self):
		if self.GRADO in ["Ispettore", "Presidente"]:
			return True
		return False

	def EsenteSabati(self):
		if self.GRADO in ["Ispettore", "Presidente"]:
			return True
		return False

	def Aspirante(self):
		if self.GRADO == "Aspirante" and not self.ASPIRANTE_PASSA_A_VIGILE:
			return True
		return False

	def Graduato(self):
		if self.GRADO in ["Comandante", "Vicecomandante", "Capoplotone", "CapoSQUADRA"]:
			return True
		return False

	def OffsetCompleanno(self, data_inizio):
		if (
			self.DATA_DI_NASCITA.month <= data_inizio.month
			and self.DATA_DI_NASCITA.day < data_inizio.day
			):
			compleanno = dt.date(data_inizio.year + 1, self.DATA_DI_NASCITA.month, self.DATA_DI_NASCITA.day)
		else:
			compleanno = dt.date(data_inizio.year, self.DATA_DI_NASCITA.month, self.DATA_DI_NASCITA.day)
		offset = (compleanno - data_inizio).days
		return offset

	def NumeroServizi(self):
		return self.NOTTI + self.SABATI + self.FESTIVI

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
				data[int(line[0])].PASSATO_SERVIZI_EXTRA = int(line[1])
				data[int(line[0])].PASSATO_SABATI = list(map(lambda x: int(x), line[2:7]))
				data[int(line[0])].PASSATO_SERVIZI_ONEROSI = list(map(lambda x: int(x), line[7:11]))
	fi.close()
	return data

def correggi_aspiranti(data, data_inizio, data_fine):
	for vigile in data.keys():
		if (
			data[vigile].GRADO == "Aspirante"
			and data[vigile].DATA_PASSAGGIO_VIGILE > data_inizio
			and data[vigile].DATA_PASSAGGIO_VIGILE < data_fine
			):
			data[vigile].ASPIRANTE_PASSA_A_VIGILE = True
	return data
