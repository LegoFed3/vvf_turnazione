from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import vvf_turnazione as vvf

#Parametri annuali
data_inizio = dt.date(2021, 1, 15)
data_fine = dt.date(2022, 1, 14)
squadra_di_partenza = 1

#Altri parametri
vigili_fn = "./vigili.csv"
riporti_fn = "./riporti.csv"
time_limit = 300000 #ms
verbose = False
loose = False
no_servizi_compleanno = True

model = vvf.TurnazioneVVF(data_inizio, data_fine, squadra_di_partenza, vigili_fn, riporti_fn, loose=loose, no_servizi_compleanno=no_servizi_compleanno)
model.Solve(time_limit, verbose)

model.SaveSolution()
print("\nPremere INVIO per uscire.")
input()
