# Installation

Open the folder containing the project files in VS Code (Either download or clone repository)

Install the required packages using the command in a new terminal:
`pip install -r requirements.txt`
(created from `pip freeze > requirements.txt`)

Run `python ./src/mapdl_solver.py` in a terminal opened in the root folder

Notes: 

- If you ever run into an issue saying that there is a lock in place, delete the `temp_files` folder and use Task Manager (windows app) to end all tasks with the name "APDL" or other ansys things.

- Make sure you are either on UCI wifi or on the UCI VPN for Ansys licensing to work properly. Use the Ansys Licencing Settings app for help with this, or if the app fails to launch.

# Get model cdb file from Ansys Mechanical:

The cdb file contains all of the needed geometric, material, and static boundary properties (such as connections between bodies) to run a simulation.

Material must be set for Ansys to run, but materials can be overwritten using this program (see trials for details).

This solver creates the dynamic boundary condition (convection or temperature applied to a surface), so these should not be included in the cdb file.

1. Create geometry, mesh, contacts, and assign materials in Ansys Mechanical

2. Remove/supress all dynamic boundaries (temperature/convection) because these will be created by the solver.

3. Select the inner pipe surface and right click `Insert -> Named Selection`  
    Name it "heated_surface".  
    Do the same for the surfaces whose temperature is recorded, naming them uniquely.

    Repeat for entire bodies whose materials need to be set.

    Record these names in the solver parameters file.

4. Under `Transient Thermal` in the tree on the left, right click `Insert -> Commands`, and type:  
    CDWRITE,DB,"C:\\...\\file_name", cdb  
    where your desired absolute file path is provided. This can be copied from Windows file explorer by navigating to your desired location, then click on the top middle bar and copy the folder address. Then, add your file name after the last folder. Do not include the extension (.cdb) in the file path.

5. Press `Solve` in Ansys and a file will be generated at the specified location which contains the necessary information.   
    You may get an error message saying that there aren't any boundary conditions. This is fine, just ignore it.

    It may help to set the time for the simulation to be short in order to reduce "solving" time. These settings are reset by the Mapdl Solver program.


# Setting up solver parameters

Use the `solver_parameters.json` file to change most parameters. This uses JSON format, containing an object with several parameters. View the provided example files if you get stuck on formatting.

The number of processors to use can be changed at the top of `src/mapdl_solver.py`

## Parameters
- `"model"`
    - The name of the cdb model to use. This only includes geometric and material properties, and named selections. **DO NOT HAVE ACTIVE BOUNDARY CONDITIONS WHEN EXPORTING**

- `"boundary_type"`
    - Must be either "convection" or "temperature".

- `"boundary_selection"`
    - The name of the named selection where the boundary condition (either temperature or convection) is applied.

- `"trials"` or `"trial_input_folder"` and `"trial_output_folder"`
    - Specifies the simulation parameters for each individual simulation

- `"trial_defaults"`
    - Specifies any parameters needed to complete trial definitions

## Trials

You can use `"trials"` or `"trial_input_folder"` (or both) to define trials, which describe the details of each simulation to perform. The solver will run all trials sequentially.

If `"trials"` is used, create a list of objects containing the required parameters. Any parameters which are missing from any trial must be defined in `"trial_defaults"`. Defaults do not overwrite individual trials.

If `"trial_input_folder"` is used, `"trial_output_folder"` must also be defined. In addition, all trial parameters other than the tables must be defined in `trial_defaults`.

- `"trial_input_folder"` is the name of the directory to find csv input files (i.e. `./sub_folder`), which must contain a column labeled `time` and `temp`, and `conv` if a convection boundary is used. Extra columns will be ignored.

- `"trial_output_folder"` is the folder where output files will be created, where the name of each output file is `"result_" + trial file name`

### Material Selection
- `"materials"`: **list[object]**
    - List of `{"body_name":"...", "properties":{...}}`, where `"body_name"` is the name of the named selection where this material will be applied.
    - Properties can be `"thermal_conductivity"`, `"density"`, and `"specific_heat"`
        - Values can be either a number for a constant value, or a temperature based table `[[T0,P0], [T1,P1], ...]`, where `T` is temperature and `P` is the property value.
    - Thermal conductivity in `W/m*K`
    - Density in `kg/m^3`
    - Specific heat in `J/kg*K`

### Required Parameters
- `"time_step"`: **number**
    - Simulation time step (seconds)

- `"output_surfaces"`: **list[object]**
    - List of `{"selection":"...", "label":"..."}`, where selection is the named selection surface, and label is the name that will be used in the results file header

- `"initial_temperature"`: **number**
    - Uniform starting temperature in Celcius
    - Defaults to the first temperature in the temperature table

- `"output_step"`: **number**
    - Seconds between recording the simulation data to the results file. If this is not a multiple of the time step parameter, the nearest time step will be used.

- `"temperature_time_table"`: **list[list]** or **string**
    - Time is in seconds and temperature is in Celcius
    - Option 1: Name of a CSV file containing columns of equal lengths, one labeled "time", another labeled "conv". Default location is the project root.
    - Option 2: A table formatted like `[[time0, temp0],[time1,temp1],...]`.

- `"convection_time_table"`: **list[list]** or **string**
    - Only if using a convection boundary
    - Time is in seconds and convection coefficient is in W/m²K
    - Option 1: A CSV file containing columns of equal lengths, one labeled "time", another labeled "conv". Default location is the project root.
    - Option 2: A table formatted like `[[time0, conv0],[time1,conv1],...]`.

- `"output_file"`: **string**
    - Defaults to `"trial_000"`, with the number corresponding to when the trial is defined. Default output location is the project root folder, but can be set by setting the global `trial_output_folder`
    - Name of the CSV file to output results into (creates file and directory if it doesn't exist). Can contain subdirectories by using `./sub_folder/file_name.csv`