### DO NOT CHANGE THESE LINES: Parameters are auto-filled in stl_gtfs_parameter_parser_and_test_file_generator.py
### BEGINNING OF PARAMETERS ###
import os
import traceback

# Chemins des fichiers et dossiers pour les données GTFS
gtfs_folder_path = os.path.join("data","fixed_line","gtfs","gtfs2019-11-25-LargeInstanceAll")
requests_file_path = os.path.join(gtfs_folder_path,"requests.csv")
output_folder_name = "gtfs2019-11-25_LargeInstanceAll"

# Liste des lignes de bus à optimiser
# Les suffixes E/O/S/N indiquent la direction :
# E: Est, O: Ouest, S: Sud, N: Nord
routes_to_optimize_names =  ['144E', '144O', '20E', '20O', '222E', '222O', '22E', '22O', '24E', '24O', '252E', '252O', '26E', '26O', '42E', '42O', '52E', '52O', '56E', '56O', '60E', '60O', '66E', '66O', '70E', '70O', '74E', '74O', '76E', '76O', '942E', '942O', '151S', '151N', '17S', '17N', '27S', '27N', '33S', '33N', '37S', '37N', '41S', '41N', '43S', '43N', '45S', '45N', '46S', '46N', '55S', '55N', '61S', '61N', '63S', '63N', '65S', '65N', '901S', '901N', '902S', '902N', '903S', '903N', '925S', '925N']

# Paramètres de l'algorithme d'optimisation
algo = 0  # 0: offline, 1: deterministic, 2: regret, 3: Perfect Information
sp = False  # Activation des tactiques de speedup
ss = False  # Activation des tactiques de skip-stop
is_corridor = False  # Indique si l'optimisation concerne un corridor
transfer_hubs = []  # Liste des hubs de transfert à considérer
### END OF PARAMETERS ###

import sys
import time
import logging

# Ajout des chemins au système pour importer les modules nécessaires
sys.path.append(os.path.abspath('../../..'))
sys.path.append(r"C:\Users\kklau\Desktop\Simulator\python\examples")
sys.path.append(r"/home/kollau/Recherche_Kolcheva/Simulator/python/examples")

# Importation du simulateur de synchronisation des transferts
from stl_gtfs_transfer_synchro import stl_gtfs_transfer_synchro_simulator

# Configuration du logger pour le suivi de l'exécution
logging_level = logging.WARNING

# Démarrage de la simulation
start_time=time.time()
print('Begin testing...')

# Paramètres supplémentaires pour la simulation
coordinates_file_path = None  # Chemin vers le fichier des coordonnées (non utilisé)
freeze_interval = 1  # Intervalle de gel pour l'optimisation (en secondes)

try: 
    # Appel du simulateur avec les paramètres configurés
    stl_gtfs_transfer_synchro_simulator(
                        gtfs_folder_path=gtfs_folder_path,  # Dossier contenant les données GTFS
                        requests_file_path=requests_file_path,  # Fichier des demandes
                        coordinates_file_path=coordinates_file_path,  # Coordonnées (optionnel)
                        routes_to_optimize_names = routes_to_optimize_names,  # Lignes à optimiser
                        ss = ss,  # Utilisation des tactiques de skip-stop
                        sp = sp,  # Utilisation des tactiques de speedup
                        algo = algo,  # Choix de l'algorithme d'optimisation
                        freeze_interval = freeze_interval,  # Intervalle de gel
                        output_folder_name = output_folder_name,  # Nom du dossier de sortie
                        logging_level = logging_level,  # Niveau de log
                        is_from_smartcard_data = True,  # Utilisation des données de cartes à puce
                        is_corridor = is_corridor,  # Indicateur de corridor
                        transfer_hubs = transfer_hubs  # Liste des hubs de transfert
                        )
    
    # Affichage du temps d'exécution
    final_time = time.time() - start_time
    print('Execution time: ', final_time)
    print('End testing...')
    
except Exception as e:
    # Gestion des erreurs avec affichage de la trace d'erreur
    print('An error occured during the simulation')
    error_traceback = traceback.format_exc()
    print('Error traceback: ', error_traceback)
    final_time = time.time() - start_time
    print('Execution time: ', final_time)
    print('End testing after error...')