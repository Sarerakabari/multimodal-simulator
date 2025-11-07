import logging  # Required to modify the log level
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))  # ...\examples
sys_dir=os.path.normpath(os.path.join(current_dir,'..'))
root_project=os.path.normpath(os.path.join(current_dir,'..','..'))
sys.path.insert(0, sys_dir)

from multimodalsim.__main__ import extract_simulation_output
from multimodalsim.observer.environment_observer import \
    StandardEnvironmentObserver
from multimodalsim.optimization.fixed_line.fixed_line_dispatcher import \
    FixedLineDispatcher
# from multimodalsim.optimization.fixed_line.fixed_line_synchro_dispatcher import \
#     FixedLineSynchroDispatcher
from multimodalsim.optimization.optimization import Optimization
from multimodalsim.optimization.splitter import MultimodalSplitter_synchro
from multimodalsim.reader.data_reader import GTFSReader, os
from multimodalsim.simulator.coordinates import CoordinatesFromFile, CoordinatesOSRM
from multimodalsim.simulator.simulation import Simulation
from operator import itemgetter

def define_next_vehicles( routes_by_vehicle_id, route_name_by_vehicle_id ): 
    all_vehicles_with_start_times_and_route_names = [(vehicle_id, routes_by_vehicle_id[vehicle_id].current_stop.arrival_time, route_name_by_vehicle_id[vehicle_id]) for vehicle_id in routes_by_vehicle_id]
    all_vehicles_with_start_times_and_route_names = sorted(all_vehicles_with_start_times_and_route_names, key = itemgetter(2, 1))
    next_vehicles = {}
    for i in range(len(all_vehicles_with_start_times_and_route_names) - 1):
        if all_vehicles_with_start_times_and_route_names[i][2] == all_vehicles_with_start_times_and_route_names[i+1][2]:
            next_vehicles[all_vehicles_with_start_times_and_route_names[i][0]] = all_vehicles_with_start_times_and_route_names[i+1][0]
        else:
            next_vehicles[all_vehicles_with_start_times_and_route_names[i][0]] = None
    next_vehicles[all_vehicles_with_start_times_and_route_names[-1][0]] = None
    return next_vehicles


