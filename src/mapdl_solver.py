from ansys.mapdl.core import launch_mapdl
from ansys.mapdl.core.mapdl_grpc import MapdlGrpc
import os
import numpy as np
import json
import time

global NUM_PROCESSORS, solver_parameters_file
NUM_PROCESSORS = 1

C = 273.15

global mapdl, parameters
mapdl: MapdlGrpc
parameters: dict

def to_absolute_path(path):
    return os.path.abspath(path) if not os.path.isabs(path) else os.path.normpath(path)

def validate_parameters():
    global parameters, NUM_PROCESSORS, solver_parameters_file

    required_parameters = {
        "model": str,
        "scale": float,
        "boundary_type": str,
        "boundary_selection": str,
    }

    allowable_boundary_types = ["temperature","convection","pipe_convection"]

    required_trial_parameters = {
        "time_step": int,
        "output_surfaces": list|str|np.ndarray,
        "initial_temperature": float,
        "output_step": int,
        "temperature_time_table": list|str|np.ndarray,
        "output_file": str,
        "materials": list|None
    }


    error_messages = []

    if NUM_PROCESSORS > os.cpu_count():
        print(f"Warning: Requested {NUM_PROCESSORS} processors, but only {os.cpu_count()} are available. Using {os.cpu_count()} processors instead.")
        NUM_PROCESSORS = os.cpu_count()

    parameters = json.loads(open(solver_parameters_file,"r").read())
    model_path = parameters["model"]
    parameters["model"] = to_absolute_path(model_path)

    parameters["scale"] = float(parameters.get("scale", 1.0))

    # add convection parameter requirements if needed
    if parameters["boundary_type"] == "convection":
        required_trial_parameters["convection_time_table"] = list|str|np.ndarray

    # create trials from input folder if specified
    if "trial_input_folder" in parameters:
        # search for all files in the trial input folder
        input_folder = to_absolute_path(parameters["trial_input_folder"])
        if not os.path.isdir(input_folder):
            error_messages.append(f"Specified trial_input_folder '{input_folder}' does not exist or is not a directory.")
        
        input_files = [f for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f))]

        if "trials" not in parameters: parameters["trials"] = []

        for input_file in input_files:
            # read the file as a csv, making a table where headers are keys
            file_path = os.path.join(input_folder, input_file)
            # Assuming comma delimiter based on context "read... as a csv"
            
            trial = {}
            trial["temperature_time_table"] = file_path
            trial["output_file"] = os.path.join(parameters.get("trial_output_folder","./"), f"results_{os.path.splitext(input_file)[0]}.csv")
            parameters["trials"].append(trial)


    # apply trial defaults to each trial
    for key, value in dict(parameters["trial_defaults"]).items():
        for trial in parameters["trials"]:
            if key not in trial:
                trial[key] = value

    # load temperature and convection tables, and material properties
    for trial in parameters["trials"]:
        if parameters["boundary_type"] == "convection":
            if "convection_time_table" not in trial and isinstance(trial.get("temperature_time_table"), str):
                trial["convection_time_table"] = trial.get("temperature_time_table")
            else:
                error_messages.append("For convection boundary type, each trial must have a 'convection_time_table' parameter. If 'temperature_time_table' is provided as a string path, it will be used as the 'convection_time_table'.")

        if isinstance(trial.get("temperature_time_table"), str):
            input_file = to_absolute_path(trial["temperature_time_table"])
            data_array = np.genfromtxt(input_file, delimiter=',', names=True, dtype=None, encoding='utf-8')
            csv_data = {name.lower(): data_array[name] for name in data_array.dtype.names}
            trial["temperature_time_table"] = np.array([csv_data["time"], csv_data["temp"]]).T

            if "output_file" not in trial:
                trial["output_file"] = os.path.join(parameters.get("trial_output_folder","./"), f"{os.path.splitext(input_file)[0]}_results.csv")
        
        if isinstance(trial.get("convection_time_table"), str):
            input_file = to_absolute_path(trial["convection_time_table"])
            data_array = np.genfromtxt(input_file, delimiter=',', names=True, dtype=None, encoding='utf-8')
            csv_data = {name.lower(): data_array[name] for name in data_array.dtype.names}
            trial["convection_time_table"] = np.array([csv_data["time"], csv_data["conv"]]).T
            
            if "output_file" not in trial:
                trial["output_file"] = os.path.join(parameters.get("trial_output_folder","./"), f"{os.path.splitext(input_file)[0]}_results.csv")

        if "initial_temperature" not in trial:
            trial["initial_temperature"] = trial["temperature_time_table"][0][1]

        if "materials" not in trial:
            trial["materials"] = None
    
    # ensure that there are trials to run
    if len(parameters["trials"]) == 0:
        error_messages.append("No trials specified. Please add trial configurations to the 'trials' parameter or provide trial input files in the 'trial_input_folder'.")

    # create output files and directories
    for i, trial in enumerate(parameters["trials"]):
        output_file = to_absolute_path(
            trial.get("output_file",
            os.path.join(parameters.get("trial_output_folder", f"./"), f"trial{i:03}_results.csv"))
            )
        
        output_folder = os.path.dirname(output_file)
        if not os.path.isdir(output_folder):
            os.makedirs(output_folder)
            print(f"Created directory for output file: {os.path.dirname(output_file)}")

        trial["output_file"] = output_file

    # validate required parameters
    for key, value in required_parameters.items():
        if key not in parameters:
            error_messages.append(f"Missing required parameter '{key}'")
        if not isinstance(parameters[key], value):
            error_messages.append(f"Parameter '{key}' must be of type {value}, but got {type(parameters[key])}")

    # validate boundary_type
    if parameters["boundary_type"] not in allowable_boundary_types:
        error_messages.append(f"Invalid boundary_type: {parameters['boundary_type']}. Must be one of {allowable_boundary_types}")



    # validate each trial's parameters
    for i, trial in enumerate(parameters["trials"]):
        for key, value in required_trial_parameters.items():
            if key not in trial:
                error_messages.append(f"Missing required trial parameter '{key}' for trial #{i}")
            if not isinstance(trial[key], value):
                error_messages.append(f"Trial parameter '{key}' must be of type {value}, but got {type(trial[key])}")


    
    # scale convection and temperature according to the scale parameter
    for trial in parameters["trials"]:
        scale = parameters["scale"]
        trial["temperature_time_table"][:,1] = (trial["temperature_time_table"][:,1] + C)*scale**2 - C
        if parameters["boundary_type"] == "convection":
            trial["convection_time_table"][:,1] /= scale

        trial["initial_temperature"] = (trial["initial_temperature"] + C)*scale**2 - C

    return error_messages

