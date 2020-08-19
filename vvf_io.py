from datetime import datetime

class Vigile:
	nome = ""
	cognome = ""
	data_di_nascita = datetime(1900, 1, 1)
	grado = "Vigile"
	autista = False
	squadra = 0
	gruppo_festivo = 0
	
	
	def __init__(self, *args):
		self.nome = args[0][0]
		self.cognome = args[0][1]
		self.data_di_nascita = datetime.strptime(args[0][2], '%d/%m/%Y').date()
		self.grado = args[0][3]
		self.squadra = int(args[0][4])
		self.gruppo_festivo = int(args[0][5])

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
		if self.grado == "Aspirante":
			return True
		return False

	def esente_diurni(self):
		return False

def read_csv_vigili(filename="./vigili.csv"):
	data = {}
	fi = open(filename, "r")
	for line in fi:
		if line[0] == "#":
			continue
		else:
			line = line.strip("\n\r").split(";")
			line = list(filter(lambda x: x != '', line))
			if len(line) > 0:
				data[int(line[0])] = Vigile(line[1:])
	fi.close()
	return data
