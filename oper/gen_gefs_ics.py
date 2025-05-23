'''
Description: This script gets ensemble GEFS members for GraphCast initialization
@uthor: Sadegh Sadeghi Tabas (sadegh.tabas@noaa.gov)
Revision history: Sadegh Tabas, initial code
                  4/29/2025, Linlin Cui, enable two AWS buckets, the input files are on noaa-ncepdev-none-ca-ufs-cpldcld

'''
import os
import sys
from time import time
import glob
import argparse
import subprocess
from datetime import datetime, timedelta
import re
import boto3
import xarray as xr
import numpy as np
from botocore.config import Config
from botocore import UNSIGNED
import pygrib
import requests
from bs4 import BeautifulSoup


class GFSDataProcessor:
    def __init__(self, start_datetime, end_datetime, member, num_pressure_levels=13, output_directory=None, download_directory=None, keep_downloaded_data=True, aws=None):
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.num_levels = num_pressure_levels
        self.output_directory = output_directory
        self.download_directory = download_directory
        self.keep_downloaded_data = keep_downloaded_data
        self.member = member

        #self.s3 = boto3.client('s3')
        profile_name = os.environ.get('AWS_PROFILE', 'default')
        session = boto3.Session(profile_name=profile_name)
        current_credentials = session.get_credentials().get_frozen_credentials()
        self.s3 = session.client(
            's3',
            aws_access_key_id=current_credentials.access_key,
            aws_secret_access_key=current_credentials.secret_key,
        )
    
        # Specify the S3 bucket name and root directory
        self.bucket_name = 'noaa-ncepdev-none-ca-ufs-cpldcld'
        
        self.root_directory = 'gefs'

        # Specify the local directory where you want to save the files
        if self.download_directory is None:
            self.local_base_directory = os.path.join(os.getcwd(), self.bucket_name+'_'+str(self.num_levels)+'_'+str(self.member))  # Use current directory if not specified
        else:
            self.local_base_directory = os.path.join(self.download_directory, self.bucket_name+'_'+str(self.num_levels)+'_'+str(self.member))

        # List of file formats to download
        if self.num_levels == 13:     
            self.file_formats = ['pgrb2.0p25.f000', 'pgrb2s.0p25.f000'] # , '0p25.f001'
        else:
            self.file_formats = ['pgrb2.0p25.f000', 'pgrb2b.0p25.f000', 'pgrb2.0p25.f006'] # , '0p25.f001'
    
    def s3bucket(self, date_str, time_str, local_directory):
        # Construct the S3 prefix for the directory
        s3_prefix = f"Linlin.Cui/gefs_wcoss2/{self.root_directory}.{date_str}/{time_str}/atmos/"

        def get_data(s3_prefix, file_format, local_directory):
            # List objects in the S3 directory
            s3_objects = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=s3_prefix)
            for obj in s3_objects.get('Contents', []):
                obj_key = obj['Key']
                if obj_key.endswith(f'{file_format}'):

                    # Define the local file path
                    local_file_path = os.path.join(local_directory, os.path.basename(obj_key))

                    # Download the file from S3 to the local path
                    self.s3.download_file(self.bucket_name, obj_key, local_file_path)
                    print(f"Downloaded {obj_key} to {local_file_path}")

                 
        for file_format in self.file_formats:
            curr_file = f"ge{self.member}.t{time_str}z.{file_format}"
            get_data(s3_prefix, curr_file, local_directory)
        
    def download_data(self):
        # Calculate the number of 6-hour intervals
        delta = (self.end_datetime - self.start_datetime)
        total_intervals = int(delta.total_seconds() / 3600 / 6)  # 6 hours per interval

        # Loop through the 6-hour intervals
        current_datetime = self.start_datetime
        while current_datetime <= self.end_datetime:
            date_str = current_datetime.strftime("%Y%m%d")
            time_str = current_datetime.strftime("%H")
            
            # Define the local directory path where the file will be saved
            local_directory = os.path.join(self.local_base_directory, date_str, time_str)

            # Create the local directory if it doesn't exist
            os.makedirs(local_directory, exist_ok=True)
            
            
            self.s3bucket(date_str, time_str, local_directory)
                
            

            # Move to the next 6-hour interval
            current_datetime += timedelta(hours=6)

        print("Download completed.")

    def process_data_with_wgrib2(self):
        # Define the directory where your GRIB2 files are located
        data_directory = self.local_base_directory

        # Create a dictionary to specify the variables, levels, and whether to extract only the first time step (if needed)
        variables_to_extract = {
            '.pgrb2s.0p25.f000': {
                ':HGT:': {
                    'levels': [':surface:'],
                    'first_time_step_only': True,  # Extract only the first time step
                },
                ':TMP:': {
                    'levels': [':2 m above ground:'],
                },
                ':PRMSL:': {
                    'levels': [':mean sea level:'],
                },
                ':VGRD|UGRD:': {
                    'levels': [':10 m above ground:'],
                },
            },
            '.pgrb2.0p25.f000': {
                ':LAND:': {
                    'levels': [':surface:'],
                    'first_time_step_only': True,  # Extract only the first time step
                },
                ':SPFH|VVEL|VGRD|UGRD|HGT|TMP:': {
                    'levels': [':(50|100|150|200|250|300|400|500|600|700|850|925|1000) mb:'],
                },
            }
        }
        if self.num_levels == 37:
            variables_to_extract['.pgrb2.0p25.f000'][':SPFH|VVEL|VGRD|UGRD|HGT|TMP:']['levels'] = [':(1|2|3|5|7|10|20|30|50|70|100|150|200|250|300|350|400|450|500|550|600|650|700|750|800|850|900|925|950|975|1000) mb:']
            variables_to_extract['.pgrb2b.0p25.f000'] = {}
            variables_to_extract['.pgrb2b.0p25.f000'][':SPFH|VVEL|VGRD|UGRD|HGT|TMP:'] = {}
            variables_to_extract['.pgrb2b.0p25.f000'][':SPFH|VVEL|VGRD|UGRD|HGT|TMP:']['levels'] = [':(125|175|225|775|825|875) mb:']
       
        # Create an empty list to store the extracted datasets
        extracted_datasets = []
        files = []
        print("Start extracting variables and associated levels from grib2 files:")
        # Loop through each folder (e.g., gdas.yyyymmdd)
        date_folders = sorted(next(os.walk(data_directory))[1])
        for date_folder in date_folders:
            date_folder_path = os.path.join(data_directory, date_folder)

            # Loop through each hour (e.g., '00', '06', '12', '18')
            for hour in ['00', '06', '12', '18']:
                subfolder_path = os.path.join(date_folder_path, hour)

                # Check if the subfolder exists before processing
                if os.path.exists(subfolder_path):
                    # Loop through each GRIB2 file (.f000, .f001, .f006)
                    for file_extension, variable_data in variables_to_extract.items():
                        for variable, data in variable_data.items():
                            levels = data['levels']
                            first_time_step_only = data.get('first_time_step_only', False)  # Default to False if not specified

                            pattern = os.path.join(subfolder_path, f'ge{self.member}.t*z{file_extension}')
                            # Use glob to search for files matching the pattern
                            matching_files = glob.glob(pattern)
                            
                            # Check if there's exactly one matching file
                            if len(matching_files) == 1:
                                grib2_file = matching_files[0]
                                print("Found file:", grib2_file)
                            else:
                                print("Error: Found multiple or no matching files.")
                                
                            # Extract the specified variables with levels from the GRIB2 file
                            for level in levels:
                                output_file = os.path.join(self.download_directory,f'{variable}_{level}_{date_folder}_{hour}{file_extension}_{self.num_levels}_{self.member}.nc')
                                files.append(output_file)
                                
                                # Extracting levels using regular expression
                                matches = re.findall(r'\d+', level)
                                
                                # Convert the extracted matches to integers
                                curr_levels = [int(match) for match in matches]
                                
                                # Get the number of levels
                                number_of_levels = len(curr_levels)
                                
                                # Use wgrib2 to extract the variable with level
                                wgrib2_command = ['wgrib2', '-nc_nlev', f'{number_of_levels}', grib2_file, '-match', f'{variable}', '-match', f'{level}', '-netcdf', output_file]
                                subprocess.run(wgrib2_command, check=True)

                                # Open the extracted netcdf file as an xarray dataset
                                ds = xr.open_dataset(output_file)

                                # if variable == '^(597):':
                                #    ds['time'] = ds['time'] - np.timedelta64(6, 'h')

                                # If specified, extract only the first time step
                                if variable not in [':LAND:', ':HGT:']:
                                    extracted_datasets.append(ds)
                                else:
                                    if first_time_step_only:
                                        # Append the dataset to the list
                                        ds = ds.isel(time=0)
                                        extracted_datasets.append(ds)
                                        variables_to_extract[file_extension][variable]['first_time_step_only'] = False
                                
                                # Optionally, remove the intermediate GRIB2 file
                                # os.remove(output_file)
        print("Merging grib2 files:")
        ds = xr.merge(extracted_datasets)
        
        print("Merging process completed.")
        
        print("Processing, Renaming and Reshaping the data")
        # Drop the 'level' dimension
        ds = ds.drop_dims('level')

        # Rename variables and dimensions
        ds = ds.rename({
            'latitude': 'lat',
            'longitude': 'lon',
            'plevel': 'level',
            'HGT_surface': 'geopotential_at_surface',
            'LAND_surface': 'land_sea_mask',
            'PRMSL_meansealevel': 'mean_sea_level_pressure',
            'TMP_2maboveground': '2m_temperature',
            'UGRD_10maboveground': '10m_u_component_of_wind',
            'VGRD_10maboveground': '10m_v_component_of_wind',
            #'APCP_surface': 'total_precipitation_6hr',
            'HGT': 'geopotential',
            'TMP': 'temperature',
            'SPFH': 'specific_humidity',
            'VVEL': 'vertical_velocity',
            'UGRD': 'u_component_of_wind',
            'VGRD': 'v_component_of_wind'
        })

        # Assign 'datetime' as coordinates
        ds = ds.assign_coords(datetime=ds.time)
        
        # Convert data types
        ds['lat'] = ds['lat'].astype('float32')
        ds['lon'] = ds['lon'].astype('float32')
        ds['level'] = ds['level'].astype('int32')

        # Adjust time values relative to the first time step
        ds['time'] = ds['time'] - ds.time[0]

        # Expand dimensions
        ds = ds.expand_dims(dim='batch')
        ds['datetime'] = ds['datetime'].expand_dims(dim='batch')

        # Squeeze dimensions
        ds['geopotential_at_surface'] = ds['geopotential_at_surface'].squeeze('batch')
        ds['land_sea_mask'] = ds['land_sea_mask'].squeeze('batch')

        # Update geopotential unit to m2/s2 by multiplying 9.80665
        ds['geopotential_at_surface'] = ds['geopotential_at_surface'] * 9.80665
        ds['geopotential'] = ds['geopotential'] * 9.80665

        # Update total_precipitation_6hr unit to (m) from (kg/m^2) by dividing it by 1000kg/m³
        # ds['total_precipitation_6hr'] = ds['total_precipitation_6hr'] / 1000
        # add total precip with 0 values (does not impact the forecasts for 13 PLs)
        other_dims = ['batch', 'time', 'lat', 'lon']
        # Create an array filled with zeros for other dimensions
        zeros_shape = tuple(ds.sizes[dim] for dim in other_dims)
        zeros_array = np.zeros(zeros_shape, dtype=np.float32)

        # Add the zeros array as a new variable in the dataset
        ds['total_precipitation_6hr'] = (other_dims, zeros_array)
        
        # Define the output NetCDF file
        date = (self.start_datetime + timedelta(hours=6)).strftime('%Y%m%d%H')
        steps = str(len(ds['time']))

        if self.output_directory is None:
            self.output_directory = os.getcwd()  # Use current directory if not specified
        output_netcdf = os.path.join(self.output_directory, f"source-ge{self.member}_date-{date}_res-0.25_levels-{self.num_levels}_steps-{steps}.nc")

        # Save the merged dataset as a NetCDF file
        ds.to_netcdf(output_netcdf)
        print(f"Saved output to {output_netcdf}")
        for file in files:
            os.remove(file)
            
        # Optionally, remove downloaded data
        if not self.keep_downloaded_data:
            self.remove_downloaded_data()

        print(f"Process completed successfully, your inputs for GraphCast model generated at:\n {output_netcdf}")

    def process_data_with_pygrib(self):
        # Define the directory where your GRIB2 files are located
        data_directory = self.local_base_directory

        #Get time-varying variables
        variables_to_extract = {
            '.pgrb2.0p25.f000': {
                '2t': {
                    'typeOfLevel': 'heightAboveGround',
                    'level': 2,
                },
                'prmsl': {
                    'typeOfLevel': 'meanSea',
                    'level': 0,
                },
                '10u, 10v': {
                    'typeOfLevel': 'heightAboveGround',
                    'level': 10,
                },
                'w, u, v, q, t, gh': {
                    'typeOfLevel': 'isobaricInhPa',
                    'level': [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000],
                },
            },
            '.pgrb2.0p25.f006': {
                'tp': {  # total precipitation 
                    'typeOfLevel': 'surface',
                    'level': 0,
                },
            }
        }

        if self.num_levels == 37:
            variables_to_extract['.pgrb2.0p25.f000']['w, u, v, q, t, gh']['level'] = [
                1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 
                100, 150, 200, 250, 300, 350, 400,
                450, 500, 550, 600, 650, 700, 750,
                800, 850, 900, 925, 950, 975, 1000,
            ]
            extra_levels = [125, 175, 225, 775, 825, 875]
            file_extension_2b = '.pgrb2b.0p25.f000'

        # Create an empty list to store the extracted datasets
        mergeDSs = []
        print("Start extracting variables and associated levels from grib2 files:")
        # Loop through each folder (e.g., gdas.yyyymmdd)
        date_folders = sorted(next(os.walk(data_directory))[1])
        for date_folder in date_folders:
            date_folder_path = os.path.join(data_directory, date_folder)

            # Loop through each hour (e.g., '00', '06', '12', '18')
            for hour in ['00', '06', '12', '18']:
                subfolder_path = os.path.join(date_folder_path, hour)

                # Check if the subfolder exists before processing
                if os.path.exists(subfolder_path):

                    mergeDAs = []

                    for file_extension, variables in variables_to_extract.items():
                        pattern = os.path.join(subfolder_path, f'gdas.t*z{file_extension}')
                        # Use glob to search for files matching the pattern
                        matching_files = glob.glob(pattern)
                        
                        # Check if there's exactly one matching file
                        if len(matching_files) == 1:
                            fname = matching_files[0]
                            print("Found file:", fname)
                        else:
                            print("Error: Found multiple or no matching files.")

                        #open grib file
                        grbs = pygrib.open(fname)

                        for key, value in variables.items():

                            variable_names = key.split(', ')
                            levelType = value['typeOfLevel']
                            desired_level = value['level']
                    
                            for var_name in variable_names:

                                print(f'Get variable {var_name} from file {fname}:')
                                da = self.get_dataarray(grbs, var_name, levelType, desired_level)

                                #extract variables from pgrb2b
                                if (levelType == 'isobaricInhPa') & (self.num_levels == 37):
                                    fname2b = os.path.join(subfolder_path, f'gdas.t{hour}z{file_extension_2b}')
                                    grbs2b = pygrib.open(fname2b)
                                    da_extra = self.get_dataarray(grbs2b, var_name, levelType, extra_levels)
                                    da_combined = da.combine_first(da_extra) 
                                    mergeDAs.append(da_combined)
                                else:
                                    mergeDAs.append(da)

                    ds = xr.merge(mergeDAs)

                    mergeDSs.append(ds)
                    ds.close()

        #Concatenate ds
        ds = xr.concat(mergeDSs, dim='time')

        #Get 2D static variables
        grbfiles = glob.glob(f'{data_directory}/*/*/*.f000')
        grbfiles.sort()
        #Get lsm/orog from the first file
        grbs = pygrib.open(grbfiles[0])
        levelType = 'surface'
        desired_level = 0
        for var_name in ['lsm', 'orog']:
            da = self.get_dataarray(grbs, var_name, levelType, desired_level)
            ds = xr.merge([ds, da])

        ds = ds.rename({
            'lsm': 'land_sea_mask',
            'orog': 'geopotential_at_surface',
            'prmsl': 'mean_sea_level_pressure',
            '2t': '2m_temperature',
            '10u': '10m_u_component_of_wind',
            '10v': '10m_v_component_of_wind',
            'tp': 'total_precipitation_6hr',
            'gh': 'geopotential',
            't': 'temperature',
            'q': 'specific_humidity',
            'w': 'vertical_velocity',
            'u': 'u_component_of_wind',
            'v': 'v_component_of_wind'
        })

        ds = ds.assign_coords(datetime=ds.time)

        # Adjust time values relative to the first time step
        ds['time'] = ds['time'] - ds.time[0]

        # Expand dimensions
        ds = ds.expand_dims(dim='batch')
        ds['datetime'] = ds['datetime'].expand_dims(dim='batch')

        # Squeeze dimensions
        ds['geopotential_at_surface'] = ds['geopotential_at_surface'].squeeze('batch')
        ds['land_sea_mask'] = ds['land_sea_mask'].squeeze('batch')

        # Update geopotential unit to m2/s2 by multiplying 9.80665
        ds['geopotential_at_surface'] = ds['geopotential_at_surface'] * 9.80665
        ds['geopotential'] = ds['geopotential'] * 9.80665

        # Update total_precipitation_6hr unit to (m) from (kg/m^2) by dividing it by 1000kg/m³
        ds['total_precipitation_6hr'] = ds['total_precipitation_6hr'] / 1000

        # Define the output NetCDF file
        date = (self.start_datetime + timedelta(hours=6)).strftime('%Y%m%d%H')
        steps = str(len(ds['time']))

        if self.output_directory is None:
            self.output_directory = os.getcwd()  # Use current directory if not specified
        output_netcdf = os.path.join(self.output_directory, f"source-gdas_date-{date}_res-0.25_levels-{self.num_levels}_steps-{steps}.nc")

        #final_dataset = ds.assign_coords(datetime=ds.time)
        ds.to_netcdf(output_netcdf)
        ds.close()
        
        # Optionally, remove downloaded data
        if not self.keep_downloaded_data:
            self.remove_downloaded_data()

        print(f"Process completed successfully, your inputs for GraphCast model generated at:\n {output_netcdf}")
            
    def remove_downloaded_data(self):
        # Remove downloaded data from the specified directory
        print("Removing downloaded grib2 data...")
        try:
            os.system(f"rm -rf {self.local_base_directory}")
            print("Downloaded data removed.")
        except Exception as e:
            print(f"Error removing downloaded data: {str(e)}")

    def get_dataarray(self, grbfile, var_name, level_type, desired_level):

        # Find the matching grib message
        variable_message = grbfile.select(shortName=var_name, typeOfLevel=level_type, level=desired_level)
    
        # create a netcdf dataset using the matching grib message
        lats, lons = variable_message[0].latlons()
        lats = lats[:,0]
        lons = lons[0,:]
    
        #check latitude range
        reverse_lat = False
        if lats[0] > 0:
            reverse_lat = True
            lats = lats[::-1]
    
        steps = variable_message[0].validDate
        if var_name=='tp':
            steps = steps + timedelta(hours=6)
        #precipitation rate has two stepType ('instant', 'avg'), use 'instant')
        if len(variable_message) > 2:
            data = []
            for message in variable_message:
                data.append(message.values)
            data = np.array(data)
            if reverse_lat:
                data = data[:, ::-1, :]
        else:
            data = variable_message[0].values
            if reverse_lat:
                data = data[::-1, :]
    
        if len(data.shape) == 2:
            da = xr.Dataset(
                data_vars={
                    var_name: (['lat', 'lon'], data.astype('float32'))
                },
                coords={
                    'lon': lons.astype('float32'),
                    'lat': lats.astype('float32'),
                    'time': steps,  
                }
            )
        elif len(data.shape) == 3:
            da = xr.Dataset(
                data_vars={
                    var_name: (['level', 'lat', 'lon'], data.astype('float32'))
                },
                coords={
                    'lon': lons.astype('float32'),
                    'lat': lats.astype('float32'),
                    'level': np.array(desired_level).astype('int32'),
                    'time': steps,  
                }
            )
    
        return da

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and process GEFS data")
    parser.add_argument("start_datetime", help="Start datetime in the format 'YYYYMMDDHH'")
    parser.add_argument("end_datetime", help="End datetime in the format 'YYYYMMDDHH'")
    parser.add_argument("member", help="GEFS member options: [c00, p01, ..., p30]")
    parser.add_argument("-l", "--levels", help="number of pressure levels, options: 13, 37", default="13")
    parser.add_argument("-m", "--method", help="method to extract variables from grib2, options: wgrib2, pygrib", default="wgrib2")
    parser.add_argument("-o", "--output", help="Output directory for processed data")
    parser.add_argument("-d", "--download", help="Download directory for raw data")
    parser.add_argument("-k", "--keep", help="Keep downloaded data (yes or no)", default="no")

    args = parser.parse_args()

    start_datetime = datetime.strptime(args.start_datetime, "%Y%m%d%H")
    end_datetime = datetime.strptime(args.end_datetime, "%Y%m%d%H")
    member = args.member
    num_pressure_levels = int(args.levels)
    method = args.method
    output_directory = args.output
    download_directory = args.download
    keep_downloaded_data = args.keep.lower() == "yes"
    
    data_processor = GFSDataProcessor(start_datetime, end_datetime, member, num_pressure_levels, output_directory, download_directory, keep_downloaded_data)
    data_processor.download_data()
    
    if method == "wgrib2":
      data_processor.process_data_with_wgrib2()
    elif method == "pygrib":
      data_processor.process_data_with_pygrib()
    else:
      raise NotImplementedError(f"Method {method} is not supported!")
