# Importation des modules nécessaires
import logging
import time
from threading import Thread, Condition
import multiprocessing as mp
from typing import Optional, Callable

# Importation des modules internes relatifs à la simulation multimodale et à l'optimisation
from multimodalsim.optimization.state import State
from multimodalsim.simulator.event import ActionEvent, TimeSyncEvent
import multimodalsim.simulator.vehicle as vehicle_module

import multimodalsim.simulator.request as request
import multimodalsim.simulator.passenger_event as passenger_event_process
import multimodalsim.simulator.vehicle_event as vehicle_event_process
from multimodalsim.state_machine.status import OptimizationStatus
import multimodalsim.simulator.event_queue as event_queue
import multimodalsim.simulator.environment as environment
import multimodalsim.optimization.optimization as optimization_module
# Initialisation du logger pour suivre les événements dans le code
logger = logging.getLogger(__name__)

# Classe principale pour l'optimisation des événements dans la simulation
class Optimize(ActionEvent):
    def __init__(self, time: float, queue: 'event_queue.EventQueue',
                 multiple_optimize_events: Optional[bool] = None,
                 batch: Optional[float] = None,
                 max_optimization_time: Optional[float] = None,
                 asynchronous: Optional[bool] = None) -> None:
        """
        Initialisation de l'événement d'optimisation avec des paramètres personnalisés.
        """
        # Charge les paramètres de configuration à partir de la configuration de l'environnement de simulation
        self.__load_parameters_from_config(queue.env.optimization,
                                           multiple_optimize_events, batch,
                                           max_optimization_time, asynchronous)
        # Ajuste le temps d'exécution pour qu'il soit un multiple de 'batch', si nécessaire
        if self.__batch is not None:
            # Round to the smallest integer greater than or equal to time that
            # is also a multiple of batch.
            time = time + (batch - (time % batch)) % batch
        # Appel du constructeur parent (ActionEvent) pour initialiser l'événement
        super().__init__('Optimize', queue, time,
                         event_priority=self.VERY_LOW_PRIORITY,
                         state_machine=queue.env.optimization.state_machine)

    def process(self, env: 'environment.Environment') -> str:
        """
        Processus de traitement de l'événement 'Optimize'.
        """
        if self.state_machine.current_state.status \
                == OptimizationStatus.OPTIMIZING:
            with env.optimize_cv:
                env.optimize_cv.wait()
            self.add_to_queue()
            process_message = 'Optimize process is put back in the event queue'
        else:
             # Sinon, on continue normalement avec l'optimisation
            process_message = super().process(env)

        return process_message

    def _process(self, env: 'environment.Environment') -> str:
        """
        Implémentation du processus d'optimisation dans l'environnement.
        """
        # Extraction des statistiques de l'environnement
        stats_extractor = env.optimization.environment_statistics_extractor # Condition pour synchroniser l'optimisation
        env_stats = stats_extractor.extract_environment_statistics(env) # Mise à jour de l'état de l'optimisation
        # Vérification si une optimisation est nécessaire
        if env.optimization.need_to_optimize(env_stats):
            env.optimize_cv = Condition()
            # Choix de l'optimisation asynchrone ou synchrone
            env.optimization.state = env.get_new_state()

            if self.__asynchronous:
                self.__optimize_asynchronously(env)
            else:
                self.__optimize_synchronously(env)
        else:
            # Si l'optimisation n'est pas nécessaire, on génère un résultat d'optimisation vide
            optimization_result = optimization_module.OptimizationResult(
                None, [], [])
            EnvironmentUpdate(optimization_result, self.queue).add_to_queue()

        return 'Optimize process is implemented'

    def add_to_queue(self) -> None:

        """
        Ajoute l'événement à la file d'attente si nécessaire.
        """

        if self.__multiple_optimize_events or not \
                self.queue.is_event_type_in_queue(self.__class__, self.time):
            super().add_to_queue()

    def __optimize_synchronously(self, env):
        """
        Optimisation synchrone : bloque l'exécution, effectue l'optimisation et met à jour l'environnement.
        """
        # Gel des routes pendant l'optimisation
        env.optimization.state.freeze_routes_for_time_interval(
            env.optimization.freeze_interval)
        # Exécution de l'optimisation
        optimization_result = env.optimization.dispatch(
            env.optimization.state)
        # Dégel des routes après l'optimisation
        env.optimization.state.unfreeze_routes_for_time_interval(
            env.optimization.freeze_interval)
        # Envoi des résultats de l'optimisation à la file d'attente
        EnvironmentUpdate(optimization_result, self.queue).add_to_queue()

    def __optimize_asynchronously(self, env):
        """
        Optimisation asynchrone : lance l'optimisation dans un thread séparé.
        """
        hold_cv = Condition() # Condition pour attendre la fin de l'optimisation
        # Création de l'événement de mise en pause pendant l'optimisation
        hold_event = Hold(self.queue, env.current_time
                          + env.optimization.freeze_interval, hold_cv,
                          self.__max_optimization_time)
        hold_event.add_to_queue()
        # Création et démarrage du thread pour l'optimisation asynchrone
        optimize_thread = Thread(target=self.__optimize_in_new_thread,
                                 args=(env, hold_cv, hold_event))
        optimize_thread.start()

    def __optimize_in_new_thread(self, env, hold_cv, hold_event):
        """
        Fonction exécutée dans un thread séparé pour l'optimisation asynchrone.
        """
        # Gel des routes pendant l'optimisation
        env.optimization.state.freeze_routes_for_time_interval(
            env.optimization.freeze_interval)
        # Utilisation de multiprocessing pour gérer les données partagées
        with mp.Manager() as manager:
            process_dict = self.__create_process_dict(env, manager)
            # Création et lancement du processus d'optimisation
            opt_process = self.__create_optimize_process(process_dict,
                                                         hold_event)
            opt_process.start()
            opt_process.join() # Attente de la fin du processus d'optimisation
             # Mise à jour de l'environnement avec les résultats de l'optimisation
            self.__create_environment_update(process_dict, hold_event)
        # Dégel des routes après l'optimisation
        env.optimization.state.unfreeze_routes_for_time_interval(
            env.optimization.freeze_interval)
        # Notifie l'événement de synchronisation que l'optimisation est terminée
        with env.optimize_cv:
            env.optimize_cv.notify()

    def __create_process_dict(self, env, manager):
        """
        Crée un dictionnaire partagé pour le processus d'optimisation.
        """

        process_dict = manager.dict()
        process_dict["state"] = env.optimization.state
        process_dict["dispatch_function"] = env.optimization.dispatch
        process_dict["optimization_result"] = None

        return process_dict

    def __create_optimize_process(self, process_dict, hold_event):
        """
        Crée et retourne un processus de dispatch pour l'optimisation.
        """
        opt_process = DispatchProcess(dispatch=Optimize.dispatch,
                                      process_dict=process_dict)
        with hold_event.cv:
            hold_event.optimization_process = opt_process

        return opt_process

    def __create_environment_update(self, process_dict, hold_event):
        """
        Crée une mise à jour de l'environnement avec les résultats de l'optimisation.
        """
        with hold_event.cv:
            hold_event.cancelled = True
            optimization_result = process_dict["optimization_result"]
            EnvironmentUpdate(optimization_result,
                              self.queue).add_to_queue()
            hold_event.cv.notify()

    @staticmethod
    def dispatch(dispatch_function: Callable,
                 state: State) -> 'optimization_module.OptimizationResult':
        """
        Effectue l'optimisation en appelant la fonction de dispatch et retourne les résultats.
        """
        optimization_result = dispatch_function(state)

        return optimization_result

    def __load_parameters_from_config(self, optimization,
                                      multiple_optimize_events, batch,
                                      max_optimization_time, asynchronous):
        """
        Charge les paramètres de configuration de l'optimisation.
        """

        config = optimization.config
        # Récupère les paramètres à partir de la configuration, en utilisant les valeurs par défaut si nécessaires


        self.__multiple_optimize_events = config.multiple_optimize_events \
            if multiple_optimize_events is None else multiple_optimize_events
        self.__batch = config.batch if batch is None else config.batch

        self.__asynchronous = config.asynchronous \
            if asynchronous is None else asynchronous

        max_optimization_time = config.max_optimization_time \
            if max_optimization_time is None else max_optimization_time
        self.__max_optimization_time = optimization.freeze_interval \
            if max_optimization_time is None else max_optimization_time

