#!/bin/bash --login

module load intel/19.1.3.304 
module use /apps/dev/lmodules/intel/19.1.3.304
module load libjpeg/9c
module load ve/eagle/1.0

HOMEDIR=${1:-/lfs/h2/emc/nems/noscrub/$USER/mlglobal}

JOBDIR=${HOMEDIR}/oper/wcoss2
cd $JOBDIR

# delete previous files
rm *.out *.err *.pbs

python submit_mlgefs_job_wcoss2.py -w $HOMEDIR
