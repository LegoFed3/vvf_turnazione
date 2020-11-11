import time
import datetime as dt
import vvf_turnazione as vvf
import vvf_io as vvfio

t0 = time.time()
parser = vvfio.VVFParser()
args = parser.parse_args()

model = vvf.TurnazioneVVF(args)
model.Solve(args.time_limit, args.verbose, args.jobs)


model.SaveSolution()
print("Dati salvati in turni_{}.csv e riporti_{}.csv.".format(model.anno, model.anno))
t1 = time.time()
print("Soluzione trovata in {0:.2f} secondi.".format(t1 - t0))