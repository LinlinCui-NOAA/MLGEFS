""" Utility for converting netcdf data to grib2 with grib2io.

    History:
        06/04/2025: Linlin Cui (linlin.cui@noaa.gov), added support for grib2io
"""

import os
from time import time
import json
import multiprocessing as mp

import xarray as xr
import grib2io
import numpy as np
import pandas as pd
import pygrib


class Netcdf2Grib:
    def __init__(self, table_file):

        with open(table_file, 'r') as f:
            self.attrs = json.load(f)

    def save_grib2(self, start_datetime, xarray_ds, gefs_member, outdir):

        xarray_ds['geopotential'] = xarray_ds['geopotential'] / 9.80665

        if 'total_precipitation_6hr' in xarray_ds:
            xarray_ds['total_precipitation_6hr'] = xarray_ds['total_precipitation_6hr'] * 1000
        xarray_ds['total_precipitation_cumsum'] = xarray_ds['total_precipitation_6hr'].cumsum(axis=0)

        xarray_ds['level'] = xarray_ds['level'] * 100
        xarray_ds = xarray_ds.squeeze(dim='batch')

        nt = int(xarray_ds.time.shape[0])
        for index, time_index in enumerate(np.arange(nt)):
            da = xarray_ds.isel(time=time_index)

            cycle = start_datetime.hour
            outfile = os.path.join(outdir, f'pmlgefs{gefs_member}.t{cycle:02d}z.pgrb2.0p25.f{(time_index+1)*6:03d}')

            #delelte the old file
            if os.path.isfile(outfile):
                os.remove(outfile)

            values = da.values
            current_date = start_datetime + da.time.values


            for var in self.attrs:
                var0 = var
                if 'plevel' in var:
                    var = '_'.join(var.split('_')[:-2])
                    level = int(var0.split('_')[-1])
                    da_selected = da[var].sel(level=level)
                else:

                    da_selected = da[var]
            
                da_selected.attrs = {
                    'GRIB2IO_section0': np.array([1196575042, 0, 0, 2, 733060]),
                    'GRIB2IO_section1': np.array([7, 0, 2, 1, 1, current_date.year, current_date.month, current_date.day, current_date.hour, 0, 0, 0, 1]),
                    'GRIB2IO_section2': [],
                    'GRIB2IO_section3': np.array([0, 1038240, 0, 0, 0, 6, 0, 0, 0, 0, 0, 0, 1440, 721, 0, -1, 90000000, 0, 48, -90000000, 359750000,250000, 250000, 0]),
                    'GRIB2IO_section4': np.array(self.attrs[var0]['GRIB2IO_section4']),
                    'GRIB2IO_section5': np.array(self.attrs[var0]['GRIB2IO_section5']),
                    'fullName': self.attrs[var0]['fullName'],
                    'shortName': self.attrs[var0]['shortName'],
                    'units': self.attrs[var0]['units']
                }

                da_selected.grib2io.to_grib2(outfile, mode='a')

if __name__ == "__main__":
    
    table_file = 'tables.json'
    
    startdate = pd.to_datetime('2024-04-01 00:00:00')
    ds = xr.open_dataset('forecasts_levels-13_steps-64.nc')

    t0 = time()
    outdir = './forecasts_levels-13_c00'
    member = 'c00'
    converter = Netcdf2Grib(table_file)
    converter.save_grib2(startdate, ds, member, outdir)

    print(f'It took {(time()-t0)/60} mins')