def start_solver():
    global mapdl, parameters, NUM_PROCESSORS
    run_dir = os.path.join(os.getcwd(), "temp_files")
    os.makedirs(run_dir, exist_ok=True)
    print("Launching solver...")
    mapdl = launch_mapdl(run_location=run_dir, override=True, nproc=NUM_PROCESSORS, start_timeout=80)

    mapdl.clear()
    mapdl.cdread("db", parameters["model"])

    print("Solver launched and loaded sucessfully.")

def apply_material_properties(trial):
    global mapdl

    mapdl.prep7()

    if trial.get("materials") is None:
        print("No materials specified for this trial. Skipping material property application.")
        return

    map = {
        "thermal_conductivity": "KXX",
        "density": "DENS",
        "specific_heat": "C"
    }

    #start with default temperature bounds
    all_temperatures = set([20, 500])

    # gather all unique temperatures from the material properties
    for material in trial.get("materials", []):
        for name in map.keys():
            value = material['properties'].get(name)

            if type(value) in [list, np.ndarray]:
                value = np.array(value)
                if type(value[0]) in [list, np.ndarray]:
                    all_temperatures.update(value[:,0])

    # sort the temperatures and convert to a numpy array
    all_temperatures = np.array(sorted(list(all_temperatures)))

    # clear the table
    mapdl.mptemp()
    # populate the temperature table with the unique temperatures
    for i in range(len(all_temperatures)):
        mapdl.mptemp(sloc=i+1, t1=all_temperatures[i])

    id = 1
    for material in trial.get("materials", []):
        mapdl.allsel()
        mapdl.cmsel('s', material['body_name'], entity='ELEM')
        mapdl.mpchg(mat=id, elem="all")

        for name, lab in map.items():
            value = material['properties'].get(name)

            values = np.array([])

            if type(value) in [int,float]:
                values = np.ones(all_temperatures.shape)*value
            elif type(value) in [list, np.ndarray]:
                value = np.array(value)
                # print(f"Interp material property '{name}'")
                # print(value)
                
                values = np.interp(all_temperatures, value[:,0], value[:,1])
            else:
                print(f"Invalid value type for material property '{name}': {type(value)}. Must be int, float, list, or np.ndarray.")
                print(values)
                continue
            
            for i in range(len(all_temperatures)):
                c1 = values[i]
                mapdl.mpdata(lab, mat=id, sloc=i+1, c1=c1)

        id += 1

    mapdl.finish()



