from __future__ import print_function
from ortools.linear_solver import pywraplp


# TODO: actual parser
print("Input data:")
vigili = list([i for i in range(68)])
vigili_autisti = vigili[:20]
vigili_squadra = []
num_squadre = 4
for i in range(num_squadre):
	vigili_squadra.append(list([j for j in vigili if j%num_squadre==i]))

num_giorni = 365
giorni_festivi_extra = []

print("* Vigili: ", vigili)
print("* Squadre: ", vigili_squadra)
print("* Festivi extra: ", giorni_festivi_extra)
	
#Collections
var_notti = {}
constr_notti = {}
constr_notti_settimana_vigile = {}

var_sabati = {}
constr_sabati = {}
constr_sabati_vigile = {}
constr_sabati_notti_circostanti_vigile = {}

var_festivi = {}
constr_festivi = {}
constr_festivi_autista = {}
constr_festivi_vigile = {}
constr_festivi_notti_circostanti_vigile = {}

var_servizi_vigile = {}
constr_servizi_vigile = {}
var_differenza_servizi = {}
constr_differenza_servizi = {}

#Model
solver = pywraplp.Solver('VVF_turni', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

#Solver Parameters
solver.EnableOutput()
solver.SetNumThreads(2)

print("Creating model...")
giorno = 0
squadra = 0
while giorno < num_giorni or squadra != (num_squadre - 1):
	for i in range(7):
		curr_giorno = giorno + i

		#VAR: vigili di squadra candidati per la notte
		var_notti[curr_giorno] = {}
		for vigile in vigili_squadra[squadra]:
			var_notti[curr_giorno][vigile] = solver.IntVar(0, 1, "var_vigile({})_notte({})".format(vigile, curr_giorno))
			
		#CONSTR: 1 vigile per notte
		constr_notti[curr_giorno] = solver.Constraint(1, 1)
		for var in var_notti[curr_giorno].values():
			constr_notti[curr_giorno].SetCoefficient(var, 1)
			
		#SABATO
		if i == 1 and curr_giorno not in giorni_festivi_extra:

			#VAR: vigile candidati per il sabato
			var_sabati[curr_giorno] = {}
			for vigile in vigili:
				var_sabati[curr_giorno][vigile] = solver.IntVar(0, 1, "var_vigile({})_sabato({})".format(vigile, curr_giorno))

			#CONSTR: 1 vigile per sabato
			constr_sabati[curr_giorno] = solver.Constraint(1, 1)
			for vigile in vigili:
				constr_sabati[curr_giorno].SetCoefficient(var_sabati[curr_giorno][vigile], 1)

		#FESTIVO
		if i == 2 or curr_giorno in giorni_festivi_extra:
			
			#VAR: vigili candidati per il festivo
			var_festivi[curr_giorno] = {}
			for vigile in vigili:
				var_festivi[curr_giorno][vigile] = solver.IntVar(0, 1, "var_vigile({})_festivo({})".format(vigile, curr_giorno))
				
			#CONSTR: 3-4 vigili per festivo
			constr_festivi[curr_giorno] = solver.Constraint(3, 4)
			for vigile in vigili:
				constr_festivi[curr_giorno].SetCoefficient(var_festivi[curr_giorno][vigile], 1)
				
			#CONSTR: almeno 1 autista per festivo
			constr_festivi_autista[curr_giorno] = solver.Constraint(1, solver.infinity())
			for autista in vigili_autisti:
				constr_festivi_autista[curr_giorno].SetCoefficient(var_festivi[curr_giorno][autista], 1)
			
	#CONSTR: max 1 notte per vigile a settimana
	settimana = int(giorno / 7)
	constr_notti_settimana_vigile[settimana] = {}
	for vigile in vigili_squadra[squadra]:
		constr_notti_settimana_vigile[settimana][vigile] = solver.Constraint(0, 1)
		for i in range(7):
			curr_giorno = giorno + i
			constr_notti_settimana_vigile[settimana][vigile].SetCoefficient(var_notti[curr_giorno][vigile], 1)

	squadra = (squadra + 1) % num_squadre
	giorno += 7

for vigile in vigili:
	#CONSTR: max 1 sabato
	constr_sabati_vigile[vigile] = solver.Constraint(0, 1)
	for sabato in var_sabati.keys():
		constr_sabati_vigile[vigile].SetCoefficient(var_sabati[sabato][vigile], 1)
		
	#CONSTR: max 1 tra venerdì notte, sabato e sabato notte
	constr_sabati_notti_circostanti_vigile[vigile] = {}
	for sabato in var_sabati.keys():
		constr_sabati_notti_circostanti_vigile[vigile][sabato] = solver.Constraint(0, 1)
		constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(var_sabati[sabato][vigile], 1)
		if vigile in var_notti[sabato].keys():
			constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(var_notti[sabato][vigile], 1)
		venerdi = sabato - 1
		if vigile in var_notti[venerdi].keys():
			constr_sabati_notti_circostanti_vigile[vigile][sabato].SetCoefficient(var_notti[venerdi][vigile], 1)
		
	#CONSTR: 3-5 festivi l'anno #NOTA: 4-5 non ha soluzione
	constr_festivi_vigile[vigile] = solver.Constraint(3, 5)
	for festivo in var_festivi.keys():
		constr_festivi_vigile[vigile].SetCoefficient(var_festivi[festivo][vigile], 1)
		
	#CONSTR: max 1 tra festivo e notti circostanti
	constr_festivi_notti_circostanti_vigile[vigile] = {}
	for festivo in var_sabati.keys():
		constr_festivi_notti_circostanti_vigile[vigile][festivo] = solver.Constraint(0, 1)
		constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(var_sabati[festivo][vigile], 1)
		if vigile in var_notti[festivo].keys():
			constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(var_notti[festivo][vigile], 1)
		giorno_prima = festivo - 1
		if vigile in var_notti[giorno_prima].keys():
			constr_festivi_notti_circostanti_vigile[vigile][festivo].SetCoefficient(var_notti[giorno_prima][vigile], 1)

	#VAR: somma servizi per vigile (ausiliaria)
	var_servizi_vigile[vigile] = solver.NumVar(0, solver.infinity(), "var_servizi_vigile({})".format(vigile))
	constr_servizi_vigile[vigile] = solver.Constraint(0, 0)
	constr_servizi_vigile[vigile].SetCoefficient(var_servizi_vigile[vigile], -1)
	for giorno in range(len(var_notti.keys())):
		if vigile in var_notti[giorno].keys():
			constr_servizi_vigile[vigile].SetCoefficient(var_notti[giorno][vigile], 1)
		if giorno in var_sabati.keys():
			constr_servizi_vigile[vigile].SetCoefficient(var_sabati[giorno][vigile], 1) #1.1) #1)
		if giorno in var_festivi.keys():
			constr_servizi_vigile[vigile].SetCoefficient(var_festivi[giorno][vigile], 1) #2) #)

print("Creating auxiliary variables...")
#CONSTR: max 1 servizio di differenza tra ogni coppia di vigili
for v1 in vigili:
	for v2 in vigili:
		if v1 != v2:
			var_differenza_servizi[(v1, v2)] = solver.NumVar(-solver.infinity(), solver.infinity(), "var_differenza_servizi({}, {})".format(v1, v2))
			# v1-v2<=aux
			constr_differenza_servizi[(v1, v2, '+')] = solver.Constraint(-solver.infinity(), 0)
			constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(var_differenza_servizi[(v1, v2)], -1)
			constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(var_servizi_vigile[v1], 1)
			constr_differenza_servizi[(v1, v2, '+')].SetCoefficient(var_servizi_vigile[v2], -1)
			# v2-v1<=aux
			constr_differenza_servizi[(v1, v2, '-')] = solver.Constraint(-solver.infinity(), 0)
			constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(var_differenza_servizi[(v1, v2)], -1)
			constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(var_servizi_vigile[v1], -1)
			constr_differenza_servizi[(v1, v2, '-')].SetCoefficient(var_servizi_vigile[v2], 1)
			
# TIME LIMIT
solver.SetTimeLimit(60000) #ms

# OBJECTIVE
objective = solver.Objective()
#OBJ: minimizza le differenze tra servizi
for var in var_differenza_servizi.values():
	objective.SetCoefficient(var, 1)

objective.SetMinimization()

print("Model has {} variables and {} constraints.".format(solver.NumVariables(), solver.NumConstraints()))

model = open("model.txt", "w")
model.write(solver.ExportModelAsLpFormat(False))
# model.write(solver.ExportModelAsMpsFormat(True, False))
model.close()
exit()

print("Solving model...")
status = solver.Solve()

# Print solution
if status == pywraplp.Solver.INFEASIBLE:
	print('The problem does not have an optimal solution.')
	print('Relax your constraints and try again.')
else:
	if status == pywraplp.Solver.FEASIBLE:
		print("WARNING: solution is not optimal.")
	print('Solution:')
	print('Objective value =', solver.Objective().Value())
	print("* Notti:")
	for giorno in range(len(var_notti.keys())):
		for vigile in var_notti[giorno].keys():
			if var_notti[giorno][vigile].solution_value() == 1:
				print("Notte {} - Vigile {}".format(giorno, vigile))
	print("* Sabati:")
	for sabato in var_sabati.keys():
		for vigile in vigili:
			if var_sabati[sabato][vigile].solution_value() == 1:
				print("Sabato {} - Vigile {}".format(sabato, vigile))
	print("* Festivi:")
	for festivo in var_festivi.keys():
		vigili_festivo = []
		for vigile in vigili:
			if var_festivi[festivo][vigile].solution_value() == 1:
				vigili_festivo.append(vigile)
		print("Festivo {} - Vigili: {}".format(festivo, vigili_festivo))
	print("* Servizi per vigile:")
	for vigile in vigili:
		print("Vigile {}: {}".format(vigile, int(var_servizi_vigile[vigile].solution_value())))
		# print("Vigile {}: {}".format(vigile, var_servizi_vigile[vigile].solution_value()))
	#TODO	
