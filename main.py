import time
import datetime as dt
import argparse
import vvf_turnazione
import vvf_io


# Command line argument parser
def date(string):
    try:
        d = list(map(int, string.split("-")))
        d = dt.date(d[0], d[1], d[2])
        return d
    except Exception as e:
        msg = f"{string} is not a valid date string (expected format: YYYY-MM-DD):\n{e}"
        raise argparse.ArgumentTypeError(msg)


class VVFParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(description="Compute yearly shifts for volunteer firefighters")

        # Positional Arguments
        self.add_argument("data_di_inizio", type=date, help="start date, which must be a Friday")
        self.add_argument("data_di_fine", type=date, help="end date, which must be a Friday")
        self.add_argument("squadra_di_partenza", type=int, help="starting squad for weekly availability")

        # Optional Arguments
        self.add_argument("-c", "--servizi-compleanno",
                          help="enable assigning shifts on firefighter's birthdays",
                          action="store_true")
        self.add_argument("-j", "--jobs", type=int,
                          help="number of parallel threads to solve the model (Default: 1)",
                          default=1)
        self.add_argument("-l", "--loose",
                          help="enable assigning night shifts outside weekly availability",
                          action="store_true")
        self.add_argument("-o", "--organico-fn", type=str,
                          help="path to CSV containing the available firemen (Default: organico.csv)",
                          default="./organico.csv")
        self.add_argument("-r", "--riporti-fn", type=str,
                          help="path to CSV containing last year's extra and onerous shifts (Default: riporti.csv)",
                          default="./riporti.csv")
        self.add_argument("-s", "--seed", type=int, help="SCIP random seed", default=round(time.time()))
        self.add_argument("-t", "--time-limit", type=int,
                          help="time limit in seconds (Default: no limit)", default=0)
        self.add_argument("-v", "--verbose", help="enable verbose solver output",
                          action="store_true")


t0 = time.time()
parser = VVFParser()
args = parser.parse_args()

model = vvf_turnazione.ILPTurnazione(args)
model.solve()

# model = vvf_affiancamenti.ILPAffiancamenti(model)
# model.solve()

vvf_io.save_solution_to_files(model)

t1 = time.time()
print("Soluzione trovata in {0:.2f} secondi.".format(t1 - t0))