def stl_gtfs_transfer_synchro_simulator(gtfs_folder_path=os.path.join(root_project,"data","fixed_line","gtfs","gtfs-generated-small"),
                       requests_file_path=os.path.join(root_project,"data","fixed_line","gtfs","gtfs-generated-small","requests.csv"),
                       coordinates_file_path=None,
                       routes_to_optimize_names = [],
                       ss = False,
                       sp = False,
                       algo = 0,
                       freeze_interval = 5,
                       output_folder_name = "gtfs-generated-small",
                       logging_level = logging.WARNING,
                        is_corridor = False,
                       transfer_hubs = []):

    
    sys.path.append(current_dir)
    sys.path.append(r"/home/kollau/Recherche_Kolcheva/Simulator/python/examples")
    sys.path.append(os.path.abspath('../../..'))

    # To modify the log level (at INFO, by default)
    logger = logging.getLogger(__name__)
    logging.getLogger().setLevel(logging_level)
    logger.warning(" Start simulation for instance with skip_stop_is_allowed = {}, speedup_is_allowed = {}, algo = {}".format(ss, sp, algo))
    # show logging level
    logger.warning("Logging level: {}".format(logging.getLevelName(logger.getEffectiveLevel())))
    # Read input data from files with a DataReader. The DataReader returns a
    # list of Vehicle objects and a list of Trip objects.
    data_reader = GTFSReader(gtfs_folder_path, requests_file_path)

    # Set to None if coordinates of the vehicles are not available.
    if coordinates_file_path is not None:
        coordinates = CoordinatesFromFile(coordinates_file_path)
    else:
        coordinates = CoordinatesOSRM()

    vehicles, routes_by_vehicle_id, route_name_by_vehicle_id = data_reader.get_vehicles()

    trips, cap_vehicle_id_by_leg, route_name_by_leg = data_reader.get_trips()

    next_vehicles=define_next_vehicles(routes_by_vehicle_id,route_name_by_vehicle_id )

    # Get available connections saved in a .json file in the data folder
    available_connections_path = os.path.join(gtfs_folder_path, "available_connections.json")
    available_connections = data_reader.get_available_connections(available_connections_path)

    # Generate the network from GTFS files.
    g = data_reader.get_network_graph(available_connections=available_connections)

    # Initialize the optimizer.
    splitter = MultimodalSplitter_synchro(g, available_connections=available_connections,
                                  freeze_interval=freeze_interval,
                                  
                                  )
    routes_to_optimize_names = routes_to_optimize_names if routes_to_optimize_names!=[] else list(set([route_name_by_vehicle_id [vehicle.id] for vehicle in vehicles]))
    
    # Create the output folder
    output_folder_path = os.path.join(root_project,"output","fixed_line","gtfs", output_folder_name)
    output_folder_path = get_output_subfolder(output_folder_path, algo, ss, sp, routes_to_optimize_names)
    print(output_folder_path)

    
    # Update transfer hubs with available connections
    all_transfer_stop_ids = []
    for stop_id in transfer_hubs:
        if int(stop_id) in available_connections:
            all_transfer_stop_ids += available_connections[int(stop_id)]
            
    # Initialize the dispatcher.
    dispatcher = FixedLineDispatcher(ss = ss,
                                     sp = sp,
                                     algo = algo, 
                                     routes_to_optimize_names = routes_to_optimize_names,
                                     output_folder_path = output_folder_path,
                                     is_corridor = is_corridor,
                                     transfer_hubs = all_transfer_stop_ids,
                                     next_vehicles=next_vehicles,
                                     route_name_by_vehicle_id=route_name_by_vehicle_id,
                                     cap_vehicle_id_by_leg=cap_vehicle_id_by_leg,
                                     route_name_by_leg=route_name_by_leg)
    Data = {}
    for route_name in routes_to_optimize_names: 
        logger.info("Getting and clustering data for route %s" % route_name)
        Data[route_name] = dispatcher.get_and_cluster_data(route_name = route_name)
    dispatcher.Data = Data

    # Initialize the optimization.   
    opt = Optimization(dispatcher, splitter, freeze_interval=freeze_interval)

    # Initialize the observer.
    environment_observer = StandardEnvironmentObserver()

    # Initialize the simulation.
    simulation = Simulation(opt,
                            trips,
                            vehicles,
                            routes_by_vehicle_id,
                            environment_observer=environment_observer,
                            # coordinates=coordinates,
                        )
    
    # Execute the simulation.
    simulation.simulate()

    # Extract the simulation output
    extract_simulation_output(simulation, output_folder_path)

def get_output_subfolder(output_folder_path, algo, ss, sp, routes_to_optimize_names):
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)
    
    add = ''
    # Smart card usage addendum
    
    add+='SMARTCARD_' # Use historical smart card data to recreate trips for O/D pairs
  
    # Algorithm addendum
    if algo == 0:
        add += 'O' # Offline
        # Create the output folder
        output_folder_path_with_addendum = os.path.join(output_folder_path, add)
        if not os.path.exists(output_folder_path_with_addendum):
            os.makedirs(output_folder_path_with_addendum)
        return output_folder_path_with_addendum
    
    if algo == 1:
        add += 'D_' # Deterministic
    elif algo == 2:
        add += 'R_'# Regret
    elif algo == 3:
        add += 'PI_' # Perfect information

    # Tactics addendum
    if ss and sp:
        add += 'SPSS_' # Skip stop speed up, and hold
    elif ss:
        add += 'SS_' # Skip stop and hold
    elif sp:
        add += 'SP_' # Speed up and hold
    else:
        add += 'H_' # Hold

    # Routes to optimize addendum
    add += 'ROUTES_'
    if len(routes_to_optimize_names) == 1: # Optimize one route
        add +='SINGLE_'+ routes_to_optimize_names[0]
    else: # Optimize multiple routes
        add += 'MULTIPLE'
        # for route in routes_to_optimize_names:
        #     add += '_'+ route
    
    # Create the output folder
    output_folder_path_with_addendum = os.path.join(output_folder_path, add)
    if not os.path.exists(output_folder_path_with_addendum):
        os.makedirs(output_folder_path_with_addendum)
    return output_folder_path_with_addendum