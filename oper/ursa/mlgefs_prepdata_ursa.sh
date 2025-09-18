#!/bin/bash --login

# load necessary modules
module use /contrib/spack-stack/spack-stack-1.9.1/envs/ue-oneapi-2024.2.1/install/modulefiles/Core/
module load stack-oneapi
module load wgrib2
module list

# Activate Conda environment
source /scratch3/NCEPDEV/nems/Linlin.Cui/miniforge3/etc/profile.d/conda.sh
conda activate graphcast

echo "Current state: $curr_datetime"
echo "6 hours earlier state: $prev_datetime"

export GEFSDATA=/scratch3/NCEPDEV/stmp/Linlin.Cui/gefs_wcoss2

DATAROOT=/scratch3/NCEPDEV/stmp/$USER
PDY=${curr_datetime:0:8}
cyc=${curr_datetime:8:2}

num_pressure_levels=13
echo "number of pressure levels: $num_pressure_levels"

start_time=$(date +%s)
echo "Generate graphcast inputs for: $curr_datetime"
# Run the Python script gdas.py with the calculated times
python gen_gefs_ics.py "$prev_datetime" "$curr_datetime" "$gefs_member" -l "$num_pressure_levels" -s cached -o $DATAROOT/pmlgefs."$PDY"/"$cyc"/ -d $DATAROOT/pmlgefs."$PDY"/"$cyc"/

end_time=$(date +%s)  # Record the end time in seconds since the epoch

# Calculate and print the execution time
execution_time=$((end_time - start_time))
cho "Execution time for gen_gefs_ics.py: $execution_time seconds"
