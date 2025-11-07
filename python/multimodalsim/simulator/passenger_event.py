import logging

from multimodalsim.simulator.event import Event, ActionEvent
import multimodalsim.simulator.optimization_event \
    as optimization_event_process
from multimodalsim.simulator.vehicle_event import VehicleBoarded, \
    VehicleAlighted

logger = logging.getLogger(__name__)

# Classe représentant l'événement où un passager est libéré
class PassengerRelease(Event):
    def __init__(self, trip, queue):
        """
        Initialise l'événement de libération du passager. Ce processus consiste à
        ajouter le trajet au système et à vérifier s'il est nécessaire de diviser le trajet
        en legs plus petits.
        """
        super().__init__('PassengerRelease', queue, trip.release_time)
        self.__trip = trip # Le trajet du passager à libérer

    @property
    def trip(self):
        return self.__trip

    def _process(self, env):
        """
        Processus de libération du passager. Le trajet est ajouté au système et
        les legs sont assignés si nécessaire. Si la synchronisation de transfert est désactivée,
        une optimisation est déclenchée.
        """
        env.add_trip(self.__trip) # Ajouter le trajet au système
        env.add_non_assigned_trip(self.__trip) # Ajouter le trajet à la liste des trajets non assignés

        if self.__trip.current_leg is None:
            legs = env.optimization.split(self.__trip, env) # Diviser le trajet en legs si nécessaire
            self.__trip.assign_legs(legs) # Assigner les legs au trajet
        
       

        return 'Done processing Passenger Release'

# Classe représentant l'événement d'assignation d'un passager à un véhicule
class PassengerAssignment(ActionEvent):
    def __init__(self, passenger_update, queue):
        """
        Initialise l'événement d'assignation du passager à un véhicule. 
        L'assignation met à jour les informations concernant le trajet du passager et le véhicule.
        """
        self.__passenger_update = passenger_update # Mettre à jour l'assignation du passager
        self.__trip = queue.env.get_trip_by_id(
            self.__passenger_update.request_id) # Obtenir le trajet du passager
        super().__init__('PassengerAssignment', queue,
                         state_machine=self.__trip.state_machine) # Initialiser l'événement d'assignation

    def _process(self, env):
        """
        Processus d'assignation d'un passager à un véhicule. 
        Mette à jour les legs du trajet et l'assigne à un véhicule.
        """
        self.__env = env
        vehicle = env.get_vehicle_by_id(
            self.__passenger_update.assigned_vehicle_id) # Obtenir le véhicule assigné au passager
        
        # Si un leg est déjà assigné, le mettre à jour
        if self.__passenger_update.current_leg is not None:
            self.__trip.current_leg =\
                self.__env.get_leg_by_id(self.__passenger_update.current_leg.id)

                # Si des legs suivants existent, les mettre à jour  
        if self.__passenger_update.next_legs is not None:
            self.__trip.next_legs =\
                self.__replace_copy_legs_with_actual_legs(
                    self.__passenger_update.next_legs) # Remplacer les legs avec les legs actuels
          # Assigner le véhicule au premier leg du trajet
        self.__trip.next_legs[0].assigned_vehicle = vehicle

        env.remove_non_assigned_trip(self.__trip.id) # Retirer le trajet de la liste des trajets non assignés
        env.add_assigned_trip(self.__trip) # Ajouter le trajet à la liste des trajets assignés
        PassengerReady(self.__trip, self.queue).add_to_queue() # Passer à l'état "PassengerReady"

        return 'Done processing Passenger Assignment'

    def __replace_copy_legs_with_actual_legs(self, legs):
        """
        Remplacer les legs de copie par les legs réels en récupérant les legs correspondants dans l'environnement.
        """
        if type(legs) is list:
            actual_legs = list(
                self.__env.get_leg_by_id(leg.id) for leg in legs)
        else:
            actual_legs = self.__env.get_leg_by_id(legs.id)

        return actual_legs

# Classe représentant l'événement où le passager est prêt
class PassengerReady(ActionEvent):
    def __init__(self, trip, queue):
        """
        Initialise l'événement de "Passager Prêt". Cet événement est déclenché lorsque le passager
        est prêt à embarquer, basé sur l'heure de préparation du trajet.
        """
        super().__init__('PassengerReady', queue,
                         max(trip.ready_time, queue.env.current_time),
                         state_machine=trip.state_machine,
                         event_priority=Event.HIGH_PRIORITY) # Priorité élevée pour cet événement
        self.__trip = trip
    
    def _process(self, env):
        """
        Processus pour marquer un passager comme prêt à embarquer. Il n'y a pas de mise à jour
        spécifique à effectuer dans cet événement à part signaler que le processus est terminé.
        """
        return 'Done processing Passenger Ready process'


# Classe représentant l'événement où le passager monte dans le véhicule
class PassengerToBoard(ActionEvent):
    def __init__(self, trip, queue):
        """
        Initialise l'événement de "Passager à embarquer". Cet événement marque le début du trajet
        du passager lorsqu'il monte dans le véhicule.
        """
        super().__init__('PassengerToBoard', queue,
                         max(trip.ready_time, queue.env.current_time),
                         state_machine=trip.state_machine)
        self.__trip = trip

    def _process(self, env):
        """
        Processus pour marquer qu'un passager commence à embarquer dans le véhicule.
        On démarre le prochain leg du trajet et on assigne l'heure de montée dans le véhicule.
        """
        self.__trip.start_next_leg()
        self.__trip.current_leg.boarding_time = env.current_time
        VehicleBoarded(self.__trip, self.queue).add_to_queue()

        return 'Done processing Passenger To Board process'

# Classe représentant l'événement où le passager descend du véhicule
class PassengerAlighting(ActionEvent):
    def __init__(self, trip, queue):
        """
        Initialise l'événement de "Passager en train de descendre". Cet événement marque
        la fin du trajet du passager lorsque celui-ci descend du véhicule.
        """
        super().__init__('PassengerAlighting', queue,
                         state_machine=trip.state_machine)
        self.__trip = trip

    def _process(self, env):
        """
        Processus pour marquer qu'un passager descend du véhicule. 
        On termine le leg actuel du trajet et on gère les connexions éventuelles.
        """
        self.__trip.current_leg.alighting_time = env.current_time # Assigner l'heure de descente
        VehicleAlighted(self.__trip.current_leg, self.queue).add_to_queue() # Ajouter un événement de descente

        self.__trip.finish_current_leg() # Terminer le leg actuel du trajet
         # Vérifier s'il y a une connexion pour un autre leg
        if self.__trip.next_legs is None or len(self.__trip.next_legs) == 0:
            # Pas de connexion, le trajet est terminé
            logger.debug("No connection: {}".format(self.__trip.id))
        else:
            # Connexion à un autre leg
            logger.debug("Connection: {}".format(self.__trip.id))

            # Réaffecter le trajet comme non assigné
            env.remove_assigned_trip(self.__trip.id)
            env.add_non_assigned_trip(self.__trip)

        

        return 'Done processing Passenger Alighting process'
