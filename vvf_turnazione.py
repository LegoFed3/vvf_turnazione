from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import vvf_io

anno = 2021
giorno_inizio = 15
giorno_fine = 14
squadra_di_partenza = 1

DB = vvf_io.read_csv_vigili()
vigili = list(DB.keys())
vigili_squadra = {}
vigili_gruppi_festivo = {}
for vigile in vigili:
	# Squadra
	if DB[vigile].squadra == 0:
		continue
	elif DB[vigile].squadra not in vigili_squadra.keys():
		vigili_squadra[DB[vigile].squadra] = []
	vigili_squadra[DB[vigile].squadra].append(vigile)
	# Gruppo Festivo
	if DB[vigile].gruppo_festivo == 0:
		continue
	elif DB[vigile].gruppo_festivo not in vigili_gruppi_festivo.keys():
		vigili_gruppi_festivo[DB[vigile].gruppo_festivo] = []
	vigili_gruppi_festivo[DB[vigile].gruppo_festivo].append(vigile)


num_squadre = len(vigili_squadra.keys())
data_inizio = dt.date(anno, 1, giorno_inizio)
data_fine = dt.date(anno+1, 1, giorno_fine)
num_giorni = (data_fine - data_inizio).days
giorni_festivi_speciali = [
	dt.date(anno,8,15), #Ferragosto
	dt.date(anno,12,25), #Natale
	]

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

var_servizi_vigile = {}
constr_servizi_vigile = {}
constr_notti_comandanti = {}
var_differenza_servizi = {}
constr_differenza_servizi = {}

