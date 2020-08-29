from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import argparse
import vvf_turnazione as vvf
import vvf_io as vvfio

#Argument Parser
parser = argparse.ArgumentParser(description="Compute yearly shifts for volunteer firefighters")

#Parametri
parser.add_argument("-c", "--servizi-compleanno",
					help="enable assigning shifts on firefighter's birthdays",
					action="store_true")
parser.add_argument("-di", "--data-inizio", type=vvfio.date,
					help="start date, which must be a Friday (Default: 2021-1-15)",
					default="2021-1-15")
parser.add_argument("-df", "--data-fine", type=vvfio.date,
					help="end date, which must be a Friday (Default: 2022-1-14)",
					default="2022-1-14")
parser.add_argument("-l", "--loose",
					help="enable assigning night shifts outside weekly availability",
					action="store_true")
parser.add_argument("-R", "--riporti-fn", type=str,
					help="path to CSV containing last year's extra and onerous shifts (Default: riporti.csv)",
					default="./riporti.csv")
parser.add_argument("-s", "--squadra-di-partenza", type=int,
					help="starting squad for weekly availability (Default: 1)",
					default="1")
parser.add_argument("-t", "--time-limit", type=int,
					help="time limit in ms (Default: 300000)", default=300000)
parser.add_argument("-v", "--verbose", help="enable verbose solver output",
					action="store_true")
parser.add_argument("-V", "--vigili-fn", type=str,
					help="path to CSV containing the available firefigthers (Default: vigili.csv)",
					default="./vigili.csv")
args = parser.parse_args()

model = vvf.TurnazioneVVF(args.data_inizio, args.data_fine,
						  args.squadra_di_partenza, args.vigili_fn,
						  args.riporti_fn, args.loose, args.servizi_compleanno)
model.Solve(args.time_limit, args.verbose)

model.SaveSolution()
print("\nPremere INVIO per uscire.")
input()
