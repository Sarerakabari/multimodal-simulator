import pandas as pd
import logging
import sys
sys.path.insert(1, r"C:\Users\kklau\Desktop\Simulator")

from multimodalsim.config.request_generator_config \
    import RequestsGeneratorConfig

logger = logging.getLogger(__name__)


class RequestsGenerator:
    """
    Classe de base pour la génération de demandes de transport.
    Cette classe définit l'interface commune pour tous les générateurs de demandes.
    """
    def __init__(self):
        pass

    def generate_requests(self):
        pass


class CAPRequestsGenerator(RequestsGenerator):
    """
    Générateur de demandes de transport basé sur les données CAP (Comptage Automatique des Passagers).
    
    Cette classe hérite de RequestsGenerator et implémente la génération de demandes
    à partir des données de comptage des passagers et des horaires des véhicules.
    """

    def __init__(self, cap_file_path, stop_times_file_path, config=None, trips_file_path = None):
        """
        Initialise le générateur de demandes CAP.
        
        Args:
            cap_file_path: Chemin vers le fichier de données CAP
            stop_times_file_path: Chemin vers le fichier des temps d'arrêt
            config: Configuration optionnelle du générateur
            trips_file_path: Chemin vers le fichier des trajets
        """
        super().__init__()

        # Chargement de la configuration
        config = RequestsGeneratorConfig() if config is None else config
        self.__load_config(config)

        # Initialisation du formateur CAP
        self.__cap_formatter = CAPFormatter(cap_file_path,
                                          stop_times_file_path, config)

        # Initialisation des attributs
        self.__requests_df = None
        self.__stop_times_file_path = stop_times_file_path
        self.__trips_file_path = trips_file_path

    @property
    def requests_df(self):
        """Retourne le DataFrame des demandes générées."""
        return self.__requests_df

    def generate_requests(self, max_connection_time=None,
                        release_time_delta=None, ready_time_delta=None,
                        due_time_delta=None,
                        PI = False):
        """
        Génère les demandes de transport à partir des données CAP.
        
        Args:
            max_connection_time: Temps maximum pour une correspondance
            release_time_delta: Délai avant la libération de la demande
            ready_time_delta: Délai avant que la demande soit prête
            due_time_delta: Délai avant l'échéance de la demande
            PI: Indicateur de performance
            
        Returns:
            DataFrame contenant les demandes générées
        """
        # Utilisation des valeurs par défaut si non spécifiées
        if max_connection_time is None:
            max_connection_time = self.__max_connection_time
        if release_time_delta is None:
            release_time_delta = self.__release_time_delta
        if ready_time_delta is None:
            ready_time_delta = self.__ready_time_delta
        if due_time_delta is None:
            due_time_delta = self.__due_time_delta

        # Formatage et extraction des demandes
        formatted_cap_df = self.__cap_formatter.format_cap(max_connection_time)
        self.__extract_requests_from_cap(formatted_cap_df)
        self.__format_requests(release_time_delta, ready_time_delta,
                             due_time_delta)
        self.__get_first_possible_transfers_for_requests(time_limit=300, PI = PI)

        return self.__requests_df

    def save_to_csv(self, requests_file_path, requests_df=None):
        """
        Sauvegarde les demandes dans un fichier CSV.
        
        Args:
            requests_file_path: Chemin du fichier de sortie
            requests_df: DataFrame des demandes à sauvegarder
        """
        if requests_df is None and self.__requests_df is None:
            raise ValueError("Requests must be generated first!")

        if requests_df is None:
            requests_df = self.__requests_df

        requests_df.to_csv(requests_file_path, sep=";")

    def __load_config(self, config):
        """
        Charge la configuration du générateur.
        
        Args:
            config: Objet de configuration contenant les paramètres
        """
        # Chargement des paramètres de configuration
        self.__max_connection_time = config.max_connection_time
        self.__release_time_delta = config.release_time_delta
        self.__ready_time_delta = config.ready_time_delta
        self.__due_time_delta = config.due_time_delta
        self.__id_col = config.id_col
        self.__arrival_time_col = config.arrival_time_col
        self.__boarding_time_col = config.boarding_time_col
        self.__origin_stop_id_col = config.origin_stop_id_col
        self.__destination_stop_id_col = config.destination_stop_id_col
        self.__boarding_type_col = config.boarding_type_col

    def __extract_requests_from_cap(self, formatted_cap_df):
        """
        Extrait les demandes à partir des données CAP formatées.
        
        Args:
            formatted_cap_df: DataFrame des données CAP formatées
            
        Returns:
            DataFrame des demandes extraites
        """
        # Regroupement des données par identifiant client
        cap_grouped_by_id_client = formatted_cap_df.groupby(self.__id_col)

        all_request_rows_list = []
        for name, group in cap_grouped_by_id_client:
            request_legs = []
            first_row = True
            sorted_group = group.sort_values(self.__boarding_time_col)
            for index, row in sorted_group.iterrows():
                if first_row:
                    request_row = row[[self.__id_col,
                                     self.__origin_stop_id_col,
                                     self.__boarding_time_col]]
                    first_row = False

                # Ajout des informations sur les segments de trajet
                request_legs.append(
                    (row[self.__origin_stop_id_col],
                     row[self.__destination_stop_id_col],
                     row["S_VEHJOBID_IDJOURNALIER"]))

                # Traitement des premières montées et des correspondances
                if row["boarding_type_lead"] == "1ère montée" or pd.isnull(
                        row["boarding_type_lead"]):
                    request_row = pd.concat([request_row, row[
                        [self.__destination_stop_id_col,
                         self.__arrival_time_col]]])
                    request_row["legs"] = request_legs
                    all_request_rows_list.append(request_row)
                    request_legs = []
                    first_row = True

        # Création du DataFrame final
        self.__requests_df = pd.concat(all_request_rows_list, axis=1).T

        return self.__requests_df

    def __format_requests(self, release_time_delta, ready_time_delta,
                        due_time_delta):
        """
        Formate les demandes avec les délais spécifiés.
        
        Args:
            release_time_delta: Délai avant la libération
            ready_time_delta: Délai avant que la demande soit prête
            due_time_delta: Délai avant l'échéance
            
        Returns:
            DataFrame des demandes formatées
        """
        # Formatage des colonnes de base
        self.__requests_df["origin"] = \
            self.__requests_df[self.__origin_stop_id_col]
        self.__requests_df["destination"] = \
            self.__requests_df[self.__destination_stop_id_col]
        self.__requests_df["nb_passengers"] = 1
        
        # Calcul des temps de libération, de disponibilité et d'échéance
        self.__requests_df["release_time"] = \
            self.__requests_df[self.__boarding_time_col] - release_time_delta
        self.__requests_df["ready_time"] = \
            self.__requests_df[self.__boarding_time_col] - ready_time_delta
        self.__requests_df["due_time"] = \
            self.__requests_df[self.__arrival_time_col] + due_time_delta

        # Nettoyage et conversion des données
        self.__requests_df = self.__requests_df.drop(
            [self.__origin_stop_id_col, self.__boarding_time_col,
             self.__destination_stop_id_col, self.__arrival_time_col], axis=1)
        self.__requests_df["origin"] = self.__requests_df["origin"].apply(int)
        self.__requests_df["destination"] = \
            self.__requests_df["destination"].apply(int)
        self.__requests_df["release_time"] = \
            self.__requests_df["release_time"].apply(int)
        self.__requests_df["ready_time"] = \
            self.__requests_df["ready_time"].apply(int)
        self.__requests_df["due_time"] = \
            self.__requests_df["due_time"].apply(int)

        # Réindexation et formatage des identifiants
        self.__requests_df.reset_index(drop=True, inplace=True)
        self.__requests_df.reset_index(inplace=True)

        self.__requests_df["ID"] = self.__requests_df[self.__id_col] + "_" \
                                 + self.__requests_df[
                                     "index"].apply(str)
        self.__requests_df.index = self.__requests_df["ID"]
        self.__requests_df.drop([self.__id_col, "index", "ID"], axis=1,
                              inplace=True)

        # Sélection des colonnes finales
        columns = ["origin", "destination", "nb_passengers", "release_time",
                 "ready_time", "due_time", "legs"]

        self.__requests_df = self.__requests_df[columns]

        return self.__requests_df[columns]

    def __get_first_possible_transfers_for_requests(self, time_limit = 300, PI = False):
        """
        Optimise les correspondances possibles pour les demandes avec transferts.
        
        Args:
            time_limit: Fenêtre de temps pour considérer les correspondances
            PI: Indicateur de performance
        """
        # Lecture des fichiers de données
        stop_times_df = pd.read_csv(self.__stop_times_file_path, delimiter=",")
        stop_times_df["arrival_time"] = stop_times_df["arrival_time"].apply(int)
        stop_times_df["departure_time"] = stop_times_df["departure_time"].apply(int)
        stop_times_df["stop_id"] = stop_times_df["stop_id"].apply(int)
        stop_times_df["trip_id"] = stop_times_df["trip_id"].apply(int)
        stop_times_df["planned_arrival_time"] = stop_times_df["planned_arrival_time"].apply(int)

        # Création des dictionnaires de données
        stop_times_grouped_by_trip = stop_times_df.groupby("trip_id")
        stop_times_dict = stop_times_grouped_by_trip.apply(lambda x: list(zip(x["arrival_time"], x["departure_time"], x["stop_id"], x["planned_arrival_time"])))
        stop_times_dict = stop_times_dict.to_dict()

        # Lecture des trajets
        trips_df = pd.read_csv(self.__trips_file_path, delimiter=",")
        trips_df["trip_id"] = trips_df["trip_id"].apply(int)
        trips_df["route_id"] = trips_df["route_id"].apply(str)
        route_id_dict = dict(zip(trips_df["trip_id"], trips_df["route_id"]))      

        # Création du dictionnaire des temps de passage
        passage_times_at_stops = {}
        all_route_ids = trips_df["route_id"].unique()
        for route_id in all_route_ids:
            passage_times_at_stops[route_id] = {}
        for trip_id in stop_times_dict.keys():
            route_id = route_id_dict[trip_id]
            for arrival_time, departure_time, stop_id, planned_arrival_time in stop_times_dict[trip_id]:
                if stop_id not in passage_times_at_stops[route_id]:
                    passage_times_at_stops[route_id][stop_id] = []
                passage_times_at_stops[route_id][stop_id].append((arrival_time, departure_time, trip_id, planned_arrival_time, min(arrival_time, planned_arrival_time)))
        for route_id in all_route_ids:
            for stop_id in passage_times_at_stops[route_id].keys():
                passage_times_at_stops[route_id][stop_id] = sorted(passage_times_at_stops[route_id][stop_id], key=lambda x: x[4])
        
        # Traitement des demandes
        requests_df = self.__requests_df.copy()
        counter = 0
        ready_time_delta = 60
        if PI:
            ready_time_delta = 120
        all_counter = 0
        updated_resquests = {}
        
        # Optimisation des correspondances pour chaque demande
        for request_id, request in requests_df.iterrows():
            legs = request["legs"]
            if len(legs) > 1:
                all_counter += 1
            # Ajustement du temps de disponibilité
            first_leg_origin_stop_id = legs[0][0]
            first_trip_id = legs[0][2]
            first_route_id = route_id_dict[first_trip_id]
            passage_times = passage_times_at_stops[first_route_id][first_leg_origin_stop_id]
            original_start_tuple = next((stop_tuple for stop_tuple in passage_times if stop_tuple[2] == first_trip_id), None)
            if original_start_tuple is not None:
                original_planned_arrival_time = original_start_tuple[3]
                request['ready_time'] = original_planned_arrival_time - ready_time_delta
            
            updated_resquests[request_id] = request
            
        # Mise à jour du DataFrame des demandes
        updated_requests_df = pd.DataFrame.from_dict(updated_resquests, orient="index")
        self.__requests_df = updated_requests_df

