import logging  # Pour modifier le niveau de log
from multimodalsim.__main__ import extract_simulation_output
from multimodalsim.observer.environment_observer import \
    StandardEnvironmentObserver
from multimodalsim.optimization.fixed_line.fixed_line_dispatcher import \
    FixedLineDispatcher
# from multimodalsim.optimization.fixed_line.fixed_line_synchro_dispatcher import \
#     FixedLineSynchroDispatcher
from multimodalsim.optimization.optimization import Optimization
from multimodalsim.optimization.splitter import MultimodalSplitter
from multimodalsim.reader.data_reader import GTFSReader, os
from multimodalsim.simulator.coordinates import CoordinatesFromFile, CoordinatesOSRM
from multimodalsim.simulator.simulation import Simulation
import sys

def stl_gtfs_transfer_synchro_simulator(gtfs_folder_path=os.path.join("data","fixed_line","gtfs","gtfs-generated-small"),
                       requests_file_path=os.path.join("data","fixed_line","gtfs","gtfs-generated-small","requests.csv"),
                       coordinates_file_path=None,
                       routes_to_optimize_names = [],
                       ss = False,
                       sp = False,
                       algo = 0,
                       freeze_interval = 5,
                       output_folder_name = "gtfs-generated-small",
                       logging_level = logging.WARNING,
                       is_from_smartcard_data = True,
                       is_corridor = False,
                       transfer_hubs = []):
    """
    Simulateur de synchronisation des transferts pour le transport en commun.
    
    Cette fonction gère la simulation complète du système de transport, incluant :
    - La lecture des données GTFS
    - L'optimisation des horaires
    - La synchronisation des transferts
    - La génération des résultats
    
    Args:
        gtfs_folder_path: Chemin vers le dossier contenant les fichiers GTFS
        requests_file_path: Chemin vers le fichier des demandes
        coordinates_file_path: Chemin vers le fichier des coordonnées (optionnel)
        routes_to_optimize_names: Liste des lignes à optimiser
        ss: Booléen pour activer les tactiques de skip-stop
        sp: Booléen pour activer les tactiques de speedup
        algo: Type d'algorithme d'optimisation (0: offline, 1: deterministic, 2: regret, 3: Perfect Information)
        freeze_interval: Intervalle de gel pour l'optimisation
        output_folder_name: Nom du dossier de sortie
        logging_level: Niveau de log
        is_from_smartcard_data: Booléen indiquant si les données proviennent de cartes à puce
        is_corridor: Booléen indiquant si l'optimisation concerne un corridor
        transfer_hubs: Liste des hubs de transfert
    """
    # Configuration des chemins d'accès
    sys.path.append(r"C:\Users\kklau\Desktop\Simulator\python\examples")
    sys.path.append(r"/home/kollau/Recherche_Kolcheva/Simulator/python/examples")
    sys.path.append(os.path.abspath('../../..'))
    
    # Configuration du logger
    logger = logging.getLogger(__name__)
    logging.getLogger().setLevel(logging_level)
    logger.warning(" Start simulation for instance with skip_stop_is_allowed = {}, speedup_is_allowed = {}, algo = {}".format(ss, sp, algo))
    logger.warning("Logging level: {}".format(logging.getLevelName(logger.getEffectiveLevel())))

    # Lecture des données d'entrée avec le lecteur GTFS
    data_reader = GTFSReader(gtfs_folder_path, requests_file_path)

    # Configuration des coordonnées (fichier ou service OSRM)
    if coordinates_file_path is not None:
        coordinates = CoordinatesFromFile(coordinates_file_path)
    else:
        coordinates = CoordinatesOSRM()

    # Récupération des véhicules et des trajets
    vehicles, routes_by_vehicle_id = data_reader.get_vehicles()
    trips = data_reader.get_trips()

    # Lecture des connexions disponibles depuis le fichier JSON
    available_connections_path = os.path.join(gtfs_folder_path, "available_connections.json")
    available_connections = data_reader.get_available_connections(available_connections_path)

    # Génération du graphe de réseau à partir des fichiers GTFS
    g = data_reader.get_network_graph(available_connections=available_connections)

    # Initialisation de l'optimiseur
    splitter = MultimodalSplitter(g, available_connections=available_connections,
                                  freeze_interval=freeze_interval,
                                  is_from_smartcard_data = is_from_smartcard_data)
    
    # Sélection des lignes à optimiser
    routes_to_optimize_names = routes_to_optimize_names if routes_to_optimize_names!=[] else list(set([vehicle.route_name for vehicle in vehicles]))
    
    # Création du dossier de sortie
    output_folder_path = os.path.join("output","fixed_line","gtfs", output_folder_name)
    output_folder_path = get_output_subfolder(output_folder_path, algo, ss, sp, routes_to_optimize_names, is_from_smartcard_data)
    print(output_folder_path)

    # Mise à jour des hubs de transfert avec les connexions disponibles
    all_transfer_stop_ids = []
    for stop_id in transfer_hubs:
        if int(stop_id) in available_connections:
            all_transfer_stop_ids += available_connections[int(stop_id)]
            
    # Initialisation du dispatcher
    dispatcher = FixedLineDispatcher(ss = ss,
                                     sp = sp,
                                     algo = algo, 
                                     routes_to_optimize_names = routes_to_optimize_names,
                                     output_folder_path = output_folder_path,
                                     is_corridor = is_corridor,
                                     transfer_hubs = all_transfer_stop_ids)
    
    # Récupération et clustering des données pour chaque ligne
    Data = {}
    for route_name in routes_to_optimize_names: 
        logger.info("Getting and clustering data for route %s" % route_name)
        Data[route_name] = dispatcher.get_and_cluster_data(route_name = route_name)
    dispatcher.Data = Data

    # Initialisation de l'optimisation
    opt = Optimization(dispatcher, splitter, freeze_interval=freeze_interval)

    # Initialisation de l'observateur
    environment_observer = StandardEnvironmentObserver()

    # Initialisation de la simulation
    simulation = Simulation(opt,
                            trips,
                            vehicles,
                            routes_by_vehicle_id,
                            environment_observer=environment_observer,
                            transfer_synchro = True)
    
    # Exécution de la simulation
    simulation.simulate()

    # Extraction des résultats de la simulation
    extract_simulation_output(simulation, output_folder_path)

