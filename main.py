from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import argparse
import vvf_turnazione as vvf
import vvf_io as vvfio

parser = argparse.ArgumentParser(description="Compute yearly shifts for volunteer firefighters")

#Positional Arguments
parser.add_argument("data_di_inizio", type=vvfio.date,
					help="start date, which must be a Friday (Default: 2021-1-15)",
					nargs='?', default="2021-1-15")
parser.add_argument("data_di_fine", type=vvfio.date,
					help="end date, which must be a Friday (Default: 2022-1-14)",
					nargs='?', default="2022-1-14")
parser.add_argument("squadra_di_partenza", type=int,
					help="starting squad for weekly availability (Default: 1)",
					nargs='?', default="1")

#Optional Arguments
parser.add_argument("-c", "--servizi-compleanno",
					help="enable assigning shifts on firefighter's birthdays",
					action="store_true")
parser.add_argument("-j", "--jobs", type=int,
                    help="number of parallel threads to solve the model (Default: 3)",
                    default="3")
parser.add_argument("-l", "--loose",
					help="enable assigning night shifts outside weekly availability",
					action="store_true")
parser.add_argument("-o", "--organico-fn", type=str,
					help="path to CSV containing the available firefigthers (Default: organico.csv)",
					default="./organico.csv")
parser.add_argument("-r", "--riporti-fn", type=str,
					help="path to CSV containing last year's extra and onerous shifts (Default: riporti.csv)",
					default="./riporti.csv")
parser.add_argument("-t", "--time-limit", type=int,
					help="time limit in ms (Default: 300000)", default=300000)
parser.add_argument("-v", "--verbose", help="enable verbose solver output",
					action="store_true")

args = parser.parse_args()
model = vvf.TurnazioneVVF(args)
model.Solve(args.time_limit, args.verbose, args.jobs)

model.SaveSolution()
print("\nPremi INVIO per uscire.")
input()