class CAPFormatter:
    """
    Classe pour le formatage des données CAP (Comptage Automatique des Passagers).
    
    Cette classe gère la lecture, le prétraitement et le formatage des données
    de comptage des passagers pour les rendre compatibles avec le générateur de demandes.
    """

    def __init__(self, cap_file_path, stop_times_file_path, config):
        """
        Initialise le formateur CAP.
        
        Args:
            cap_file_path: Chemin vers le fichier de données CAP
            stop_times_file_path: Chemin vers le fichier des temps d'arrêt
            config: Configuration du formateur
        """
        # Chargement de la configuration
        self.__load_config(config)

        # Lecture des fichiers de données
        self.__read_cap_csv(cap_file_path)
        self.__read_stop_times_csv(stop_times_file_path)

    @property
    def cap_df(self):
        """Retourne le DataFrame des données CAP formatées."""
        return self.__cap_df

    def format_cap(self, max_connection_time):
        """
        Formate les données CAP selon les paramètres spécifiés.
        
        Args:
            max_connection_time: Temps maximum pour une correspondance
            
        Returns:
            DataFrame des données CAP formatées
        """
        # Prétraitement et formatage des données
        self.__preformat()
        self.__filter()
        self.__add_boarding_type(max_connection_time)

        return self.__cap_df

    def __load_config(self, config):
        """
        Charge la configuration du formateur.
        
        Args:
            config: Objet de configuration contenant les paramètres
        """
        # Chargement des noms de colonnes et paramètres
        self.__id_col = config.id_col
        self.__arrival_time_col = config.arrival_time_col
        self.__boarding_time_col = config.boarding_time_col
        self.__origin_stop_id_col = config.origin_stop_id_col
        self.__destination_stop_id_col = config.destination_stop_id_col
        self.__boarding_type_col = config.boarding_type_col
        self.__origin_stop_lat_col = config.origin_stop_lat_col
        self.__origin_stop_lon_col = config.origin_stop_lon_col
        self.__destination_stop_lat_col = config.destination_stop_lat_col
        self.__destination_stop_lon_col = config.destination_stop_lon_col

    def __read_cap_csv(self, cap_file_path):
        """
        Lit le fichier CSV des données CAP.
        
        Args:
            cap_file_path: Chemin vers le fichier de données CAP
        """
        self.__cap_df = pd.read_csv(cap_file_path, delimiter=";")

    def __read_stop_times_csv(self, stop_times_file_path):
        """
        Lit le fichier CSV des temps d'arrêt.
        
        Args:
            stop_times_file_path: Chemin vers le fichier des temps d'arrêt
        """
        self.__stop_times_df = pd.read_csv(stop_times_file_path,
                                         dtype={"stop_id": str})

    def __preformat(self):
        """
        Prétraite les données CAP en sélectionnant et formatant les colonnes nécessaires.
        
        Returns:
            DataFrame prétraité
        """
        # Sélection des colonnes à conserver
        cap_columns = [self.__origin_stop_id_col,
                     self.__destination_stop_id_col,
                     self.__boarding_time_col, self.__arrival_time_col,
                     self.__boarding_type_col, self.__id_col,
                     self.__origin_stop_lat_col, self.__origin_stop_lon_col,
                     self.__destination_stop_lat_col,
                     self.__destination_stop_lon_col,
                     "S_VEHJOBID_IDJOURNALIER"]
        
        # Tri et nettoyage des données
        self.__cap_df = self.__cap_df.sort_values(
            [self.__id_col, self.__boarding_time_col])[cap_columns].dropna()
        
        # Conversion des types de données
        self.__cap_df = self.__cap_df.astype(
            {self.__origin_stop_id_col: int,
             self.__destination_stop_id_col: int,
             "S_VEHJOBID_IDJOURNALIER": int})
        self.__cap_df = self.__cap_df.astype(
            {self.__origin_stop_id_col: str,
             self.__destination_stop_id_col: str})

        return self.__cap_df

    def __filter(self):
        """
        Filtre les données CAP pour ne conserver que les trajets valides.
        
        Returns:
            DataFrame filtré
        """
        # Regroupement des arrêts par trajet
        stop_times_grouped_by_id = self.__stop_times_df.groupby("trip_id")
        stops_by_trip_series = stop_times_grouped_by_id["stop_id"].apply(list)

        # Vérification de l'existence des arrêts dans les trajets
        cap_with_stops_list_df = self.__cap_df.merge(
            stops_by_trip_series, left_on="S_VEHJOBID_IDJOURNALIER",
            right_index=True)

        cap_with_stops_list_df["trip_exists"] = cap_with_stops_list_df.apply(
            lambda x: x[self.__origin_stop_id_col] in x["stop_id"] and x[
                self.__destination_stop_id_col] in x["stop_id"], axis=1)

        # Filtrage des trajets valides
        self.__cap_df = cap_with_stops_list_df[
            cap_with_stops_list_df["trip_exists"]]

        return self.__cap_df

    def __add_boarding_type(self, max_connection_time):
        """
        Ajoute le type de montée (première montée ou correspondance) aux données CAP.
        
        Args:
            max_connection_time: Temps maximum pour une correspondance
            
        Returns:
            DataFrame avec les types de montée ajoutés
        """
        # Tri des données par identifiant client et temps de montée
        self.__cap_df.sort_values([self.__id_col, self.__boarding_time_col],
                                inplace=True)
        cap_grouped_by_id_client = self.__cap_df.groupby(self.__id_col)

        # Calcul des différences de temps entre les montées
        self.__cap_df["arrival_time_lag_lag"] = cap_grouped_by_id_client[
            self.__arrival_time_col].shift(1)
        self.__cap_df["arr_dep_diff"] = \
            self.__cap_df[self.__boarding_time_col] \
            - self.__cap_df["arrival_time_lag_lag"]
        
        # Détermination du type de montée
        self.__cap_df["boarding_type"] = self.__cap_df.apply(
            lambda x: x[self.__boarding_type_col]
            if x["arr_dep_diff"] < max_connection_time
            else "1ère montée", axis=1)
        self.__cap_df["boarding_type_lead"] = cap_grouped_by_id_client[
            "boarding_type"].shift(-1)

        # Conversion des identifiants d'arrêt en entiers
        self.__cap_df[self.__origin_stop_id_col] = self.__cap_df[self.__origin_stop_id_col].apply(
            int)
        self.__cap_df[self.__destination_stop_id_col] = self.__cap_df[
            self.__destination_stop_id_col].apply(int)

        return self.__cap_df
