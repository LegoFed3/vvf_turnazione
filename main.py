import time
import datetime as dt
import argparse
import logging
import sys
import vvf_turnazione
# import vvf_affiancamenti
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
        self.add_argument("data_di_inizio", type=date, help="start date, which must be a Monday")
        self.add_argument("data_di_fine", type=date, help="end date, which must be a Sunday")
        self.add_argument("squadra_di_partenza", type=int, help="starting squad for weekly availability")

        # Optional Arguments
        self.add_argument("-c", "--servizi-compleanno",
                          help="enable assigning shifts on firefighter's birthdays",
                          action="store_true")
        self.add_argument("-j", "--jobs", type=int,
                          help="number of parallel workers to solve the model; CP-SAT needs 8+ to perform well "
                               "(Default: 8)",
                          default=8)
        self.add_argument("--log-file", type=str,
                          help="also write the log (with timestamps) to this file, overwriting it")
        self.add_argument("-l", "--loose",
                          help="enable assigning night shifts outside weekly availability",
                          action="store_true")
        self.add_argument("-o", "--organico-fn", type=str,
                          help="path to CSV containing the available firemen (Default: organico.csv)",
                          default="./organico.csv")
        self.add_argument("-r", "--riporti-fn", type=str,
                          help="path to CSV containing last year's extra and onerous shifts (Default: riporti.csv)",
                          default="./riporti.csv")
        self.add_argument("-p", "--partenza", type=str,
                          help="path to a turni CSV (e.g. from a previous run) used as the solver's starting solution")
        self.add_argument("-t", "--time-limit", type=int,
                          help="time limit in seconds (Default: no limit)", default=0)
        self.add_argument("-v", "--verbose", help="enable verbose solver output",
                          action="store_true")


class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        return f"{record.levelname}: {message}" if record.levelno >= logging.WARNING else message


def setup_logging(log_file):
    logging.addLevelName(logging.WARNING, "ATTENZIONE")
    logging.addLevelName(logging.ERROR, "ERRORE")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ConsoleFormatter("%(message)s"))
    root.addHandler(console)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(file_handler)


t0 = time.time()
parser = VVFParser()
args = parser.parse_args()
setup_logging(args.log_file)
logger = logging.getLogger("main")

logger.info(r"""  __     ____     _______   _____                           _                   
  \ \   / /\ \   / /  ___| |_   _|   _ _ __ _ __   __ _ ___(_) ___  _ __   ___  
   \ \ / /  \ \ / /| |_      | || | | | '__| '_ \ / _` |_  / |/ _ \| '_ \ / _ \ 
    \ V /    \ V / |  _|     | || |_| | |  | | | | (_| |/ /| | (_) | | | |  __/ 
     \_/      \_/  |_|       |_| \__,_|_|  |_| |_|\__,_/___|_|\___/|_| |_|\___| 
                                                                                
""")

model = vvf_turnazione.Turnazione(args)
model.solve()

# model = vvf_affiancamenti.ILPAffiancamenti(model)
# model.solve()

vvf_io.save_solution_to_files(model)

t1 = time.time()
logger.info("Soluzione trovata in {0:.2f} secondi.".format(t1 - t0))
