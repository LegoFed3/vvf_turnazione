# from __future__ import print_function
from ortools.linear_solver import pywraplp
import datetime as dt
import math
import vvf_io


class ILPAffiancamenti:
    # Collections
    giorno_squadra = {}
    var_notti = {}
    var_sabati = {}
    var_festivi = {}
    var_servizi_vigile = {}
    var_cost_servizi_vigile = {}
    var_differenza_servizi = {}

    # Model
    solver = pywraplp.Solver('VVF_Turnazione', pywraplp.Solver.SCIP_MIXED_INTEGER_PROGRAMMING)

    def __init__(self, turnazione):
        print("* Creo il modello per gli affiancamenti...")
        self.args = turnazione.args
        self.solution = turnazione.solution
        self.servizi_per_vigile = turnazione.servizi_per_vigile
        self.DB = turnazione.DB

        self.data_inizio = turnazione.data_inizio
        self.data_fine = turnazione.data_fine
        self.anno = turnazione.anno

        print("N.Y.I.")

    def solve(self):
        return