# Classe qui gère la mise à jour de l'environnement après une optimisation  
class EnvironmentUpdate(ActionEvent):
    def __init__(self,
                 optimization_result: 'optimization_module.OptimizationResult',
                 queue: 'event_queue.EventQueue') -> None:
        """
        Initialise l'événement de mise à jour de l'environnement.
        Cette classe gère les modifications des véhicules et des demandes après l'optimisation.
        """
        super().__init__('EnvironmentUpdate', queue,
                         state_machine=queue.env.optimization.state_machine)
        self.__optimization_result = optimization_result

    def _process(self, env: 'environment.Environment') -> str:
        """
        Processus de mise à jour de l'environnement basé sur les résultats de l'optimisation.
        """
        # Met à jour les demandes modifiées après optimisation
        for trip in self.__optimization_result.modified_requests:
            next_legs = trip.next_legs
            next_leg_assigned_vehicle = trip.next_legs[0].assigned_vehicle

            passenger_update = request.PassengerUpdate(
                next_leg_assigned_vehicle.id, trip.id, next_legs)
            passenger_event_process.PassengerAssignment(
                passenger_update, self.queue).add_to_queue()
        # Met à jour les véhicules modifiés après optimisation
        for veh in self.__optimization_result.modified_vehicles:
            route = \
                self.__optimization_result.state.route_by_vehicle_id[veh.id]
            if route.current_stop is not None:
                # Copie des informations des passagers à bord et de l'heure de départ du stop actuel
                current_stop_modified_passengers_to_board = \
                    route.current_stop.passengers_to_board
                current_stop_departure_time = \
                    route.current_stop.departure_time
            else:
                current_stop_modified_passengers_to_board = None
                current_stop_departure_time = None

            # Ajoute les legs assignés du véhicule qui ont été modifiés pendant l'optimisation
            modified_trips_ids = [modified_trip.id for modified_trip in
                                  self.__optimization_result.modified_requests]
            modified_assigned_legs = [leg for leg in route.assigned_legs
                                      if leg.trip.id in modified_trips_ids]

            next_stops = route.next_stops
            route_update = vehicle_module.RouteUpdate(
                veh.id, current_stop_modified_passengers_to_board, next_stops,
                current_stop_departure_time, modified_assigned_legs)
            vehicle_event_process.VehicleNotification(
                route_update, self.queue).add_to_queue()
         # Ajoute un événement pour marquer que l'environnement est inactif après la mise à jour
        EnvironmentIdle(self.queue).add_to_queue()

        return 'Environment Update process is implemented'