def create_boundary_conditions():
    global mapdl, parameters
    mapdl.prep7() # model creation preprocessor

    mapdl.allsel()

    #select nodes on the desired boundary
    mapdl.cmsel('s', parameters["boundary_selection"], entity='NODE')

    # note: this table must be defined before adding the boundary condition(s),
    # but it can be modified afterwards and those changes will be reflected in the solver.
    mapdl.load_table("TEMP_TABLE", np.array([[0,0],[1,0]]), "TIME")
        
    if parameters["boundary_type"] == "convection":
        mapdl.load_table("CONV_TABLE",np.array([[0,0],[1,0]]), "TIME")
        mapdl.sf('all',lab='CONV', value="%CONV_TABLE%", value2="%TEMP_TABLE%")
    else:
        mapdl.d('all',lab='TEMP', value="%TEMP_TABLE%")

    # plot the selected boundary nodes to verify correct boundary selection, if having issues
    # mapdl.nplot()

    mapdl.finish()

def solve_trial(trial):
    global mapdl, parameters

    print(f"Solving trial with output file: {trial['output_file']}...")

    mapdl.load_table("TEMP_TABLE", np.array(trial["temperature_time_table"]), "TIME")
    if parameters["boundary_type"] == "convection":
        mapdl.load_table("CONV_TABLE", np.array(trial["convection_time_table"]), "TIME")

    mapdl.allsel()
    mapdl.slashsolu()
    mapdl.antype('TRANS') #analysis type
    mapdl.trnopt('FULL') #solving method: FULL, MSUP (superposition method)

    mapdl.tunif(trial["initial_temperature"]) #uniform initial temperature

    mapdl.time(trial["temperature_time_table"][-1, 0]) #total time period to solve over
    mapdl.timint("ON", "THERM") #turns on transient effects

    mapdl.autots('ON') #automatic time stepping on
    # initial, min, max
    mapdl.deltim(trial["time_step"], trial["time_step"], trial["time_step"])

    mapdl.kbc(0) #load step type: 0 ramp, 1 step
    output = mapdl.solve(verbose=False)
    mapdl.finish()

    print(f"Trial solved...")

def get_temperature_table(trial, substeps: list[int])->dict:
    """
    Process the results from the MAPDL simulation.

    Parameters
    ----------
    trial: dict
        contains "output_surfaces" : list[dict]
            A list of dictionaries with keys "selection" and "label", defining the named selections
            to process and their labels to output.
    substeps : list[int]
        A list of substep indices to process.

    Returns
    -------
    dict
        A dictionary containing the temperature table.
        Contains keys for each selection label corresponding to a `np.array` of
        average nodal temperatures at each substep,
        and key "substep" corresponding to the `np.array` of substeps.
    """
    global mapdl

    output_surfaces = trial["output_surfaces"]

    print("Processing results...")
    output = {}

    all_times = np.array(mapdl.result.time_values)
    times = all_times[substeps]

    output["substep"] = np.array(substeps)
    output["Time(s)"] = times
    output["temperature"] = np.interp(times, trial["temperature_time_table"][:,0], trial["temperature_time_table"][:,1])
    if parameters["boundary_type"] == "convection":
        output["convection"] = np.interp(times, trial["convection_time_table"][:,0], trial["convection_time_table"][:,1])

    selection_masks = []

    mapdl.post1()

    mapdl.allsel()

    all_node_ids = [int(nid) for nid in mapdl.mesh.nnum]
    all_selected_node_ids = set([])

    # create masks and initialize output arrays
    for surface in output_surfaces:
        selection_name = surface["selection"]

        mapdl.cmsel('s', selection_name, entity="NODE")
        node_ids = [int(nid) for nid in mapdl.mesh.nnum]
        all_selected_node_ids.update(node_ids)
        
        label = surface["label"]
        output[label] = np.zeros(len(substeps))

    all_selected_node_ids = list(all_selected_node_ids)
    
    for surface in output_surfaces:
        selection_name = surface["selection"]
        mapdl.cmsel('s', selection_name, entity="NODE")
        node_ids = [int(nid) for nid in mapdl.mesh.nnum]
        selection_masks.append(np.isin(all_node_ids, node_ids))

    mapdl.allsel()
    # mapdl.nsel('NONE')
    # for selection in output_selections:
    #     selection_name = selection["selection"]
    #     mapdl.cmsel('a', selection_name, entity="NODE")

    # Initialize timers
    t1_total = 0
    t2_total = 0

    for i, substep in enumerate(substeps):
        t0 = time.time()
        _, temperatures = mapdl.result.nodal_temperature(substep, nodes = all_selected_node_ids)
        t1_total += time.time() - t0

        t0 = time.time()
        for j in range(len(output_surfaces)):
            surface = output_surfaces[j]
            mask = selection_masks[j]
            label = surface["label"]

            output[label][i] = float(np.mean(temperatures[mask]))
        t2_total += time.time() - t0

    print(f"Total time for running nodal_temperature: {t1_total:.4f}s")
    print(f"Total time for processing selections: {t2_total:.4f}s")
    return output

