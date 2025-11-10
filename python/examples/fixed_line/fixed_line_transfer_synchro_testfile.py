### DO NOT CHANGE THESE LINES: Parameters are auto-filled in stl_gtfs_parameter_parser_and_test_file_generator.py
### BEGINNING OF PARAMETERS ###
import os
import traceback
current_dir = os.path.dirname(os.path.abspath(__file__))  # ...\examples
project_root = os.path.normpath(os.path.join(current_dir,'..', '..','..'))
gtfs_folder_path = os.path.join(project_root,"data","fixed_line","gtfs","gtfs2019-11-01-Test_de_comparaison_modeles")
requests_file_path = os.path.join(gtfs_folder_path,"requests.csv")
output_folder_name = "gtfs2019-11-01_Test_de_comparaison_modeles_output"
routes_to_optimize_names =  ["70E","70O"]
algo =3
sp = False
ss = False
is_corridor = False
transfer_hubs = []
### END OF PARAMETERS ###

import sys
import time
import logging
sys.path.append(os.path.abspath('../../..'))
current_dir = os.path.dirname(os.path.abspath(__file__))  # ...\examples
sys_dir=os.path.normpath(os.path.join(current_dir,'..'))
sys.path.insert(0, sys_dir)
from stl_gtfs_transfer_synchro import stl_gtfs_transfer_synchro_simulator
# Setup the logger
logging_level = logging.WARNING
# Start the simulation
start_time=time.time()
print('Begin testing...')
coordinates_file_path = None
freeze_interval = 0
try: 
    stl_gtfs_transfer_synchro_simulator(
                        gtfs_folder_path=gtfs_folder_path,
                        requests_file_path=requests_file_path,
                        coordinates_file_path=coordinates_file_path,
                        routes_to_optimize_names = routes_to_optimize_names,
                        ss = ss, # Allow the use of skip-stop tactics
                        sp = sp, # Allow the use of speedup tactics
                        algo = algo, # 0: offline, 1: deterministic, 2: regret, 3: Perfect Information
                        freeze_interval = freeze_interval,
                        output_folder_name = output_folder_name,
                        logging_level = logging_level,
                        is_from_smartcard_data = True,
                        is_corridor = is_corridor,
                        transfer_hubs = transfer_hubs
                        )
    final_time = time.time() - start_time
    print('Execution time: ', final_time)
    print('End testing...')
except Exception as e:
    print('An error occured during the simulation')
    # traceback.print_exc()
    error_traceback = traceback.format_exc()
    print('Error traceback: ', error_traceback)
    final_time = time.time() - start_time
    print('Execution time: ', final_time)
    print('End testing after error...')