#Model
solver = pywraplp.Solver('VVF_turni', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

#Solver Parameters
solver.EnableOutput()
solver.SetNumThreads(2)

print("Creo il modello...")
giorno = 0
squadra = squadra_di_partenza
while giorno < num_giorni or squadra != (num_squadre - 1):
	for i in range(7):
		curr_giorno = giorno + i
		curr_data = data_inizio + dt.timedelta(curr_giorno)
		
		giorno_squadra[curr_giorno] = squadra

		#VAR: vigili di squadra candidati per la notte
		var_notti[curr_giorno] = {}
		# for vigile in vigili_squadra[squadra]:
			# var_notti[curr_giorno][vigile] = solver.IntVar(0, 1, "var_vigile({})_notte({})".format(vigile, curr_giorno))
		for vigile in vigili:
			if not DB[vigile].esente_notti():
				var_notti[curr_giorno][vigile] = solver.IntVar(0, 1, "var_vigile({})_notte({})".format(vigile, curr_giorno))
			
		#CONSTR: 1 vigile per notte
		constr_notti[curr_giorno] = solver.Constraint(1, 1, "constr_notte({})".format(curr_giorno))
		for var in var_notti[curr_giorno].values():
			constr_notti[curr_giorno].SetCoefficient(var, 1)
			
		#SABATO
		if curr_data.weekday() == 5 and curr_data not in giorni_festivi_speciali:

			#VAR: vigile candidati per il sabato
			var_sabati[curr_giorno] = {}
			for vigile in vigili:
				if not DB[vigile].esente_diurni():
					var_sabati[curr_giorno][vigile] = solver.IntVar(0, 1, "var_vigile({})_sabato({})".format(vigile, curr_giorno))

			#CONSTR: 1 vigile per sabato
			constr_sabati[curr_giorno] = solver.Constraint(1, 1, "constr_sabato({})".format(curr_giorno))
			for vigile in vigili:
				if not DB[vigile].esente_diurni():
					constr_sabati[curr_giorno].SetCoefficient(var_sabati[curr_giorno][vigile], 1)

		#FESTIVO
		if curr_data.weekday() == 6 or curr_data in giorni_festivi_speciali:
			
			#VAR: vigili candidati per il festivo
			var_festivi[curr_giorno] = {}
			for gruppo in vigili_gruppi_festivo.keys():
				var_festivi[curr_giorno][gruppo] = solver.IntVar(0, 1, "var_gruppo({})_festivo({})".format(gruppo, curr_giorno))
				
			#CONSTR: 1 gruppo festivo a festivo
			constr_festivi[curr_giorno] = solver.Constraint(1, 1, "constr_festivo({})".format(curr_giorno))
			for gruppo in vigili_gruppi_festivo.keys():
				constr_festivi[curr_giorno].SetCoefficient(var_festivi[curr_giorno][gruppo], 1)
			
	#CONSTR: max 1 notte per vigile a settimana
	settimana = int(giorno / 7)
	constr_notti_settimana_vigile[settimana] = {}
	for vigile in vigili_squadra[squadra]:
		if not DB[vigile].esente_notti():
			constr_notti_settimana_vigile[settimana][vigile] = solver.Constraint(-solver.infinity(), 1, "constr_una_notte_settimana({})_vigile({})".format(settimana, vigile))
			for i in range(7):
				curr_giorno = giorno + i
				constr_notti_settimana_vigile[settimana][vigile].SetCoefficient(var_notti[curr_giorno][vigile], 1)

	squadra = (squadra % num_squadre) + 1
	giorno += 7

for vigile in vigili:
	gruppo = DB[vigile].gruppo_festivo
	# Calcola giorno di compleanno come offset
	compleanno = DB[vigile].data_di_nascita
	if compleanno.month == 1 and compleanno.day < giorno_inizio:
		compleanno = dt.date(anno+1, compleanno.month, compleanno.day)
	else:
		compleanno = dt.date(anno, compleanno.month, compleanno.day)
	compleanno = (compleanno - data_inizio).days

	#CONSTR: max 1 sabato
	constr_sabati_vigile[vigile] = solver.Constraint(-solver.infinity(), 1, "constr_un_sabato_vigile({})".format(vigile))
	for sabato in var_sabati.keys():
		constr_sabati_vigile[vigile].SetCoefficient(var_sabati[sabato][vigile], 1)
		
	#CONSTR: max 1 tra venerdì notte, sabato e sabato notte
	constr_sabati_notti_circostanti_vigile[vigile] = {}
	for sabato in var_sabati.keys():
		constr_sabati_notti_circostanti_vigile[vigile][sabato] = solver.Constraint(-solver.infinity(), 1, "constr_sabato_notte_consecutivi_vigile({})_sabato({})".format(vigile, sabato))
		constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(var_sabati[sabato][vigile], 1)
		if vigile in var_notti[sabato].keys():
			constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(var_notti[sabato][vigile], 1)
		venerdi = sabato - 1
		if vigile in var_notti[venerdi].keys():
			constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(var_notti[venerdi][vigile], 1)
		
	#CONSTR: 3-5 festivi l'anno #NOTA: 4-5 non ha soluzione
	# constr_festivi_vigile[vigile] = solver.Constraint(3, 5, "constr_festivi_annuali_vigile({})".format(vigile))
	# for festivo in var_festivi.keys():
		# constr_festivi_vigile[gruppo].SetCoefficient(var_festivi[festivo][gruppo], 1)
		
	#CONSTR: max 3 notti per comandante e vice
	if DB[vigile].grado in ["Comandante", "Vicecomandante"]:
		constr_notti_comandanti[vigile] = solver.Constraint(0, 3, "constr_notti_comandanti({})".format(vigile))
		for giorno in range(len(var_notti.keys())):
			constr_notti_comandanti[vigile].SetCoefficient(var_notti[giorno][vigile], 1)
		
	#CONSTR: max 1 tra festivo e notti circostanti
	constr_festivi_notti_circostanti_vigile[vigile] = {}
	for festivo in var_festivi.keys():
		constr_festivi_notti_circostanti_vigile[vigile][festivo] = solver.Constraint(-solver.infinity(), 1, "constr_festivo_notte_consecutivi_vigile({})_festivo({})".format(vigile, festivo))
		constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(var_festivi[festivo][gruppo], 1)
		if vigile in var_notti[festivo].keys():
			constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(var_notti[festivo][vigile], 1)
		giorno_prima = festivo - 1
		if vigile in var_notti[giorno_prima].keys():
			constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(var_notti[giorno_prima][vigile], 1)

	#VAR: somma servizi per vigile (ausiliaria)
	var_servizi_vigile[vigile] = solver.NumVar(0, solver.infinity(), "var_aux_sum_servizi_vigile({})".format(vigile))
	constr_servizi_vigile[vigile] = solver.Constraint(0, 0, "constr_somma_servizi_vigile({})".format(vigile))
	constr_servizi_vigile[vigile].SetCoefficient(var_servizi_vigile[vigile], -1)
	for giorno in range(len(var_notti.keys())):
		mult = 1
		if giorno == compleanno:
			mult = 2 #Servizi fatti il giorno di compleanno "valgono" il doppio
		if vigile in var_notti[giorno].keys():
			if giorno_squadra[giorno] == DB[vigile].squadra or DB[vigile].squadra == 0:
				constr_servizi_vigile[vigile].SetCoefficient(var_notti[giorno][vigile], 1 * mult) # Notti di squadra contano 1
			else:
				constr_servizi_vigile[vigile].SetCoefficient(var_notti[giorno][vigile], 2 * mult) # Notti NON di squadra contano il doppio
		if giorno in var_sabati.keys():
			constr_servizi_vigile[vigile].SetCoefficient(var_sabati[giorno][vigile], 1 * mult)
		if giorno in var_festivi.keys():
			constr_servizi_vigile[vigile].SetCoefficient(var_festivi[giorno][gruppo], 1.01 * mult) # Base 1.01 per evitare di scambiare notti con festivi

for i in range(len(vigili)):
	v1 = vigili[i]
	for j in range(i+1, len(vigili)):
		v2 = vigili[j]
		#VAR: differenza numero servizi tra due vigili (ausiliaria)
		var_differenza_servizi[(v1, v2)] = solver.NumVar(-solver.infinity(), solver.infinity(), "var_aux_diff_servizi({},{})".format(v1, v2))
		#CONSTR: implementa quanto sopra
		constr_differenza_servizi[(v1, v2, '+')] = solver.Constraint(-solver.infinity(), 0, "constr_diff_servizi_plus_vigili({},{})".format(v1, v2))
		constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(var_differenza_servizi[(v1, v2)], -1)
		constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(var_servizi_vigile[v1], 1)
		constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(var_servizi_vigile[v2], -1)
		constr_differenza_servizi[(v1, v2, '-')] = solver.Constraint(-solver.infinity(), 0, "constr_diff_servizi_minus_vigili({},{})".format(v1, v2))
		constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(var_differenza_servizi[(v1, v2)], -1)
		constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(var_servizi_vigile[v1], -1)
		constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(var_servizi_vigile[v2], 1)
			
# TIME LIMIT
solver.SetTimeLimit(300000) #ms
# solver.SetTimeLimit(60000) #ms

# OBJECTIVE
objective = solver.Objective()
#OBJ: minimizza le differenze tra servizi
for var in var_differenza_servizi.values():
	objective.SetCoefficient(var, 1)

objective.SetMinimization()

print("Il modello ha {} variabili e {} vincoli.".format(solver.NumVariables(), solver.NumConstraints()))

model = open("model.txt", "w")
model.write(solver.ExportModelAsLpFormat(False))
# model.write(solver.ExportModelAsMpsFormat(True, False))
model.close()

print("Risolvo il modello...")
status = solver.Solve()

# Print solution
if status == pywraplp.Solver.INFEASIBLE:
	print('Il problema non ammette soluzione.')
	print('Rilassa i vincoli e riprova.')
else:
	if status == pywraplp.Solver.FEASIBLE:
		print("ATTENZIONE: la soluzione trovata potrebbe non essere ottima.")
	print('Soluzione:')
	print('Funzione obiettivo =', solver.Objective().Value())
	print("* Servizi per vigile:")
	for vigile in vigili:
		print("Vigile {}: {}".format(vigile, float(var_servizi_vigile[vigile].solution_value())))
	# Salva i turni calcolati in un CSV
	out = open("./turni_{}.csv".format(anno), "w")
	out.write("#Data;Notte;Sabato/Festivo\n")
	for giorno in range(len(var_notti.keys())):
		data = data_inizio + dt.timedelta(giorno)
		line = str(data)+";"
		for vigile in var_notti[giorno].keys():
			if var_notti[giorno][vigile].solution_value() == 1:
				line += DB[vigile].nome+" "+DB[vigile].cognome+";"
		if giorno in var_sabati.keys():
			for vigile in vigili:
				if var_sabati[giorno][vigile].solution_value() == 1:
					line += DB[vigile].nome+" "+DB[vigile].cognome+";"
		elif giorno in var_festivi.keys():
			for vigile in vigili:
				if var_festivi[giorno][DB[vigile].gruppo_festivo].solution_value() == 1:
					line += DB[vigile].nome+" "+DB[vigile].cognome+";"
		out.write(line+"\n")
	# TODO Riporta i servizi speciali
	out.close()	
