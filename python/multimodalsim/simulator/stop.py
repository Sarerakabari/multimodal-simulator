import copy
from typing import Optional
import multimodalsim.simulator.request as request


class Stop:
    """
    Un arrêt représente un lieu où un véhicule arrive pour prendre ou déposer des passagers. Il contient des informations
    sur l'heure d'arrivée et de départ, les passagers concernés, et la localisation de l'arrêt dans le réseau.
    
    Attributs :
    ----------
    arrival_time : float
        Heure d'arrivée du véhicule à l'arrêt.
    departure_time : float
        Heure de départ du véhicule de l'arrêt.
    min_departure_time : float
        Heure minimale à laquelle le véhicule peut quitter l'arrêt.
    cumulative_distance : float
        Distance cumulée parcourue par le véhicule à son arrivée à l'arrêt.
    passengers_to_board : list d'objets Trip
        Liste des passagers qui doivent monter dans le véhicule.
    boarding_passengers : list d'objets Trip
        Liste des passagers qui montent dans le véhicule.
    boarded_passengers : list d'objets Trip
        Liste des passagers déjà montés dans le véhicule.
    passengers_to_alight : list d'objets Trip
        Liste des passagers qui doivent descendre à cet arrêt.
    alighting_passengers : list d'objets Trip
        Liste des passagers en train de descendre du véhicule.
    alighted_passengers : list d'objets Trip
        Liste des passagers déjà descendus du véhicule.
    location : Location
        L'emplacement de l'arrêt, sous forme d'un objet Location (par exemple, coordonnées GPS).
    """

    def __init__(self, arrival_time: float, departure_time: float,
                 location: 'Location',
                 cumulative_distance: Optional[float] = None,
                 min_departure_time: Optional[float] = None) -> None:
        """
        Initialise l'objet Stop avec des attributs essentiels tels que l'heure d'arrivée, l'heure de départ, 
        la localisation et les listes pour la gestion des passagers.
        
        Paramètres :
        ----------
        arrival_time : float
            Heure à laquelle le véhicule arrive à l'arrêt.
        departure_time : float
            Heure à laquelle le véhicule quitte l'arrêt.
        location : Location
            L'emplacement de l'arrêt.
        cumulative_distance : float, optionnel
            Distance cumulée parcourue par le véhicule lors de son arrivée à l'arrêt.
        min_departure_time : float, optionnel
            Heure minimale à laquelle le véhicule peut quitter l'arrêt.
        """
        super().__init__()
        # Initialisation des attributs de l'arrêt
        self.__arrival_time = arrival_time
        self.__departure_time = departure_time
        self.__min_departure_time = min_departure_time
        self.__passengers_to_board = []
        self.__boarding_passengers = []
        self.__boarded_passengers = []
        self.__passengers_to_alight = []
        self.__alighting_passengers = []
        self.__alighted_passengers = []
        self.__location = location
        self.__cumulative_distance = cumulative_distance

    def __str__(self) -> str:
        """
        Retourne une représentation sous forme de chaîne de caractères de l'objet Stop, incluant les IDs de tous 
        les passagers impliqués (en attente de monter, en train de monter, montés, en attente de descendre, en train 
        de descendre, et déjà descendus).
        """
        class_string = str(self.__class__) + ": {"
        for attribute, value in self.__dict__.items():
            if "__passengers_to_board" in attribute:
                class_string += str(attribute) + ": " \
                                + str(list(str(x.id) for x in value)) + ", "
            elif "__boarding_passengers" in attribute:
                class_string += str(attribute) + ": " \
                                + str(list(str(x.id) for x in value)) + ", "
            elif "__boarded_passengers" in attribute:
                class_string += str(attribute) + ": " \
                                + str(list(str(x.id) for x in value)) + ", "
            elif "__passengers_to_alight" in attribute:
                class_string += str(attribute) + ": " \
                                + str(list(str(x.id) for x in value)) + ", "
            elif "alighting_passengers" in attribute:
                class_string += str(attribute) + ": " \
                                + str(list(str(x.id) for x in value)) + ", "
            elif "alighted_passengers" in attribute:
                class_string += str(attribute) + ": " \
                                + str(list(str(x.id) for x in value)) + ", "
            else:
                class_string += str(attribute) + ": " + str(value) + ", "

        class_string += "}"

        return class_string
    # Méthodes d'accès (getters et setters) aux attributs de l'arrêt
    @property
    def arrival_time(self) -> float:
        return self.__arrival_time

    @arrival_time.setter
    def arrival_time(self, arrival_time: float):
        self.__arrival_time = arrival_time

    @property
    def departure_time(self) -> float:
        return self.__departure_time

    @departure_time.setter
    def departure_time(self, departure_time: float):
        """
        Vérifie que l'heure de départ est supérieure ou égale à l'heure minimale de départ autorisée.
        Si ce n'est pas le cas, une exception ValueError est levée.
        """
        if self.__min_departure_time is not None \
                and departure_time < self.__min_departure_time:
            raise ValueError(
                "departure_time ({}) must be greater than or  equal to "
                "min_departure_time ({}).".format(departure_time,
                                                  self.__min_departure_time))
        self.__departure_time = departure_time

    @property
    def min_departure_time(self) -> float:
        return self.__min_departure_time

    @property
    def passengers_to_board(self) -> list['request.Trip']:
        return self.__passengers_to_board

    @passengers_to_board.setter
    def passengers_to_board(self, passengers_to_board: list['request.Trip']):
        self.__passengers_to_board = passengers_to_board

    @property
    def boarding_passengers(self) -> list['request.Trip']:
        return self.__boarding_passengers

    @boarding_passengers.setter
    def boarding_passengers(self, boarding_passengers: list['request.Trip']):
        self.__boarding_passengers = boarding_passengers

    @property
    def boarded_passengers(self) -> list['request.Trip']:
        return self.__boarded_passengers

    @boarded_passengers.setter
    def boarded_passengers(self, boarded_passengers: list['request.Trip']):
        self.__boarded_passengers = boarded_passengers

    @property
    def passengers_to_alight(self) -> list['request.Trip']:
        return self.__passengers_to_alight

    @passengers_to_alight.setter
    def passengers_to_alight(self, passengers_to_alight: list['request.Trip']):
        self.__passengers_to_alight = passengers_to_alight

    @property
    def alighting_passengers(self) -> list['request.Trip']:
        return self.__alighting_passengers

    @property
    def alighted_passengers(self) -> list['request.Trip']:
        return self.__alighted_passengers

    @property
    def location(self) -> 'Location':
        return self.__location

    @property
    def cumulative_distance(self) -> float:
        return self.__cumulative_distance

    def initiate_boarding(self, trip: 'request.Trip'):
        """
        Déplace un passager de la liste des passagers à embarquer vers la liste des passagers en train de monter.
        """
        self.passengers_to_board.remove(trip)
        self.boarding_passengers.append(trip)

    def board(self, trip: 'request.Trip'):
        """
        Déplace un passager de la liste des passagers en train de monter vers la liste des passagers déjà montés.
        """
        self.boarding_passengers.remove(trip)
        self.boarded_passengers.append(trip)

    def initiate_alighting(self, trip: 'request.Trip'):
        """
        Déplace un passager de la liste des passagers à descendre vers la liste des passagers en train de descendre.
        """
        self.passengers_to_alight.remove(trip)
        self.alighting_passengers.append(trip)

    def alight(self, trip: 'request.Trip'):
        """
        Déplace un passager de la liste des passagers en train de descendre vers la liste des passagers déjà descendus.
        """
        self.alighting_passengers.remove(trip)
        self.alighted_passengers.append(trip)

    def __deepcopy__(self, memo: dict) -> 'Stop':
        """
        Crée une copie profonde de l'objet Stop en copiant tous ses attributs, sauf ceux qui sont liés aux passagers 
        (qui doivent être réinitialisés).
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "_Stop__alighted_passengers":
                setattr(result, k, [])
            elif k == "_Stop__alighting_passengers":
                setattr(result, k, [])
            elif k == "_Stop__boarded_passengers":
                setattr(result, k, [])
            elif k == "_Stop__boarding_passengers":
                setattr(result, k, [])
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result


class Location:
    """
    La classe Location est une classe de base qui sert principalement à stocker des informations de base sur 
    l'emplacement d'un véhicule ou d'un passager (par exemple, coordonnées GPS).
    """

    def __init__(self) -> None:
        """
        Initialisation d'un objet Location. Cette classe de base ne contient pas d'attributs spécifiques.
        """
        pass

    def __eq__(self, other: 'Location') -> bool:
        """
        Compare deux objets Location pour voir s'ils sont égaux. Cette méthode est laissée vide dans la classe de base,
        mais elle peut être redéfinie dans les classes filles.
        
        Paramètre :
        ----------
        other : Location
            Un autre objet Location avec lequel comparer.

        Retourne :
        --------
        bool : True si les deux objets sont égaux, sinon False.
        """
        pass


class LabelLocation(Location):
    """
    La classe LabelLocation étend la classe Location. Elle représente un emplacement avec un label (nom) et 
    des coordonnées facultatives (longitude et latitude).
    """
    def __init__(self, label: str, lon: Optional[float] = None,
                 lat: Optional[float] = None) -> None:
        """
        Initialisation d'un objet LabelLocation avec un label et des coordonnées optionnelles.

        Paramètres :
        ----------
        label : str
            Le label (nom) de l'emplacement.
        lon : float, optionnel
            La longitude de l'emplacement.
        lat : float, optionnel
            La latitude de l'emplacement.
        """
        super().__init__()
        self.label = label # Le label identifiant l'emplacement
        self.lon = lon # La longitude (facultative)
        self.lat = lat  # La latitude (facultative)

    def __str__(self) -> str:
        """
        Retourne une représentation sous forme de chaîne de caractères de l'objet LabelLocation, incluant le label
        et les coordonnées, si elles sont spécifiées.

        Retourne :
        --------
        str : Représentation sous forme de chaîne de caractères de l'emplacement.
        """

        if self.lon is not None or self.lat is not None:
            ret_str = "{}: ({},{})".format(self.label, self.lon, self.lat)
        else:
            ret_str = "{}".format(self.label)

        return ret_str

    def __eq__(self, other: 'LabelLocation') -> bool:
        """
        Compare deux objets LabelLocation pour voir s'ils sont égaux, c'est-à-dire si leurs labels sont identiques.

        Paramètre :
        ----------
        other : LabelLocation
            Un autre objet LabelLocation avec lequel comparer.

        Retourne :
        --------
        bool : True si les deux objets ont le même label, sinon False.
        """
        if isinstance(other, LabelLocation):
            return self.label == other.label
        return False

    def __deepcopy__(self, memo: dict) -> 'LabelLocation':
        """
        Crée une copie profonde de l'objet LabelLocation, y compris ses attributs (label, longitude et latitude).

        Paramètre :
        ----------
        memo : dict
            Un dictionnaire pour mémoriser les objets déjà copiés.

        Retourne :
        --------
        LabelLocation : Une copie profonde de l'objet LabelLocation.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, copy.deepcopy(v, memo))
        return result


