from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import vvf_turnazione

data_inizio = dt.date(2021, 1, 15)
data_fine = dt.date(2022, 1, 14)
squadra_di_partenza = 1
giorni_festivi_speciali = [
	dt.date(data_inizio.year,8,15), #Ferragosto
	dt.date(data_inizio.year,12,25), #Natale
	dt.date(data_inizio.year+1,1,6), #Epifania
	]
vigili_fn = "./vigili.csv"
time_limit = 300000 #ms
verbose = True #False
loose = False
compute_aspiranti = False

model = vvf_turnazione.VVF_Turnazione(data_inizio, data_fine, squadra_di_partenza, giorni_festivi_speciali, vigili_fn, loose=loose, compute_aspiranti=compute_aspiranti)
model.solve(time_limit, verbose)

model.save_solution()
