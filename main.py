from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import vvf_turnazione as vvf
import vvf_io as vvfio

parser = vvfio.VVFParser()
args = parser.parse_args()

model = vvf.TurnazioneVVF(args)
model.Solve(args.time_limit, args.verbose, args.jobs)

model.SaveSolution()
print("Dati salvato in turni_{}.csv e riporti_{}.csv.".format(model.anno, model.anno))
