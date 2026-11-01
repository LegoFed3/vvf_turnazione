# from __future__ import print_function
from ortools.sat.python import cp_model
import datetime as dt
import logging
import math
import vvf_io

logger = logging.getLogger(__name__)


class ILPAffiancamenti:
    def __init__(self, turnazione):
        logger.info("* Creo il modello per gli affiancamenti...")
        # Collections
        self.giorno_squadra = {}
        self.var_notti = {}
        self.var_sabati = {}
        self.var_festivi = {}
        self.var_servizi_vigile = {}
        self.var_cost_servizi_vigile = {}
        self.var_differenza_servizi = {}

        # Model
        self.model = cp_model.CpModel()

        self.args = turnazione.args
        self.solution = turnazione.solution
        self.servizi_per_vigile = turnazione.servizi_per_vigile
        self.DB = turnazione.DB

        self.data_inizio = turnazione.data_inizio
        self.data_fine = turnazione.data_fine
        self.anno = turnazione.anno

        logger.info("N.Y.I.")

    def solve(self):
        return
