import pandas as pd
import os
import logging
import numpy as np
from operator import itemgetter
import re
import csv
from ast import literal_eval
from collections import Counter

from multimodalsim.config.gtfs_generator_config import GTFSGeneratorConfig

logger = logging.getLogger(__name__)

class GTFSGenerator:
    """
    Classe principale pour la génération des fichiers GTFS à partir des données de la STL.
    
    Cette classe lit les fichiers contenant les données de passage aux arrêts de la STL
    et génère les fichiers GTFS correspondants. Les fichiers d'entrée sont nommés
    Donnees_PASSAGE_ARRET_VLV_2019-11-01_2019-11-30.csv.
    Les fichiers de sortie pour chaque jour sont sauvegardés dans un dossier nommé
    d'après la date, dans le dossier gtfs_folder.
    """

    def __init__(self, config=None):
        """
        Initialise le générateur GTFS avec une configuration optionnelle.
        
        Args:
            config: Configuration personnalisée pour le générateur GTFS.
                   Si None, utilise la configuration par défaut.
        """
        config = GTFSGeneratorConfig() if config is None else config
        self.__load_config(config)

        self.__passage_arret_file_path_list = None
        self.__stop_times_df = None
        self.__stops_df = None

    def build_calendar_dates(self, passage_arret_file_path_list,
                             gtfs_folder=None):
        """
        Construit le fichier calendar_dates.txt qui définit les jours de service.
        
        Args:
            passage_arret_file_path_list: Liste des chemins vers les fichiers de passage aux arrêts
            gtfs_folder: Dossier de destination pour les fichiers GTFS
        """
        self.__passage_arret_file_path_list = passage_arret_file_path_list

        passage_arret_df = self.__get_passage_arret_df()

        # Sélection des colonnes nécessaires pour le calendrier
        calendar_dates_columns = [self.__service_id_col, self.__date_col]
        calendar_dates_df = passage_arret_df.loc[:, calendar_dates_columns] \
            .dropna()

        # Formatage des données pour le format GTFS
        calendar_dates_df.loc[:, "service_id"] = \
            calendar_dates_df[self.__service_id_col]
        calendar_dates_df.loc[:, "date"] = \
            calendar_dates_df[self.__date_col].apply(
                lambda x: "".join(x.split(" ")[0].split("-")))
        calendar_dates_df["exception_type"] = 1
        calendar_dates_df.drop_duplicates(inplace=True)
        calendar_dates_df = calendar_dates_df[["service_id", "date",
                                               "exception_type",
                                               self.__date_col]]

        # Sauvegarde du fichier si un dossier de destination est spécifié
        if gtfs_folder is not None:
            self.__save_to_file(calendar_dates_df, "calendar_dates.txt",
                                gtfs_folder)

    def build_trips(self, passage_arret_file_path_list, gtfs_folder=None):
        """
        Construit le fichier trips.txt qui définit les trajets des véhicules.
        
        Args:
            passage_arret_file_path_list: Liste des chemins vers les fichiers de passage aux arrêts
            gtfs_folder: Dossier de destination pour les fichiers GTFS
            
        Returns:
            DataFrame contenant les informations des trajets
        """
        self.__passage_arret_file_path_list = passage_arret_file_path_list

        passage_arret_df = self.__get_passage_arret_df()

        # Sélection des colonnes nécessaires pour les trajets
        trips_columns = [self.__line_col, self.__direction_col,
                         self.__service_id_col,
                         self.__trip_id_col, self.__date_col]

        trips_df = passage_arret_df.loc[:, trips_columns].dropna()
        trips_df.drop_duplicates(inplace=True)

        # Formatage des données pour le format GTFS
        trips_df.loc[:, "route_id"] = trips_df.loc[:, self.__line_col] \
                                      + trips_df.loc[:, self.__direction_col]
        trips_df.loc[:, "service_id"] = trips_df.loc[:, self.__service_id_col]
        trips_df.loc[:, "trip_id"] = trips_df.loc[:, self.__trip_id_col]
        trips_df.loc[:, "shape_id"] = trips_df.loc[:, self.__line_col] \
                                      + trips_df.loc[:, self.__direction_col]
        trips_df.loc[:, "trip_short_name"] = trips_df.loc[:, self.__line_col]

        # Sélection des colonnes à conserver
        columns_to_keep = ["route_id", "service_id", "trip_id", "shape_id",
                           "trip_short_name", self.__date_col]
        trips_df = trips_df[columns_to_keep]
        trips_df.sort_values(columns_to_keep, inplace=True)

        # Sauvegarde du fichier si un dossier de destination est spécifié
        if gtfs_folder is not None:
            self.__save_to_file(trips_df, "trips.txt", gtfs_folder)

        return trips_df

    def build_stops(self, passage_arret_file_path_list, gtfs_folder=None):
        """
        Construit le fichier stops.txt qui liste tous les arrêts.
        
        Args:
            passage_arret_file_path_list: Liste des chemins vers les fichiers de passage aux arrêts
            gtfs_folder: Dossier de destination pour les fichiers GTFS
            
        Returns:
            DataFrame contenant les informations des arrêts
        """
        self.__passage_arret_file_path_list = passage_arret_file_path_list

        passage_arret_df = self.__get_passage_arret_df()

        # Sélection des colonnes nécessaires pour les arrêts
        stops_columns = [self.__date_col, self.__stop_id_col,
                         self.__stop_name_col, self.__stop_lon_col,
                         self.__stop_lat_col]

        # Regroupement des arrêts par date et ID
        stops_df = passage_arret_df[stops_columns].groupby(
            [self.__date_col, self.__stop_id_col]).first().reset_index()
        
        # Renommage des colonnes pour le format GTFS
        stops_df.rename({self.__stop_id_col: "stop_id",
                         self.__stop_name_col: "stop_name",
                         self.__stop_lon_col: "stop_lon",
                         self.__stop_lat_col: "stop_lat"}, axis=1,
                        inplace=True)

        # Sauvegarde du fichier si un dossier de destination est spécifié
        if gtfs_folder is not None:
            self.__save_to_file(stops_df, "stops.txt",
                                gtfs_folder)

        return stops_df
 
    def build_stop_times(self, passage_arret_file_path_list, gtfs_folder=None,
                         shape_dist_traveled=False):
        """
        Construit le fichier stop_times.txt qui définit les horaires aux arrêts.
        
        Args:
            passage_arret_file_path_list: Liste des chemins vers les fichiers de passage aux arrêts
            gtfs_folder: Dossier de destination pour les fichiers GTFS
            shape_dist_traveled: Booléen indiquant si la distance parcourue doit être incluse
            
        Returns:
            DataFrame contenant les horaires aux arrêts
        """
        self.__passage_arret_file_path_list = passage_arret_file_path_list

        passage_arret_df = self.__get_passage_arret_df()

        # Sélection des colonnes nécessaires pour les horaires
        stop_times_columns = [self.__date_col, self.__line_col,
                              self.__direction_col, self.__trip_id_col,
                              self.__arrival_time_col,
                              self.__departure_time_col, self.__stop_id_col,
                              self.__stop_sequence_col,
                              self.__shape_dist_traveled_col]

        # Tri et nettoyage des données
        self.__stop_times_df = passage_arret_df[
            stop_times_columns].sort_values(
            [self.__date_col, self.__trip_id_col,
             self.__stop_sequence_col]).dropna()
        
        # Calcul des temps relatifs à l'origine
        stop_times_with_orig_time_df = \
            self.__get_stop_times_with_orig_time_df()

        # Filtrage des trajets valides
        trip_id_set = self.__get_trip_id_set()
        stop_times_with_orig_time_filtered_df = stop_times_with_orig_time_df[
            stop_times_with_orig_time_df[self.__trip_id_col].isin(trip_id_set)]

        # Construction du DataFrame complet des horaires
        full_stop_times_df = self.__get_full_stop_times_df(
            stop_times_with_orig_time_filtered_df)
        gtfs_stop_times_df = self.__get_stop_times_df(full_stop_times_df,
                                                      shape_dist_traveled)

        # Association des dates avec les trajets
        date_by_trip_id_series = \
            self.__stop_times_df.groupby(self.__trip_id_col)[
                self.__date_col].apply(
                lambda x: list(set(x))[0])
        stop_times_with_date_df = gtfs_stop_times_df.merge(
            date_by_trip_id_series, left_on="trip_id", right_index=True)

        # Nettoyage et formatage des temps
        stop_times_with_date_df["arrival_time"] = stop_times_with_date_df[
            "arrival_time"].dropna()
        stop_times_with_date_df["departure_time"] = stop_times_with_date_df[
            "departure_time"].dropna()

        stop_times_with_date_df["arrival_time"] = \
            stop_times_with_date_df["arrival_time"].astype(int)
        stop_times_with_date_df["departure_time"] = \
            stop_times_with_date_df["departure_time"].astype(int)

        # Correction des horaires pour assurer la cohérence
        stop_times_with_date_df = \
            self.__correct_stop_times_df(stop_times_with_date_df)

        # Sauvegarde du fichier si un dossier de destination est spécifié
        if gtfs_folder is not None:
            self.__save_to_file(stop_times_with_date_df, "stop_times.txt",
                                gtfs_folder)

        return stop_times_with_date_df
    
    def build_stop_times_upgrade(self, passage_arret_file_path_list, gtfs_folder=None,
                         shape_dist_traveled=True):
        """
        Construit une version améliorée du fichier stop_times.txt avec des informations supplémentaires.
        
        Args:
            passage_arret_file_path_list: Liste des chemins vers les fichiers de passage aux arrêts
            gtfs_folder: Dossier de destination pour les fichiers GTFS
            shape_dist_traveled: Booléen indiquant si la distance parcourue doit être incluse
            
        Returns:
            DataFrame contenant les horaires améliorés aux arrêts
        """
        self.__passage_arret_file_path_list = passage_arret_file_path_list

        passage_arret_df = self.__get_passage_arret_upgrade_df()

        # Sélection des colonnes nécessaires pour les horaires améliorés
        stop_times_columns = [self.__date_col, self.__line_col,
                              self.__direction_col, self.__trip_id_col,
                              self.__arrival_time_col,
                              self.__departure_time_col, self.__stop_id_col,
                              self.__stop_sequence_col,
                              self.__shape_dist_traveled_col,
                              self.__planned_arrival_time_col,
                              self.__planned_departure_time_from_origin_col]

        # Tri et nettoyage des données
        self.__stop_times_df = passage_arret_df[
            stop_times_columns].sort_values(
            [self.__date_col, self.__planned_departure_time_from_origin_col,
             self.__stop_sequence_col]).dropna()
        
        # Calcul des temps relatifs à l'origine
        stop_times_with_orig_time_df = \
            self.__get_stop_times_with_orig_time_df()

        # Filtrage des trajets valides
        trip_id_set = self.__get_trip_id_set()
        stop_times_with_orig_time_filtered_df = stop_times_with_orig_time_df[
            stop_times_with_orig_time_df[self.__trip_id_col].isin(trip_id_set)]

        # Construction du DataFrame complet des horaires
        full_stop_times_df = self.__get_full_stop_times_df(
            stop_times_with_orig_time_filtered_df)
        gtfs_stop_times_df = self.__get_stop_times_df(full_stop_times_df,
                                                      shape_dist_traveled=True)

        # Association des dates avec les trajets
        date_by_trip_id_series = \
            self.__stop_times_df.groupby(self.__trip_id_col)[
                self.__date_col].apply(
                lambda x: list(set(x))[0])
        stop_times_with_date_df = gtfs_stop_times_df.merge(
            date_by_trip_id_series, left_on="trip_id", right_index=True)

        # Nettoyage et formatage des temps
        stop_times_with_date_df["arrival_time"] = stop_times_with_date_df[
            "arrival_time"].dropna()
        stop_times_with_date_df["departure_time"] = stop_times_with_date_df[
            "departure_time"].dropna()

        # Conversion des temps en entiers
        stop_times_with_date_df["arrival_time"] = \
            stop_times_with_date_df["arrival_time"].astype(int)
        stop_times_with_date_df["departure_time"] = \
            stop_times_with_date_df["departure_time"].astype(int)
        stop_times_with_date_df["planned_arrival_time"] = \
            stop_times_with_date_df["planned_arrival_time"].astype(int)
        stop_times_with_date_df["planned_departure_time_from_origin"] = \
            stop_times_with_date_df["planned_departure_time_from_origin"].astype(int)
        stop_times_with_date_df["shape_dist_traveled"] = \
            stop_times_with_date_df["shape_dist_traveled"].astype(float)
        
        # Correction et tri des horaires
        stop_times_with_date_df = \
            self.__correct_stop_times_df(stop_times_with_date_df)
        stop_times_with_date_df = self.__sort_stop_times(stop_times_with_date_df)

        # Sauvegarde du fichier si un dossier de destination est spécifié
        if gtfs_folder is not None:
            self.__save_to_file(stop_times_with_date_df, "stop_times_upgrade.txt",
                                gtfs_folder, upgrade=True)

        return stop_times_with_date_df
        
    def fill_missing_stop_times(self, date_folder):
        """
        Remplit les temps d'arrêt manquants pour chaque trajet de la journée.
        
        Args:
            date_folder: Chemin vers le dossier contenant les données du jour
            
        Returns:
            Chemin vers le fichier contenant les arrêts par ligne
        """
        # Création des dictionnaires contenant les arrêts pour chaque ligne
        # et les identifiants de trajet pour chaque ligne
        stops_per_line_dict, trips_per_line_dict = self.create_stops_per_line(date_folder)

        # Lecture du fichier des temps d'arrêt
        stop_times_file_path = os.path.join(date_folder, "stop_times_upgrade.txt")
        new_lines = []
        with open(stop_times_file_path, 'r') as file:
            # Lecture de l'en-tête
            header = file.readline()
            # Identification des positions des colonnes
            header_split = header.strip().split(",")
            trip_id_index = header_split.index("trip_id")
            stop_id_index = header_split.index("stop_id")
            arrival_time_index = header_split.index("arrival_time")
            departure_time_index = header_split.index("departure_time")
            sequence_index = header_split.index("stop_sequence")
            shape_dist_traveled_index = header_split.index("shape_dist_traveled")
            planned_arrival_time_index = header_split.index("planned_arrival_time")
            planned_departure_time_from_origin_index = header_split.index("planned_departure_time_from_origin")
            
            # Lecture des lignes restantes
            lines = file.readlines()
            prev_trip_id = -1
            all_stops = []
            i=0
            for line in lines:
                line_split = line.strip().split(",")
                trip_id = line_split[trip_id_index]
                stop_id = int(str(line_split[stop_id_index]))
                
                # Gestion du changement de trajet
                if trip_id != prev_trip_id:
                    if i < len(all_stops)-1:
                        number_of_missing_stops = len(all_stops) - (i+1)
                        logger.warning("Trip "+trip_id+" did not stop at all stops in the line. "+str(number_of_missing_stops)+" stops are missing.")
                    prev_trip_id = trip_id
                    ligne_direction = trips_per_line_dict[trip_id]
                    all_stops = stops_per_line_dict[ligne_direction]
                    i = 0
                    stop = all_stops[i]
                    dist_prev = 0
                    time_prev = int(line_split[arrival_time_index])
                    time_plan_prev = int(float(line_split[planned_departure_time_from_origin_index]))
                    stop_sequence = 1
                    depart_plan_from_origin = int(line_split[planned_departure_time_from_origin_index])
                
                # Calcul des temps de trajet
                travel_distance = float(line_split[shape_dist_traveled_index]) - dist_prev
                travel_time = int(line_split[arrival_time_index]) - time_prev
                planned_travel_time = int(line_split[planned_arrival_time_index]) - time_plan_prev

                # Ajout des arrêts manquants
                while stop_id != int(str(stop[0])):
                    add_stop_dist = stop[2]
                    add_stop_travel_time = int(travel_time * (add_stop_dist - dist_prev) / travel_distance)
                    add_stop_arrival_time = time_prev + add_stop_travel_time
                    add_stop_departure_time = add_stop_arrival_time
                    add_stop_planned_travel_time = int(planned_travel_time * (add_stop_dist - dist_prev) / travel_distance)
                    add_stop_planned_arrival_time = time_plan_prev + add_stop_planned_travel_time
                    
                    # Ajout de la nouvelle ligne
                    new_line =[str(trip_id), str(add_stop_arrival_time), str(add_stop_departure_time), str(stop[0]), str(stop_sequence), str(0), str(0), str(add_stop_dist), str(add_stop_planned_arrival_time), str(depart_plan_from_origin)] 
                    new_lines.append(new_line)

                    # Mise à jour des variables
                    dist_prev = add_stop_dist
                    time_prev = add_stop_arrival_time
                    time_plan_prev = add_stop_planned_arrival_time
                    stop_sequence += 1
                    if i<len(all_stops) - 1:
                        i += 1
                        stop = all_stops[i]
                    else:
                        print('On ne devrait jamais etre la...')
                        break

                # Ajout de la ligne actuelle
                new_line = [trip_id, line_split[arrival_time_index], int(line_split[departure_time_index]), stop_id, stop_sequence, 0, 0, line_split[shape_dist_traveled_index], line_split[planned_arrival_time_index], line_split[planned_departure_time_from_origin_index]]
                new_lines.append(line_split)

                # Mise à jour des variables
                dist_prev = float(line_split[shape_dist_traveled_index])
                time_prev = int(line_split[arrival_time_index])
                time_plan_prev = int(line_split[planned_arrival_time_index])
                stop_sequence += 1
                if i<len(all_stops) - 1:
                    i += 1
                    stop = all_stops[i]

        # Sauvegarde du nouveau fichier des temps d'arrêt
        with open(stop_times_file_path, 'w') as file:
            file.write(header)
            for new_line in new_lines:
                file.write(",".join(new_line)+"\n")
        return stop_times_file_path
    
    def get_all_lines(self):
        """
        Extrait toutes les lignes de bus des fichiers GTFS.
        
        Returns:
            Tuple contenant deux listes :
            - Liste des lignes Nord-Sud
            - Liste des lignes Est-Ouest
        """
        # Liste des dates à analyser
        dates=['2019-11-01', '2019-11-04', '2019-11-05', '2019-11-06', '2019-11-07', 
               '2019-11-08', '2019-11-12', '2019-11-13', '2019-11-14', '2019-11-15', 
               '2019-11-18', '2019-11-19', '2019-11-20', '2019-11-21', '2019-11-22', 
               '2019-11-25']
        
        all_ligns_SN = []
        all_ligns_EO = []
        
        # Analyse de chaque date
        for date in dates:
            date_folder = os.path.join("data", "fixed_line", "gtfs", "gtfs" + date)
            filename = os.path.join(date_folder, "stops_per_line.txt")
            
            # Lecture des noms de ligne
            line_names=np.genfromtxt(filename, delimiter = ",", usecols=[0], 
                                    dtype = [('f0','U12')], names = True)
            
            # Classification des lignes selon leur direction
            for ligndir in line_names:
                ligndir=str(ligndir[0])
                poubelle, lign, dir = re.split(r'(\d+)', ligndir)
                if dir == 'S' or dir == 'N': 
                    all_ligns_SN.append(lign)
                elif dir == 'E' or dir == 'O':
                    all_ligns_EO.append(lign)
        
        # Suppression des doublons
        all_ligns_SN = list(dict.fromkeys(all_ligns_SN))
        all_ligns_EO = list(dict.fromkeys(all_ligns_EO))

        # Suppression des lignes spécifiques
        to_delete = [('31','S'),('39','S'),('40','O'), ('313','S'), ('360','O'),
                    ('345','S'),('402','O'),('404','O'), ('12','E'), ('48','O'), 
                    ('50','O'),('58','O')]
        for lign, dir in to_delete: 
            if lign in all_ligns_EO: 
                all_ligns_EO.remove(lign)
            if lign in all_ligns_SN: 
                all_ligns_SN.remove(lign)
                
        return all_ligns_SN, all_ligns_EO

    def create_stops_per_line(self, date_folder):
        """
        Crée un fichier contenant les arrêts par ligne.
        
        Args:
            date_folder: Chemin vers le dossier contenant les données du jour
            
        Returns:
            Tuple contenant :
            - Dictionnaire des arrêts par ligne
            - Dictionnaire des lignes par trajet
        """
        # Chemins des fichiers nécessaires
        stop_times_file_path = os.path.join(date_folder, "stop_times_upgrade.txt")
        trips_file_path = os.path.join(date_folder, "trips.txt")
        
        stops_per_line_dict = {}
        trips_per_line_dict = {}
        
        # Lecture du fichier des trajets
        with open(trips_file_path, 'r') as file:
            # Lecture de l'en-tête
            header=file.readline()
            # Identification des positions des colonnes
            header_split=header.strip().split(",")
            trip_id_index=header_split.index("trip_id")
            ligne_direction_index=header_split.index("route_id")
            
            # Lecture des lignes restantes
            lines=file.readlines()
            for line in lines:
                line_split = line.strip().split(",")
                trip_id = line_split[trip_id_index]
                ligne_direction = line_split[ligne_direction_index]
                trips_per_line_dict[trip_id] = ligne_direction
                
        # Lecture du fichier des temps d'arrêt
        with open(stop_times_file_path, 'r') as file:
            # Lecture de l'en-tête
            header = file.readline()
            # Identification des positions des colonnes
            header_split = header.strip().split(",")
            trip_id_index = header_split.index("trip_id")
            sequence_index = header_split.index("stop_sequence")
            stop_shape_dist_traveled_index = header_split.index("shape_dist_traveled")
            stop_id_index = header_split.index("stop_id")
            
            # Lecture des lignes restantes
            lines=file.readlines()
            for line in lines:
                line_split = line.strip().split(",")
                trip_id = line_split[trip_id_index]
                sequence = int(line_split[sequence_index])
                stop_shape_dist_traveled = float(line_split[stop_shape_dist_traveled_index])
                stop_id = int(line_split[stop_id_index])
                ligne_direction = trips_per_line_dict[trip_id]
                
                # Ajout de l'arrêt au dictionnaire de la ligne
                if ligne_direction not in stops_per_line_dict:
                    stops_per_line_dict[ligne_direction]=[]
                stops_per_line_dict[ligne_direction].append((stop_id, sequence, stop_shape_dist_traveled))
                
        # Tri et nettoyage des données
        for ligne_direction in stops_per_line_dict:
            # Tri par séquence et distance parcourue
            stops_per_line_dict[ligne_direction] = sorted(stops_per_line_dict[ligne_direction], 
                                                        key=itemgetter(1, 2))
            
            # Conservation d'une seule ligne par arrêt (celle avec la plus petite distance)
            stop_dict = {}
            for stop_id, stop_sequence, distance in stops_per_line_dict[ligne_direction]:
                if stop_id not in stop_dict: # déjà trié donc pas besoin de vérifier la séquence et la distance
                    stop_dict[stop_id] = [stop_sequence, distance, 0]
                stop_dict[stop_id][2] += 1
            stops_per_line_dict[ligne_direction] = sorted([(stop_id, seq, dist, count) 
                                                         for stop_id, [seq, dist, count] in stop_dict.items()], 
                                                        key = itemgetter(1,2))

        # Sauvegarde des données dans un fichier
        stops_per_line_filepath = os.path.join(date_folder, "stops_per_line.txt")
        with open(stops_per_line_filepath, 'w') as file:
            file.write("route_id,stop_id,sequence,distance,count\n")
            for ligne_direction in stops_per_line_dict:
                for stop in stops_per_line_dict[ligne_direction]:
                    file.write(ligne_direction+","+str(stop[0])+","+str(stop[1])+","+str(stop[2])+","+str(stop[3])+"\n")
                    
        return stops_per_line_dict, trips_per_line_dict

    def create_stops_per_line_month_files(self):
        """
        Collecte les données sur les arrêts et les lignes pour tout le mois.
        
        Returns:
            Chemin vers le fichier contenant les arrêts par ligne pour le mois
        """
        # Liste des dates à analyser
        dates = ['2019-11-01', '2019-11-04', '2019-11-05', '2019-11-06', '2019-11-07', 
                '2019-11-08', '2019-11-12', '2019-11-13', '2019-11-14', '2019-11-15', 
                '2019-11-18', '2019-11-19', '2019-11-20', '2019-11-21', '2019-11-22', 
                '2019-11-25']
        
        stops ={}
        
        # Analyse de chaque date
        for date in dates:
            date_folder=os.path.join("data", "fixed_line", "gtfs", "gtfs" + date)
            filename = os.path.join(date_folder, "stops_per_line.txt")
            
            # Lecture des arrêts
            all_stops = np.genfromtxt(filename, delimiter=",", usecols=[0,1,2,3,4], 
                                     dtype=[('f0','U12'),('f1','i4'),('f2','i4'),('f3','f4'),('f4','i4')], 
                                     names=True)
            
            # Organisation des arrêts par ligne
            route_names = np.unique([stop[0] for stop in all_stops])
            for route_name in route_names:
                stops[route_name] = []
            for stop in all_stops:
                stops[stop[0]].append((stop[1], stop[2], stop[3], stop[4]))
                
        new_stops = {}
        
        # Traitement des données pour chaque ligne
        for route_name in stops:
            route_stops = sorted(stops[route_name], key=itemgetter(1))
            
            # Ajout du nombre d'arrêts
            stop_dict = {}
            for stop_id, stop_sequence, distance, count in route_stops:
                if stop_id not in stop_dict:
                    stop_dict[stop_id] = [stop_sequence, distance, 0]
                stop_dict[stop_id][2] += count
                
            stops_to_write = sorted([(stop_id, seq, dist, count) 
                                   for stop_id, [seq, dist, count] in stop_dict.items()], 
                                  key = itemgetter(1))
            
            # Sauvegarde des données par ligne
            stops_per_line_month_filepath = os.path.join("data", "fixed_line", "gtfs", 
                                                        "route_data", 
                                                        'route_stops_' + route_name + '_month.txt')
            with open(stops_per_line_month_filepath, 'w') as file:
                file.write("stop_id,sequence,distance,count\n")
                for stop in stops_to_write:
                    file.write(str(stop[0])+","+str(stop[1])+","+str(stop[2])+","+str(stop[3])+"\n")
            file.close()
            new_stops[route_name] = stops_to_write
            
        # Création d'un fichier global contenant tous les arrêts pour toutes les lignes
        stops_per_line_month_filepath = os.path.join("data", "fixed_line", "gtfs", 
                                                    "route_data", "stops_per_line_month.txt")
        with open(stops_per_line_month_filepath, 'w') as file:
            file.write("route_id,stop_id,sequence,distance,count\n")
            for route_name in new_stops:
                for stop in new_stops[route_name]:
                    file.write(route_name+","+str(stop[0])+","+str(stop[1])+","+str(stop[2])+","+str(stop[3])+"\n")
        file.close()
        
        return stops_per_line_month_filepath

    def create_travel_times_month_files(self):
        """
        Collecte les données sur les temps de trajet et les temps d'arrêt pour tout le mois.
        
        Returns:
            Tuple contenant :
            - Dictionnaire des temps de trajet
            - Dictionnaire des temps d'arrêt
            - Dictionnaire des arrêts
        """
        # Liste des dates à analyser
        dates = ['2019-11-01', '2019-11-04', '2019-11-05', '2019-11-06', '2019-11-07', 
                '2019-11-08', '2019-11-12', '2019-11-13', '2019-11-14', '2019-11-15', 
                '2019-11-18', '2019-11-19', '2019-11-20', '2019-11-21', '2019-11-22', 
                '2019-11-25']
        
        # Lecture des arrêts par ligne pour le mois
        stops_per_line_month_filename = os.path.join("data", "fixed_line", "gtfs", 
                                                    "route_data","stops_per_line_month.txt")
        all_stops=np.genfromtxt(stops_per_line_month_filename, 
                                delimiter=",", 
                                usecols=[0,1,2,3,4], 
                                dtype=[('f0','U12'),('f1','i4'),('f2','i4'),('f3','f4'),('f4','i4')],
                                names=True)
        
        # Initialisation des dictionnaires
        all_routes = np.unique([stop[0] for stop in all_stops])
        travel_times_dict = {} # temps de trajet entre paires d'arrêts consécutifs
        dwells_dict = {} # temps d'arrêt aux arrêts
        stops_dict = {}
        
        for route in all_routes:
            travel_times_dict[route] = {}
            dwells_dict[route] = {}
            stops_dict[route] = {}
            
        # Organisation des arrêts par ligne
        for stop in all_stops: 
            route_name = stop[0]
            stop_id = stop[1]
            stop_sequence = stop[2]
            distance = stop[3]
            count = stop[4]
            if stop_id not in stops_dict[route_name]:
                stops_dict[route_name][stop_id] = {}
                stops_dict[route_name][stop_id]['order'] = stop_sequence
                stops_dict[route_name][stop_id]['dist'] = distance
                
        # Analyse de chaque date
        for date in dates:
            logger.info("Processing travel times for date "+date)
            
            # Lecture des trajets
            trips_filename = os.path.join("data", "fixed_line", "gtfs", "gtfs" + date, "trips.txt")
            trips = np.genfromtxt(trips_filename, delimiter=",", usecols=[0,1,2,3,4], 
                                 dtype=[('f0','U12'),('f1','U12'),('f2','U12'),('f3','U12'),('f4','U12')], 
                                 names=True)
            
            # Création d'un dictionnaire trajet -> nom de ligne
            trips_to_routename_dict = {}
            for trip in trips:
                trips_to_routename_dict[trip[2]] = trip[0]
                
            # Lecture des temps d'arrêt
            stop_times_filename = os.path.join("data", "fixed_line", "gtfs", "gtfs" + date, 
                                              "stop_times_upgrade.txt")
            with open(stop_times_filename, 'r') as file:
                # Lecture de l'en-tête
                header = file.readline()
                # Identification des positions des colonnes
                header_split = header.strip().split(",")
                trip_id_index = header_split.index("trip_id")
                stop_id_index = header_split.index("stop_id")
                arrival_time_index = header_split.index("arrival_time")
                for line in file.readlines():
                    line_split = line.strip().split(",")
                    trip_id = line_split[trip_id_index]
                    stop_id = int(line_split[stop_id_index])
                    arrival_time = int(line_split[arrival_time_index])
                    if trip_id in all_trip_ids and stop_id in all_trip_ids[trip_id]:
                        if stop_id not in times[trip_id]:
                            times[trip_id][stop_id] = arrival_time
            file.close()

            # Analyse des montées et descentes pour chaque trajet
            for trip in all_trips:
                range_legs = len(trip)
                i = 0
                for (origin, destination, trip_id) in trip:
                    # Détermination si c'est une montée ou descente en transfert
                    transfer_boarding = False
                    transfer_alighting = False
                    if i > 0:
                        transfer_boarding = True
                    if i < range_legs-1:
                        transfer_alighting = True
                    i += 1
                    
                    # Conversion des identifiants en entiers
                    origin = int(origin)
                    destination = int(destination)
                    route_name = trips_to_routename_dict[trip_id]
                    
                    # Initialisation des dictionnaires si nécessaire
                    if route_name not in boarding_passengers:
                        boarding_passengers[route_name] = {}
                        alighting_passengers[route_name] = {}
                        transfer_boarding_passengers[route_name] = {}
                        transfer_alighting_passengers[route_name] = {}
                    if trip_id not in boarding_passengers[route_name]:
                        boarding_passengers[route_name][trip_id] = {}
                        alighting_passengers[route_name][trip_id] = {}
                        transfer_boarding_passengers[route_name][trip_id] = {}
                        transfer_alighting_passengers[route_name][trip_id] = {}
                    
                    # Ajout des passagers dans les dictionnaires appropriés
                    if transfer_boarding:
                        transfer_boarding_passengers[route_name][trip_id] = self.add_passenger(
                            origin, times[trip_id][origin], 
                            transfer_boarding_passengers[route_name][trip_id])
                    else:
                        boarding_passengers[route_name][trip_id] = self.add_passenger(
                            origin, times[trip_id][origin], 
                            boarding_passengers[route_name][trip_id])
                    
                    if transfer_alighting:
                        transfer_alighting_passengers[route_name][trip_id] = self.add_passenger(
                            destination, times[trip_id][destination], 
                            transfer_alighting_passengers[route_name][trip_id])
                    else:
                        alighting_passengers[route_name][trip_id] = self.add_passenger(
                            destination, times[trip_id][destination], 
                            alighting_passengers[route_name][trip_id])
        
        # Comptage du nombre de passagers par arrêt et trajet
        for route_name in boarding_passengers:
            boarding_passengers[route_name] = self.count_passengers(boarding_passengers[route_name])
            alighting_passengers[route_name] = self.count_passengers(alighting_passengers[route_name])
            transfer_boarding_passengers[route_name] = self.count_passengers(transfer_boarding_passengers[route_name])
            transfer_alighting_passengers[route_name] = self.count_passengers(transfer_alighting_passengers[route_name])

        # Sauvegarde des données dans des fichiers CSV pour chaque ligne
        for route_name in boarding_passengers:
            # Fichier des passagers montant
            boarding_passengers_filename = os.path.join(gtfs_folder, "route_data", 
                                                      route_name+"_boarding_passengers_month.csv")
            self.write_passenger_flow_month_file(boarding_passengers_filename, 
                                               boarding_passengers[route_name])
            
            # Fichier des passagers descendant
            alighting_passengers_filename = os.path.join(gtfs_folder, "route_data", 
                                                       route_name+"_alighting_passengers_month.csv")
            self.write_passenger_flow_month_file(alighting_passengers_filename, 
                                               alighting_passengers[route_name])
            
            # Fichier des passagers en transfert montant
            transfer_boarding_passengers_filename = os.path.join(gtfs_folder, "route_data", 
                                                               route_name+"_transfer_boarding_passengers_month.csv")
            self.write_passenger_flow_month_file(transfer_boarding_passengers_filename, 
                                               transfer_boarding_passengers[route_name])
            
            # Fichier des passagers en transfert descendant
            transfer_alighting_passengers_filename = os.path.join(gtfs_folder, "route_data", 
                                                                route_name+"_transfer_alighting_passengers_month.csv")
            self.write_passenger_flow_month_file(transfer_alighting_passengers_filename, 
                                               transfer_alighting_passengers[route_name])
    
    def count_passengers(self, dict):
        """
        Compte le nombre de passagers montant/descendant au même arrêt pour le même trajet.
        
        Args:
            dict: Dictionnaire contenant les données de passagers par trajet et arrêt
            
        Returns:
            Liste triée des données de passagers avec le format [stop_id, count, time]
        """
        new_list = []
        for trip_id in dict:
            for stop_id in dict[trip_id]:
                new_list.append([stop_id, dict[trip_id][stop_id][1], 
                               dict[trip_id][stop_id][0]],)
        new_list = sorted(new_list, key=itemgetter(0))
        return new_list
    
    def add_passenger(self, stop_id, time, dict):
        """
        Ajoute un passager au dictionnaire des passagers.
        
        Args:
            stop_id: Identifiant de l'arrêt
            time: Temps de l'événement
            dict: Dictionnaire des passagers
            
        Returns:
            Dictionnaire mis à jour avec le nouveau passager
        """
        if stop_id not in dict:
            dict[stop_id] = [time, 0]
        dict[stop_id][1] += 1
        return dict
    
    def write_passenger_flow_month_file(self, filename, flows_list):
        """
        Écrit les données de flux de passagers dans un fichier CSV.
        
        Args:
            filename: Chemin du fichier de sortie
            flows_list: Liste des données de flux à écrire
        """
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["stop_id", "passenger_count", "time"])
            writer.writerows(flows_list)
        file.close()

    def __load_config(self, config):
        """
        Charge la configuration du générateur GTFS.
        
        Args:
            config: Objet de configuration contenant les noms des colonnes
                   et autres paramètres nécessaires
        """
        # Stockage des noms des colonnes de la configuration
        self.__trip_id_col = config.trip_id_col
        self.__arrival_time_col = config.arrival_time_col
        self.__departure_time_col = config.departure_time_col
        self.__stop_id_col = config.stop_id_col
        self.__stop_sequence_col = config.stop_sequence_col
        self.__line_col = config.line_col
        self.__direction_col = config.direction_col
        self.__service_id_col = config.service_id_col
        self.__date_col = config.date_col
        self.__shape_dist_traveled_col = config.shape_dist_traveled_col
        self.__stop_name_col = config.stop_name_col
        self.__stop_lon_col = config.stop_lon_col
        self.__stop_lat_col = config.stop_lat_col
        self.__stop_passenger_count_col = config.stop_passenger_count_col
        self.__nb_boarding_col = config.nb_boarding_col
        self.__nb_alighting_col = config.nb_alighting_col
        self.__planned_arrival_time_col = config.planned_arrival_time_col
        self.__planned_departure_time_from_origin_col = config.planned_departure_time_from_origin_col

    def __save_to_file(self, gtfs_df, file_name, gtfs_folder, upgrade = False):
        """
        Sauvegarde un DataFrame GTFS dans un fichier CSV.
        
        Args:
            gtfs_df: DataFrame contenant les données GTFS
            file_name: Nom du fichier de sortie
            gtfs_folder: Dossier de destination
            upgrade: Indique si c'est une version améliorée des données
        """
        # Création du dossier s'il n'existe pas
        if not os.path.exists(gtfs_folder):
            os.makedirs(gtfs_folder)

        # Traitement par date
        dates_list = gtfs_df[self.__date_col].unique()
        for date in dates_list:
            # Extraction des données pour la date courante
            trips_day_df = gtfs_df[gtfs_df[self.__date_col] == date].drop(self.__date_col, axis=1)
            
            # Création du dossier pour la date s'il n'existe pas
            gtfs_day_folder = gtfs_folder + date.split(" ")[0] + "/"
            if not os.path.exists(gtfs_day_folder):
                os.makedirs(gtfs_day_folder)

            # Sauvegarde du fichier
            trips_day_df.to_csv(gtfs_day_folder + file_name, index=None)

    def __get_passage_arret_df(self):
        """
        Charge et combine les données de passage aux arrêts.
        
        Returns:
            DataFrame contenant toutes les données de passage aux arrêts
        """
        # Définition des types de colonnes
        columns_type_dict = {
            self.__trip_id_col: str,
            self.__direction_col: str,
            self.__line_col: str,
            self.__service_id_col: str,
            self.__arrival_time_col: float,
            self.__departure_time_col: float,
            self.__stop_id_col: str,
            self.__stop_sequence_col: int,
            self.__shape_dist_traveled_col: float,
            self.__date_col: str,
            self.__stop_name_col: str,
            self.__stop_lon_col: float,
            self.__stop_lat_col: float}

        # Lecture et combinaison de tous les fichiers
        passage_arret_df_list = []
        for passage_arret_file_path in self.__passage_arret_file_path_list:
            passage_arret_df_temp = pd.read_csv(passage_arret_file_path,
                                               usecols=columns_type_dict.keys(),
                                               delimiter=",",
                                               dtype=columns_type_dict)
            passage_arret_df_list.append(passage_arret_df_temp)
        passage_arret_df = pd.concat(passage_arret_df_list).reset_index(drop=True)

        return passage_arret_df
    
    def __get_passage_arret_upgrade_df(self):
        """
        Charge et combine les données de passage aux arrêts améliorées.
        
        Returns:
            DataFrame contenant toutes les données de passage aux arrêts améliorées
        """
        # Définition des types de colonnes avec les colonnes supplémentaires
        columns_type_dict = {
            self.__trip_id_col: str,
            self.__direction_col: str,
            self.__line_col: str,
            self.__service_id_col: str,
            self.__arrival_time_col: float,
            self.__departure_time_col: float,
            self.__stop_id_col: str,
            self.__stop_sequence_col: int,
            self.__shape_dist_traveled_col: float,
            self.__date_col: str,
            self.__stop_name_col: str,
            self.__stop_lon_col: float,
            self.__stop_lat_col: float,
            self.__planned_arrival_time_col: 'Int64',
            self.__planned_departure_time_from_origin_col: 'Int64'
            }
        
        # Lecture et combinaison de tous les fichiers
        passage_arret_df_list = []
        for passage_arret_file_path in self.__passage_arret_file_path_list:
            passage_arret_df_temp = pd.read_csv(passage_arret_file_path,
                                               usecols=columns_type_dict.keys(),
                                               delimiter=",",
                                               dtype=columns_type_dict)
            passage_arret_df_list.append(passage_arret_df_temp)
        passage_arret_df = pd.concat(passage_arret_df_list).reset_index(drop=True)

        return passage_arret_df

    def __get_stop_times_with_orig_time_df(self):
        """
        Calcule les temps relatifs à l'origine pour chaque arrêt.
        
        Returns:
            DataFrame contenant les temps d'arrêt avec leurs temps relatifs à l'origine
        """
        # Extraction des temps du premier arrêt de chaque trajet
        stop_times_seq_min_df = self.__stop_times_df.loc[
            self.__stop_times_df.groupby(self.__trip_id_col)[
                self.__stop_sequence_col].idxmin()]
        stop_times_seq0_df = stop_times_seq_min_df[
            stop_times_seq_min_df[self.__stop_sequence_col] == 0]
        time_seq0_df = stop_times_seq0_df[
            [self.__trip_id_col, self.__arrival_time_col,
             self.__departure_time_col]].rename(
            {self.__arrival_time_col: "arr_orig",
             self.__departure_time_col: "dep_orig"}, axis=1)

        # Calcul des temps relatifs à l'origine
        stop_times_with_orig_time_df = self.__stop_times_df.merge(
            time_seq0_df, left_on=self.__trip_id_col,
            right_on=self.__trip_id_col, how="left")
        stop_times_with_orig_time_df["arr_time_from_orig"] = \
            stop_times_with_orig_time_df[self.__arrival_time_col] - \
            stop_times_with_orig_time_df["arr_orig"]
        stop_times_with_orig_time_df["dep_time_from_orig"] = \
            stop_times_with_orig_time_df[self.__departure_time_col] - \
            stop_times_with_orig_time_df["dep_orig"]
        stop_times_with_orig_time_df.dropna(inplace=True)

        return stop_times_with_orig_time_df

    def __get_trip_id_set(self):
        """
        Extrait l'ensemble des identifiants de trajet valides.
        
        Returns:
            Ensemble des identifiants de trajet valides
        """
        # Regroupement par ligne, direction et séquence d'arrêt
        stop_times_grouped_by_line_seq = self.__stop_times_df.groupby(
            [self.__line_col, self.__direction_col, self.__stop_sequence_col])
        nb_chronobus_by_stop = stop_times_grouped_by_line_seq[
            self.__stop_id_col].apply(lambda x: len(set(x)))

        # Regroupement par ligne, direction, séquence d'arrêt et arrêt
        stop_times_grouped_by_line_seq_chronobus = \
            self.__stop_times_df.groupby([self.__line_col,
                                         self.__direction_col,
                                         self.__stop_sequence_col,
                                         self.__stop_id_col])
        trip_id_by_stop = stop_times_grouped_by_line_seq_chronobus[
            self.__trip_id_col].apply(set)

        # Extraction des trajets valides
        trip_id_set = set().union(
            *list(trip_id_by_stop[nb_chronobus_by_stop == 1]))

        return trip_id_set

    def __get_full_stop_times_df(self, stop_times_with_orig_time_filtered_df):
        """
        Construit un DataFrame complet des temps d'arrêt.
        
        Args:
            stop_times_with_orig_time_filtered_df: DataFrame filtré des temps d'arrêt
            
        Returns:
            DataFrame complet des temps d'arrêt avec toutes les informations nécessaires
        """
        # Regroupement par ligne, direction et séquence d'arrêt
        stop_times_orig_time_grouped_by_line_seq = \
            stop_times_with_orig_time_filtered_df.groupby(
                [self.__line_col, self.__direction_col,
                 self.__stop_sequence_col])
        
        # Extraction des informations de base
        bus_id_by_line_seq_series = stop_times_orig_time_grouped_by_line_seq[
            self.__stop_id_col].first()
        mean_shape_dist_traveled_by_line_seq_series = \
            stop_times_orig_time_grouped_by_line_seq[
                self.__shape_dist_traveled_col].mean()
        arr_time_from_orig_by_line_seq_series = \
            stop_times_orig_time_grouped_by_line_seq[
                "arr_time_from_orig"].mean()
        dep_time_from_orig_by_line_seq_series = \
            stop_times_orig_time_grouped_by_line_seq[
                "dep_time_from_orig"].mean()

        # Création du DataFrame de base
        line_seq_df = pd.DataFrame(
            {"stop_id": bus_id_by_line_seq_series,
             "mean_shape_dist_traveled":
                 mean_shape_dist_traveled_by_line_seq_series,
             "arr_time_from_orig":
                 arr_time_from_orig_by_line_seq_series,
             "dep_time_from_orig":
                 dep_time_from_orig_by_line_seq_series})

        # Association des trajets avec les lignes
        trip_id_by_line_series = \
            stop_times_with_orig_time_filtered_df.groupby(
                [self.__line_col, self.__direction_col])[
                self.__trip_id_col].apply(
                lambda x: list(set(x)))
        all_trip_id_by_line_series = trip_id_by_line_series.explode()
        
        # Fusion des données
        line_seq_with_trip_id_df = line_seq_df.merge(
            all_trip_id_by_line_series,
            left_on=[self.__line_col, self.__direction_col], right_index=True)

        # Création du DataFrame final
        line_job_seq_df = line_seq_with_trip_id_df.reset_index().groupby(
            [self.__line_col, self.__direction_col, self.__trip_id_col,
             self.__stop_sequence_col]).first()

        # Fusion avec les données originales
        full_stop_times_df = line_job_seq_df.merge(
            self.__stop_times_df, left_index=True,
            right_on=[self.__line_col, self.__direction_col,
                     self.__trip_id_col, self.__stop_sequence_col],
            how="left")

        # Extraction des temps d'origine
        full_stop_times_seq0_df = full_stop_times_df[
            full_stop_times_df[self.__stop_sequence_col] == 0]
        arr_dep_trip_id_df = full_stop_times_seq0_df[
            [self.__trip_id_col, self.__arrival_time_col,
             self.__departure_time_col]].rename(
            {self.__arrival_time_col: "arr_orig",
             self.__departure_time_col: "dep_orig"},
            axis=1)

        # Fusion finale avec les temps d'origine
        full_stop_times_df = full_stop_times_df.merge(
            arr_dep_trip_id_df, left_on=self.__trip_id_col,
            right_on=self.__trip_id_col)

        return full_stop_times_df

    def __get_stop_times_df(self, full_stop_times_df, shape_dist_traveled):
        """
        Construit le DataFrame final des temps d'arrêt.
        
        Args:
            full_stop_times_df: DataFrame complet des temps d'arrêt
            shape_dist_traveled: Indique si la distance parcourue doit être incluse
            
        Returns:
            DataFrame final des temps d'arrêt au format GTFS
        """
        # Copie des identifiants de trajet
        full_stop_times_df["trip_id"] = \
            full_stop_times_df[self.__trip_id_col]
        
        # Calcul des temps d'arrivée
        full_stop_times_df["arrival_time"] = full_stop_times_df.apply(
            lambda x: x[self.__arrival_time_col] if not pd.isnull(
                x[self.__arrival_time_col])
            else x["arr_time_from_orig"] + x["arr_orig"], axis=1)
        
        # Ajout des temps planifiés si nécessaire
        if shape_dist_traveled:
            full_stop_times_df["planned_arrival_time"] = full_stop_times_df.apply(
                lambda x: x[self.__planned_arrival_time_col] if not pd.isnull(
                    x[self.__planned_arrival_time_col])
                else x["arr_time_from_orig"] + x["arr_orig"], axis=1)
            full_stop_times_df["planned_departure_time_from_origin"] = full_stop_times_df.apply(
                lambda x: x[self.__planned_departure_time_from_origin_col] if not pd.isnull(
                    x[self.__planned_departure_time_from_origin_col])
                else x["arr_orig"], axis=1)
        
        # Calcul des temps de départ
        full_stop_times_df["departure_time"] = full_stop_times_df.apply(
            lambda x: x[self.__departure_time_col] if not pd.isnull(
                x[self.__departure_time_col])
            else x["dep_time_from_orig"] + x["dep_orig"], axis=1)
        
        # Calcul de la distance parcourue
        full_stop_times_df["shape_dist_traveled"] = full_stop_times_df.apply(
            lambda x: x[self.__shape_dist_traveled_col] if not pd.isnull(
                x[self.__shape_dist_traveled_col])
            else x["mean_shape_dist_traveled"], axis=1)

        # Correction des temps de départ pour les temps de trajet non positifs
        full_stop_times_df["arrival_time_lead"] = \
            full_stop_times_df.groupby(["trip_id"])["arrival_time"].shift(-1)
        full_stop_times_df["travel_time"] = \
            full_stop_times_df["arrival_time_lead"] \
            - full_stop_times_df["departure_time"]
        full_stop_times_df["departure_time"] = full_stop_times_df.apply(
            lambda x: x["departure_time"] if x["travel_time"] > 0
            else x["arrival_time"], axis=1)

        # Filtrage des temps de trajet positifs
        full_stop_times_df["arrival_time_lead"] = \
            full_stop_times_df.groupby(["trip_id"])["arrival_time"].shift(-1)
        full_stop_times_df["travel_time"] = \
            full_stop_times_df["arrival_time_lead"] \
            - full_stop_times_df["departure_time"]
        full_stop_times_df = full_stop_times_df[full_stop_times_df["travel_time"] > 0]

        # Calcul des temps précédents
        full_stop_times_grouped_by_voy_id = \
            full_stop_times_df.groupby("trip_id")
        full_stop_times_df["prev_arrival_times"] = \
            full_stop_times_grouped_by_voy_id["arrival_time"].transform(
                lambda x: [list(x.iloc[:e]) for e, i in enumerate(x)])
        full_stop_times_df["prev_departure_times"] = \
            full_stop_times_grouped_by_voy_id["departure_time"].transform(
                lambda x: [list(x.iloc[:e]) for e, i in enumerate(x)])
        full_stop_times_df["max_prev_arrival_times"] = full_stop_times_df[
            "prev_arrival_times"].apply(
            lambda x: max(x) if len(x) > 0 else None)
        full_stop_times_df["max_prev_departure_times"] = full_stop_times_df[
            "prev_departure_times"].apply(
            lambda x: max(x) if len(x) > 0 else None)

        # Filtrage des temps incohérents
        full_stop_times_df = full_stop_times_df[
            full_stop_times_df["arrival_time"] >= full_stop_times_df[
                "max_prev_arrival_times"]]
        full_stop_times_df = full_stop_times_df[
            full_stop_times_df["departure_time"] >= full_stop_times_df[
                "max_prev_departure_times"]]

        # Ajout des colonnes GTFS standard
        full_stop_times_df["stop_sequence"] = full_stop_times_df[
            self.__stop_sequence_col]
        full_stop_times_df["pickup_type"] = 0
        full_stop_times_df["drop_off_type"] = 0

        # Sélection des colonnes finales
        gtfs_columns = ["trip_id", "arrival_time", "departure_time", "stop_id",
                       "stop_sequence", "pickup_type", "drop_off_type"]
        if shape_dist_traveled:
            gtfs_columns.append("shape_dist_traveled")
            gtfs_columns.append("planned_arrival_time")
            gtfs_columns.append("planned_departure_time_from_origin")

        stop_times_all_dates_df = full_stop_times_df[gtfs_columns]

        return stop_times_all_dates_df

    def __correct_stop_times_df(self, stop_times_df):
        """
        Corrige les incohérences dans les temps d'arrêt.
        
        Args:
            stop_times_df: DataFrame des temps d'arrêt à corriger
            
        Returns:
            DataFrame corrigé des temps d'arrêt
        """
        # Correction des temps de départ inférieurs aux temps d'arrivée
        stop_times_df["departure_time"] = stop_times_df.apply(
            lambda x: x["departure_time"] if x["departure_time"] >= x[
                "arrival_time"] else x["arrival_time"], axis=1)

        # Correction des temps d'arrivée du prochain arrêt inférieurs aux temps de départ
        stop_times_df["arrival_time_lead"] = stop_times_df.groupby(
            [self.__date_col, "trip_id"])["arrival_time"].shift(-1)
        stop_times_df["departure_time"] = stop_times_df.apply(
            lambda x: x["departure_time"] if x["arrival_time_lead"] >= x[
                "departure_time"] else x["arrival_time"], axis=1)

        # Suppression des arrêts avec des temps incohérents
        stop_times_df = stop_times_df[
            stop_times_df["arrival_time_lead"] >= stop_times_df[
                "departure_time"]]

        stop_times_df = stop_times_df.drop("arrival_time_lead", axis=1)
        return stop_times_df
    
    def __sort_stop_times(self, stop_times_df):
        """
        Trie les temps d'arrêt selon différents critères.
        
        Args:
            stop_times_df: DataFrame des temps d'arrêt à trier
            
        Returns:
            DataFrame trié des temps d'arrêt
        """
        # Suppression des trajets avec un seul arrêt
        trip_id_grouped = stop_times_df.groupby("trip_id")
        trip_id_count = trip_id_grouped.size()
        trip_id_one_stop = trip_id_count[trip_id_count == 1].index
        stop_times_df = stop_times_df[~stop_times_df["trip_id"].isin(trip_id_one_stop)]

        # Tri par date, temps de départ planifié, identifiant de trajet et séquence d'arrêt
        colums_to_sort = [self.__date_col, "planned_departure_time_from_origin", 
                         "trip_id", "stop_sequence"]
        stop_times_df = stop_times_df.sort_values(by = colums_to_sort)

        return stop_times_df