def get_output_subfolder(output_folder_path, algo, ss, sp, routes_to_optimize_names, is_from_smartcard_data):
    """
    Génère le nom du sous-dossier de sortie en fonction des paramètres de simulation.
    
    Args:
        output_folder_path: Chemin de base du dossier de sortie
        algo: Type d'algorithme utilisé
        ss: Utilisation des tactiques de skip-stop
        sp: Utilisation des tactiques de speedup
        routes_to_optimize_names: Liste des lignes optimisées
        is_from_smartcard_data: Utilisation des données de cartes à puce
        
    Returns:
        Chemin complet du sous-dossier de sortie
    """
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)
    
    add = ''
    # Ajout du préfixe selon le type de données
    if is_from_smartcard_data:
        add+='SMARTCARD_'  # Utilisation des données historiques de cartes à puce
    else:
        add+='SIMU_'  # Simulation des trajets optimaux

    # Ajout du suffixe selon l'algorithme
    if algo == 0:
        add += 'O'  # Offline
        output_folder_path_with_addendum = os.path.join(output_folder_path, add)
        if not os.path.exists(output_folder_path_with_addendum):
            os.makedirs(output_folder_path_with_addendum)
        return output_folder_path_with_addendum
    
    if algo == 1:
        add += 'D_'  # Déterministe
    elif algo == 2:
        add += 'R_'  # Regret
    elif algo == 3:
        add += 'PI_'  # Information parfaite

    # Ajout du suffixe selon les tactiques utilisées
    if ss and sp:
        add += 'SPSS_'  # Skip-stop et speedup
    elif ss:
        add += 'SS_'  # Skip-stop uniquement
    elif sp:
        add += 'SP_'  # Speedup uniquement
    else:
        add += 'H_'  # Hold uniquement

    # Ajout du suffixe selon le nombre de lignes optimisées
    add += 'ROUTES_'
    if len(routes_to_optimize_names) == 1:
        add +='SINGLE_'+ routes_to_optimize_names[0]  # Optimisation d'une seule ligne
    else:
        add += 'MULTIPLE'  # Optimisation de plusieurs lignes
    
    # Création du dossier de sortie
    output_folder_path_with_addendum = os.path.join(output_folder_path, add)
    if not os.path.exists(output_folder_path_with_addendum):
        os.makedirs(output_folder_path_with_addendum)
    return output_folder_path_with_addendum