def solve_all_trials():
    for trial in parameters["trials"]:

        t0 = time.time()
        apply_material_properties(trial)
        solve_trial(trial)
        t1 = time.time()
        solver_time = t1 - t0

        result = mapdl.result
        times = result.time_values

        output_substeps = np.array(
            [i for i, t in enumerate(times)
                if ((t % trial["output_step"]) < trial["time_step"]/2)]
        )
        
        t0 = time.time()
        temperature_table = get_temperature_table(trial, output_substeps)
        t1 = time.time()
        processing_time = t1 - t0

        with open(trial["output_file"], 'w') as file:
            scale = parameters["scale"]
            

            header_table = [
                ["model name", f"{os.path.basename(parameters['model'])}"],
                ["scale", f"{scale}"],
                ["number of nodes", f"{len(mapdl.mesh.nnum)}"],
                ["solver time (s)", f"{solver_time:.4f}"],
                ["processing time (s)", f"{processing_time:.4f}"],
                ["total time (s)", f"{(solver_time + processing_time):.4f}"],
                ["time step (s)", f"{trial['time_step']}"],
                ["output step size (s)", f"{trial['output_step']}"],
                ["duration (s)", f"{trial['temperature_time_table'][-1, 0]}"],
                ["boundary type", parameters["boundary_type"]],
                ]
            for _, row in enumerate(header_table):
                file.write(f"{row[0]}, {row[1]}\n")

            file.write("Time(s)")
            file.write(",Conv(W/m2*K)" if parameters["boundary_type"] == "convection" else "")
            file.write(",T_input(C)")
            
            for surface in trial["output_surfaces"]:
                label = surface["label"]
                file.write(f",{label}")
            file.write("\n")

            for i, substep in enumerate(temperature_table["substep"]):
                file.write(f"{times[substep]:.4f}")
                if parameters["boundary_type"] == "convection":
                    file.write(f",{temperature_table['convection'][i]*scale:.4f}")

                file.write(f",{(temperature_table['temperature'][i]+C)/scale**2-C:.4f}")

                for surface in trial["output_surfaces"]:
                    label = surface["label"]
                    file.write(f", {(temperature_table[label][i]+C)/scale**2-C:.4f}")
                file.write("\n")

def run_mapdl_solver(solver_parameters_path:str = None, num_processors:int = None):
    global solver_parameters_file, NUM_PROCESSORS
    if solver_parameters_path is not None:
        solver_parameters_file = solver_parameters_path
    if num_processors is not None:
        NUM_PROCESSORS = num_processors

    errors = validate_parameters()
    if errors:
        print("Validation errors found:")
        for error in errors:
            print(f" - {error}")
        return
    
    try:
        start_solver()
    except Exception as e:
        print(f"Error connecting to MAPDL: {e}")
        print("Please ensure that MAPDL is installed. Verify that Ansys can be opened and run on your computer. You may need to connect to the UCI VPN to access the Ansys license.")
        return
    
    create_boundary_conditions()

    solve_all_trials()
    
    mapdl.exit()


if __name__ == "__main__":
    run_mapdl_solver(solver_parameters_path = "./solver_parameters.json", num_processors = 3)