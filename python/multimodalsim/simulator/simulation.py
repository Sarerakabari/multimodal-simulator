import logging
from typing import Optional, Any

from multimodalsim.config.simulation_config import SimulationConfig
from multimodalsim.observer.data_collector import DataCollector
from multimodalsim.observer.environment_observer import EnvironmentObserver
from multimodalsim.optimization.optimization import Optimization
from multimodalsim.simulator.coordinates import Coordinates
from multimodalsim.simulator.environment import Environment
from multimodalsim.simulator.event import RecurrentTimeSyncEvent
from multimodalsim.simulator.event_queue import EventQueue

from multimodalsim.simulator.passenger_event import PassengerRelease
from multimodalsim.simulator.request import Trip
from multimodalsim.simulator.travel_times import TravelTimes
from multimodalsim.simulator.vehicle import Vehicle, Route
from multimodalsim.simulator.vehicle_event import VehicleReady

logger = logging.getLogger(__name__)

# Classe principale représentant la simulation multimodale
class Simulation:

    def __init__(self, optimization: Optimization, trips: list[Trip],
                 vehicles: list[Vehicle],
                 routes_by_vehicle_id: dict[str | int, Route],
                 network: Optional[Any] = None,
                 environment_observer: Optional[EnvironmentObserver] = None,
                 coordinates: Optional[Coordinates] = None,
                 travel_times: Optional[TravelTimes] = None,
                 config: Optional[str | SimulationConfig] = None) -> None:
        """
        Initialisation de la simulation avec tous les composants nécessaires : optimisation, trajets, véhicules, etc.
        """
         # Initialisation de l'environnement avec la configuration donnée
        self.__env = Environment(optimization, network=network,
                                 coordinates=coordinates,
                                 travel_times=travel_times)
        # Initialisation de la file d'attente des événements
        self.__queue = EventQueue(self.__env)
         # Initialisation de l'observateur de l'environnement
        self.__environment_observer = environment_observer
        # Chargement de la configuration de la simulation
        self.__load_config(config)
        # Création des événements pour chaque véhicule (VehicleReady)
        self.__create_vehicle_ready_events(vehicles, routes_by_vehicle_id)
        # Création des événements de libération des passagers (PassengerRelease)
        self.__create_passenger_release_events(trips)
        # Initialisation de l'heure de départ
        self.__initialize_time(vehicles, trips)

    @property
    def data_collectors(self) -> Optional[list[DataCollector]]:
        """
        Récupère les collecteurs de données s'ils sont définis dans l'observateur de l'environnement.
        """
        if self.__environment_observer is not None:
            data_collectors = self.__environment_observer.data_collectors
        else:
            data_collectors = None
        return data_collectors

    def simulate(self, max_time: Optional[float] = None) -> None:
        """
        Effectue la simulation en fonction de la file d'événements. La simulation s'arrête 
        lorsque la file est vide ou que le temps maximal est atteint.
        """
        max_time = self.__max_time if max_time is None else max_time

        # Boucle principale de la simulation
        while not self.__queue.is_empty():

            current_event = self.__queue.pop() # Récupère l'événement suivant dans la file d'attente


            self.__env.current_time = current_event.time # Mise à jour du temps actuel de l'environnement

            if max_time is not None and self.__env.current_time > max_time:
                break # Arrêter la simulation si le temps maximal est dépassé
            # Visualisation de l'environnement au moment de l'événement
            self.__visualize_environment(current_event, current_event.index,
                                         current_event.priority)
            # Traitement de l'événement
            process_event = current_event.process(self.__env)
            logger.debug("process_event: {}".format(process_event))
            # Collecte de données sur l'événement en cours
            self.__collect_data(current_event, current_event.index,
                                current_event.priority)
        # Fin de la simulation
        logger.info("\n***************\nEND OF SIMULATION\n***************")
        self.__visualize_environment()

    def __load_config(self, config):
        """
        Charge la configuration de la simulation, soit depuis un fichier de configuration,
        soit en utilisant la configuration par défaut.
        """
        if isinstance(config, str):
            config = SimulationConfig(config) # Chargement de la configuration à partir d'un fichier
        elif not isinstance(config, SimulationConfig):
            config = SimulationConfig() # Utilisation de la configuration par défaut
        # Initialisation des paramètres de la simulation à partir de la configuration
        self.__max_time = config.max_time
        self.__speed = config.speed
        self.__time_step = config.time_step
        self.__update_position_time_step = config.update_position_time_step

    def __create_vehicle_ready_events(self, vehicles, routes_by_vehicle_id):
        """
        Crée les événements pour chaque véhicule (VehicleReady).
        Ces événements sont ajoutés à la file d'attente pour être traités.
        """
        for vehicle in vehicles:
            route = routes_by_vehicle_id[vehicle.id] \
                if vehicle.id in routes_by_vehicle_id else None

            VehicleReady(vehicle, route, self.__queue,
                         self.__update_position_time_step).add_to_queue()

    def __create_passenger_release_events(self, trips):
        """
        Crée les événements de libération des passagers (PassengerRelease).
        Chaque événement est associé à un trajet et ajouté à la file d'attente.
        """
        for trip in trips:
            PassengerRelease(trip, self.__queue).add_to_queue()

    def __initialize_time(self, vehicles, trips):
        """
        Initialise l'heure de départ de la simulation en fonction des véhicules et des trajets.
        """
        # Recherche du temps de libération le plus tôt parmi les véhicules
        first_vehicle_event_time = self.__find_smallest_release_time(vehicles)
        # Recherche du temps de libération le plus tôt parmi les trajets
        first_event_time = self.__find_smallest_release_time(
            trips, first_vehicle_event_time)

        self.__env.current_time = first_event_time # Initialisation du temps de départ
        # Si un pas de temps est défini, un événement de synchronisation récurrent est ajouté
        if self.__time_step is not None:
            RecurrentTimeSyncEvent(self.__queue, first_event_time,
                                   self.__time_step,
                                   self.__speed).add_to_queue()

    def __find_smallest_release_time(self, objects_list,
                                     smallest_release_time=None):
        """
        Trouve le temps de libération le plus tôt parmi une liste d'objets.
        """
        if smallest_release_time is None:
            smallest_release_time = objects_list[0].release_time \
                if len(objects_list) > 0 else None

        for obj in objects_list:
            if obj.release_time < smallest_release_time:
                smallest_release_time = obj.release_time

        return smallest_release_time

    def __visualize_environment(self, current_event=None, event_index=None,
                                event_priority=None):
        """
        Visualise l'environnement à chaque événement, si un observateur est défini.
        """
        if self.__environment_observer is not None:
            for visualizer in self.__environment_observer.visualizers:
                visualizer.visualize_environment(self.__env, current_event,
                                                 event_index,
                                                 event_priority)

    def __collect_data(self, current_event=None, event_index=None, 
                       event_priority=None):
        """
        Collecte des données sur l'événement en cours via les collecteurs de données définis dans l'observateur.
        """
        if self.__environment_observer is not None:
            for data_collector in self.__environment_observer.data_collectors:
                data_collector.collect(self.__env, current_event,
                                       event_index, event_priority)
