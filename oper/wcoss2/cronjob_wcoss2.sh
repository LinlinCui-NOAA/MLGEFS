#!/bin/bash --login

cd /lfs/h2/emc/nems/noscrub/linlin.cui/Tests/eagle_ensemble

module load intel/19.1.3.304 
module use /apps/dev/lmodules/intel/19.1.3.304
module load libjpeg/9c
module load ve/eagle/1.0
module load awscli/2.7.35

# delete previous files
rm *.out *.err *.pbs

aws s3 --profile gcgfs sync s3://noaa-nws-graphcastgfs-pds/hurricanes/syndat tracker/syndat --no-sign-request

python submit_mlgefs_job.py
