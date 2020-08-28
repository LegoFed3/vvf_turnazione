from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import vvf_turnazione as vvf

#Parametri annuali
data_inizio = dt.date(2021, 1, 15)
data_fine = dt.date(2022, 1, 14)
squadra_di_partenza = 1

#Parametri statici
giorni_festivi_speciali = [
	dt.date(data_inizio.year,1,6), #Epifania
	vvf.calc_easter(data_inizio.year), #Pasqua
	vvf.calc_easter(data_inizio.year) + dt.timedelta(1), #Pasquetta
	dt.date(data_inizio.year,4,25), #25 Aprile
	dt.date(data_inizio.year,5,1), #1 Maggio
	dt.date(data_inizio.year,6,2), #2 Giugno
	dt.date(data_inizio.year,8,15), #Ferragosto
	dt.date(data_inizio.year,11,1), #1 Novembre
	dt.date(data_inizio.year,12,8), #8 Dicembre
	dt.date(data_inizio.year,12,25), #Natale
	dt.date(data_inizio.year,12,26), #S. Stefano
	dt.date(data_inizio.year+1,1,1), #1 Gennaio
	dt.date(data_inizio.year+1,1,6), #Epifania
	]
vigili_fn = "./vigili.csv"
riporti_fn = "./riporti.csv"
time_limit = 300000 #ms
verbose = True #False
loose = False
compute_aspiranti = False
no_servizi_compleanno = True

model = vvf.TurnazioneVVF(data_inizio, data_fine, squadra_di_partenza, giorni_festivi_speciali, vigili_fn, riporti_fn, loose=loose, compute_aspiranti=compute_aspiranti, no_servizi_compleanno=no_servizi_compleanno)
model.Solve(time_limit, verbose)

model.SaveSolution()
print("\nPremere INVIO per uscire.")
input()