class TimeCoordinatesLocation(Location):
    """
    La classe TimeCoordinatesLocation étend la classe Location. Elle représente un emplacement avec des 
    coordonnées temporelles : un instant de temps, une longitude et une latitude.
    """
    def __init__(self, time: float, lon: float, lat: float) -> None:
        """
        Initialisation d'un objet TimeCoordinatesLocation avec un temps, une longitude et une latitude.

        Paramètres :
        ----------
        time : float
            Le moment dans le temps auquel cet emplacement est enregistré.
        lon : float
            La longitude de l'emplacement.
        lat : float
            La latitude de l'emplacement.
        """
        super().__init__()
        self.time = time
        self.lon = lon
        self.lat = lat

    def __str__(self) -> str:
        """
        Retourne une représentation sous forme de chaîne de caractères de l'objet TimeCoordinatesLocation, incluant
        le temps, la longitude et la latitude.

        Retourne :
        --------
        str : Représentation sous forme de chaîne de caractères de l'emplacement temporel.
        """
        return "{}: ({},{})".format(self.time, self.lon, self.lat)

    def __eq__(self, other) -> bool:
        """
        Compare deux objets TimeCoordinatesLocation pour voir s'ils sont égaux, c'est-à-dire si leur temps, longitude
        et latitude sont identiques.

        Paramètre :
        ----------
        other : TimeCoordinatesLocation
            Un autre objet TimeCoordinatesLocation avec lequel comparer.

        Retourne :
        --------
        bool : True si les deux objets ont le même temps, longitude et latitude, sinon False.
        """
        if isinstance(other, TimeCoordinatesLocation):
            return self.time == other.time and self.lon == other.lon \
                   and self.lat == other.lat
        return False

    def __deepcopy__(self, memo: dict) -> 'TimeCoordinatesLocation':
        """
        Crée une copie profonde de l'objet TimeCoordinatesLocation, y compris ses attributs (temps, longitude et latitude).

        Paramètre :
        ----------
        memo : dict
            Un dictionnaire pour mémoriser les objets déjà copiés.

        Retourne :
        --------
        TimeCoordinatesLocation : Une copie profonde de l'objet TimeCoordinatesLocation.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, copy.deepcopy(v, memo))
        return result