# Classe pour marquer l'environnement comme inactif après la mise à jour
class EnvironmentIdle(ActionEvent):
    def __init__(self, queue: 'event_queue.EventQueue'):
        """
        Initialise l'événement pour marquer l'environnement comme inactif après la mise à jour.
        """
        super().__init__('EnvironmentIdle', queue,
                         state_machine=queue.env.optimization.state_machine)

    def _process(self, env: 'environment.Environment') -> str:
        """
        Processus de marquage de l'environnement comme inactif.
        """
        return 'Environment Idle process is implemented'

# Classe pour gérer l'événement de pause pendant l'optimisation (attente de l'optimisation)
class Hold(TimeSyncEvent):
    def __init__(self, queue: 'event_queue.EventQueue', event_time: float,
                 cv: Condition, max_optimization_time: float) -> None:
        """
        Initialise l'événement de pause (Hold) qui synchronise l'exécution pendant l'optimisation.
        """
        super().__init__(queue, event_time,
                         max_waiting_time=max_optimization_time,
                         event_name='Hold')

        self.__cv = cv # Condition utilisée pour la synchronisation
        self.__max_optimization_time = max_optimization_time # Temps maximum d'optimisation
        self.__timestamp = time.time() # Enregistrement du timestamp

        self.__optimization_process = None # Processus d'optimisation en attente
        # Délai d'attente pour la terminaison du processus d'optimisation
        self.__termination_waiting_time = \
            queue.env.optimization.config.termination_waiting_time

    @property
    def cv(self) -> Condition:
        return self.__cv

    @property
    def optimization_process(self) -> 'DispatchProcess':
        return self.__optimization_process

    @optimization_process.setter
    def optimization_process(self, optimization_process: 'DispatchProcess'):
        self.__optimization_process = optimization_process

    def _synchronize(self) -> None:
        # Délai d'attente pour la terminaison du processus d'optimisation
        with self.__cv:
            if not self.cancelled:
                wait_return = self.__cv.wait(timeout=self._waiting_time)
                if not wait_return:
                    self.__terminate_process() # Si l'optimisation prend trop de temps, on termine le processus

    def __terminate_process(self):
        """
        Termine le processus d'optimisation si celui-ci dépasse le délai imparti.
        """
        if self.__optimization_process.is_alive():
            logger.warning("Terminate optimization process".format(
                self.__termination_waiting_time))
            self.__optimization_process.terminate()
            time.sleep(self.__termination_waiting_time)
            if self.__optimization_process.exitcode is None:
                self.__optimization_process.kill()
            raise RuntimeError("Optimization exceeded the time limit of {} "
                               "seconds.".format(self.__max_optimization_time))

# Classe pour exécuter l'optimisation dans un processus séparé
class DispatchProcess(mp.Process):
    def __init__(self, dispatch: Callable, process_dict: dict) -> None:
        """
        Initialise le processus d'optimisation (DispatchProcess).
        Ce processus exécute l'optimisation dans un thread séparé.
        """
        super().__init__()
        self.__dispatch = dispatch
        self.__process_dict = process_dict

     # Exécution de l'optimisation et mise à jour du résultat
    def run(self) -> None:
        """
        Exécution de l'optimisation dans le processus séparé.
        """
        state = self.__process_dict["state"]
        dispatch_function = self.__process_dict["dispatch_function"]

        optimization_result = self.__dispatch(dispatch_function, state)
        self.__process_dict["optimization_result"] = optimization_result
