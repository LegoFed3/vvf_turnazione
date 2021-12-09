import time
import datetime as dt
import argparse
import vvf_turnazione as vvf
import vvf_io as vvfio


# Command line argument parser
def date(string):
	try:
		date = list(map(int, string.split("-")))
		date = dt.date(date[0], date[1], date[2])
		return date
	except:
		msg = "{} is not a valid date string (expected format: YYYY-MM-DD)".format(string)
		raise argparse.ArgumentTypeError(msg)

class VVFParser(argparse.ArgumentParser):
	def __init__(self):
		super().__init__(description="Compute yearly shifts for volunteer firefighters")

		#Positional Arguments
		self.add_argument("data_di_inizio", type=date, help="start date, which must be a Friday")
		self.add_argument("data_di_fine", type=date, help="end date, which must be a Friday")
		self.add_argument("squadra_di_partenza", type=int, help="starting squad for weekly availability")

		#Optional Arguments
		self.add_argument("-c", "--servizi-compleanno",
							help="enable assigning shifts on firefighter's birthdays",
							action="store_true")
		self.add_argument("-j", "--jobs", type=int,
							help="number of parallel threads to solve the model (Default: 1)",
							default=1)
		self.add_argument("-l", "--loose",
							help="enable assigning night shifts outside weekly availability",
							action="store_true")
		self.add_argument("-m", "--media-notti", type=str, action='store',
							help="average number of night shifts for regular firefighters",
							default="0+") #nargs=2, default=[-1, -1]
		self.add_argument("-o", "--organico-fn", type=str,
							help="path to CSV containing the available firefigthers (Default: organico.csv)",
							default="./organico.csv")
		self.add_argument("-r", "--riporti-fn", type=str,
							help="path to CSV containing last year's extra and onerous shifts (Default: riporti.csv)",
							default="./riporti.csv")
		self.add_argument("-t", "--time-limit", type=int,
							help="time limit in seconds (Default: no limit)", default=0)
		self.add_argument("-v", "--verbose", help="enable verbose solver output",
							action="store_true")

t0 = time.time()
parser = VVFParser()
args = parser.parse_args()

model = vvf.TurnazioneVVF(args)
model.Solve(args.time_limit, args.verbose, args.jobs)


model.SaveSolution()
print("Dati salvati in turni_{}.csv e riporti_{}.csv.".format(model.anno, model.anno))
t1 = time.time()
print("Soluzione trovata in {0:.2f} secondi.".format(t1 - t0))