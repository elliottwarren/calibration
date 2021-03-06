"""
Calibration for the LUMO ceilometers.

Code create block sets of calibration values based on a date range, which takes into account water vapour absorption.
The recommended calibration values to use are the daily modes. Saves yearly netCDF files of the outputs in L0 folder.
Based on the cumulostratus calibration method developed by Hopkin et al., in prep. Code designed mainly for CL31
and Lufft ceilometers but adapted here for use solely for LUMO ceilometers. Functions kept in the
LUMO_ceilometer_Utils.py script.

Data needed:
- L1 BSC files (UNSMOOTHED attenuated backscatter from ceilometers)
- Met Office NWP forecast files (water vapour correction: requiring, specific humidity, pressure and temperature)

Created by Elliott Warren Thurs 08/03/2018
Based heavily on CloudCal_filt_VaisTemp_LUMO.py by Emma Hopkin
"""

import sys
# append dir containing lcu utility library
sys.path.append('/home/micromet/Temp_Elliott/scripts/calibration')
# sys.path.append('C:/Users/Elliott/Documents/PhD Reading/LUMO - Sensor network/calibration/utils')

import LUMO_calibration_Utils as lcu

import os
import numpy as np
import datetime as dt

# ----------------------------
# Setup
# ----------------------------

# ceilometers to loop through (full ceilometer ID)
# site_ids = ['CL31-A_KSS45W']
site_ids = ['CL31-A_KSS45W', 'CL31-A_IMU', 'CL31-B_RGS', 'CL31-C_MR', 'CL31-D_NK', 'CL31-D_SWT', 'CL31-E_NK']

# years to loop through [list]
years = [2016, 2017, 2018]

# settings to tune calibration
ratio_filt = 0.05
maxB_filt = -10  #set high so that this filter is no longer used
cont_profs = 5  #number of continuous profiles required for calibration (must be odd no.)

# loop through site ids
for site_id in site_ids:

    # get site information from site_id
    ceil_id = site_id.split('_')[0]
    ceil_type = site_id.split('-')[0]
    site = site_id.split('_')[-1]

    # loop through years - create 1 netCDF file per year, per site
    for year in years:

        # create date range (daily resolution) to loop through
        # calibration values created at daily resolution
        start_date = dt.datetime(year, 1, 1)  # comparing my modes to EH modes
        end_date = dt.datetime(year, 12, 31)
        # start_date = dt.datetime(year, 1, 02)  # comparing my modes to EH modes
        # end_date = dt.datetime(year, 1, 12)
        date_range = lcu.date_range(start_date, end_date, 1, 'day')

        # create simple time range (just days) for use in saving to netCDF later
        time_deltas = [i - dt.datetime(year,1,01) for i in date_range]
        date_range_netcdf = np.array([i.days for i in time_deltas])

        # ----------------------------
        # Define variables
        # ----------------------------

        # NOT water corrected calibration
        profile_total = []  #array of total number of profiles used for calibration for each day
        peak_total = []     #array of number of profiles in the mode (from histogram)
        modes = []          #array of mode of S for each day
        means = []          #array of mean of S for each day
        medians = []        #array of median of S for each day
        sems = []           #array of standard error of S for each day
        stdevs = []         #array of standard deviation of S for each day
        C_modes = []
        C_medians = []
        C_stdevs = []
        CL_medians = []
        CL_stdevs = []

        # water corrected calibration
        modes_wv = []          #array of mode of S for each day
        means_wv = []          #array of mean of S for each day
        medians_wv = []        #array of median of S for each day
        sems_wv = []           #array of standard error of S for each day
        stdevs_wv = []         #array of standard deviation of S for each day
        C_modes_wv = []
        C_medians_wv = []
        C_stdevs_wv = []
        CL_medians_wv = []
        CL_stdevs_wv = []

        index_of_maxB = []  #index of max backscatter for each profile (includes all meteorological conditions)
        value_of_maxB = []  #value of max backscatter for each profile

        Profile_integrations = []       #integral of each profile (0.1-2.4km)

        window_tau = []     #instrument reported window transmission for each profile [%]
        window_tau_alert=[] #marker if window transmission falls below 90%
        pulse_energy = []   #intrument reported pulse energy for each profile [%]
        pulse_energy_alert = []#marker if pulse energy falls below 90%
        CBH = []            #instrument reported cloud base height [km] - no data => -999
        All_S = []          #apparent S for each profile
        S_box = []          #apparent S in arrays for box plot of each day

        WV_trans = []       #transmission correction by profile from MWR
        lengths = []
        daily_WV = []       #transmission correction by day from MWR
        daymean_modelWV = []#transmission correction by day from model
        All_modelWV = []    #transmission correction by profile from model

        profiles_in_row = []
        num_files_present = 0 # count how many BSC files were actually present in the year

        # loop through each day individually, create calibration coefficient and store in list variables

        for day in date_range:

            # 3 char DOY
            doy = day.strftime('%j')

            # state the date for each loop
            print 'processing day ' + str(day)

            # ----------------------------
            # Read in data
            # ----------------------------

            # find directory name for bsc data
            datadir_bsc = '/data/its-tier2/micromet/data/'+str(year)+'/London/L1/'+site+'/DAY/' + doy + '/'
            #datadir_bsc = 'C:/Users/Elliott/Documents/PhD Reading/LUMO - Sensor network/calibration/data/'+str(year)+\
            #              '/London/L1/'+day.strftime('%m')+'/'

            # Note: L0 BSC heights are corrected for height above ground
            #       L1 BSC heights are NOT corrected and are therefore just the range...
            bsc_filepath = datadir_bsc + ceil_id+'_BSC_'+site+'_'+day.strftime('%Y%j')+'_15sec.nc'
            # bsc_filepath = datadir_bsc + 'CL31-D_BSC_NK_'+day.strftime('%Y%j')+'_15sec.nc'

            # check if file exists
            if os.path.isfile(bsc_filepath) == True:

                # add 1 to show that a file was present
                num_files_present += 1

                # read in L1 unscmoothed backscatter data (do not correct for SNR)
                bsc_data, _ = lcu.netCDF_read_BSC(bsc_filepath, var_type='beta', SNRcorrect=False)

                # transpose the backscatter for EH functions
                bsc_data['backscatter'] = np.transpose(bsc_data['backscatter'])

                # create range in [km]
                bsc_data['range_km'] = bsc_data['range'] / 1000.0

                # ------------------------------
                # Apply scattering correction
                # ------------------------------

                # find the cloud based on the max backscatter return, and set the backscatter at all other heights to nan
                cloud_beta = lcu.find_cloud(bsc_data['backscatter'])

                # apply the multiple scattering correction for the backscatter that was not the cloud
                Scat_correct_b = lcu.scatter_correct_Vais(cloud_beta, bsc_data['range_km'])

                # apply the multiple scattering to correct the non-cloud backscatter,
                #    and merge the array with the cloud backscatter array
                beta_arr = lcu.corr_beta(Scat_correct_b, bsc_data['backscatter'])

                # ----------------------------------------------
                # Apply water vapour attenuation correction
                # ----------------------------------------------

                # get yesterday's time to get the right forecast file for the water vapour
                yest = day - dt.timedelta(days=1)

                # Get full file paths for the day and yesterday's (yest) MO data and which model the forecast came from
                yest_filepath, yest_mod = lcu.mo_create_filename(yest)
                day_filepath, day_mod = lcu.mo_create_filename(day)

                # if both day's data exist, apply water vapour correction, else set backscatter to nan
                if (os.path.exists(yest_filepath))  & (os.path.exists(day_filepath)):
                    # Calculate and apply transmissivity to multiple scattering, corrected backscatter data
                    transmission_wv = lcu.mo_read_calc_wv_transmission(yest_filepath, day_filepath, yest_mod, day_mod, day, bsc_data['range'], bsc_data['time'], bsc_data['backscatter'])
                    beta_arr_wv = beta_arr * (1.0 / np.transpose(transmission_wv))
                else:
                    beta_arr_wv = beta_arr * np.nan

                # ----------------------------------------------
                # Calculate calibration
                # ----------------------------------------------

                ## 1. Calculate lidar ratio (S) without water vapour correction

                # calculate S, including transmission correction (on non water vapour corrected profiles)
                S = lcu.lidar_ratio(beta_arr, bsc_data['range_km'])

                # Remove profiles unsuitable for calibration
                ## Apply S Filters
                Step1_S, profile_B_ratio = lcu.step1_filter(bsc_data['backscatter'], bsc_data['range_km'], maxB_filt, ratio_filt, S)  # aerosol ratio = 5%
                Step2_S = lcu.step2_Sfilt(Step1_S, 10, cont_profs)  # range in S = 10%
                # remove neg values caused by neg noise
                Step2_S[Step2_S < 0] = np.nan


                ## 2. Calculate S with water vapour correction

                # calculate lidar ratio for the water vapour corrected profiles
                S_wv = lcu.lidar_ratio(beta_arr_wv, bsc_data['range_km'])

                # filter out bad profiles, unsuitable for calibrations
                Step1_S_wv, profile_B_ratio_wv = lcu.step1_filter(bsc_data['backscatter'], bsc_data['range_km'], maxB_filt, ratio_filt, S_wv)  # aerosol ratio = 5%
                Step2_S_wv = lcu.step2_Sfilt(Step1_S_wv, 10, cont_profs)
                # remove neg values caused by neg noise
                Step2_S_wv[Step2_S_wv < 0] = np.nan

                # -----------------
                # Statistics
                # -----------------

                # Calculate mode and mean
                Cal_hist, no_of_profs = lcu.get_counts(Step2_S)  # Histogram of filtered S
                no_in_peak, day_mode, day_mean, day_median, day_sem, day_stdev, dayC_mode, dayC_median, dayC_stdev, dayCL_median, dayCL_stdev = lcu.S_mode_mean(
                Step2_S, Cal_hist)

                Cal_hist_wv, no_of_profs_wv = lcu.get_counts(Step2_S_wv)  # Histogram of filtered S
                no_in_peak_wv, day_mode_wv, day_mean_wv, day_median_wv, day_sem_wv, day_stdev_wv, dayC_mode_wv, dayC_median_wv, dayC_stdev_wv, dayCL_median_wv, dayCL_stdev_wv = lcu.S_mode_mean(
                Step2_S_wv, Cal_hist_wv)


                ## Append statistics for each

                All_S = np.concatenate((All_S, Step2_S))
                ###All_S2 = np.concatenate((All_S2, Step2_S2))
                # ~~~~
                S_forbox = np.array(Step2_S)
                S_forbox[np.isnan(S_forbox)] = 0
                S_forbox = S_forbox[np.nonzero(S_forbox)]
                if np.max(Cal_hist) > 10:
                    S_box.append(S_forbox)
                else:
                    S_box.append([0])

                profile_total.append(no_of_profs)
                peak_total.append(no_in_peak)
                modes.append(day_mode)
                means.append(day_mean)
                medians.append(day_median)
                sems.append(day_sem)
                stdevs.append(day_stdev)
                C_modes.append(dayC_mode)
                C_medians.append(dayC_median)
                C_stdevs.append(dayC_stdev)
                CL_medians.append(dayCL_median)
                CL_stdevs.append(dayCL_stdev)

                modes_wv.append(day_mode_wv)
                means_wv.append(day_mean_wv)
                medians_wv.append(day_median_wv)
                sems_wv.append(day_sem_wv)
                stdevs_wv.append(day_stdev_wv)
                C_modes_wv.append(dayC_mode_wv)
                C_medians_wv.append(dayC_median_wv)
                C_stdevs_wv.append(dayC_stdev_wv)
                CL_medians_wv.append(dayCL_median_wv)
                CL_stdevs_wv.append(dayCL_stdev_wv)

            # else if backscatter data is not available this day
            else:
                C_modes_wv.append(np.nan)
                C_medians_wv.append(np.nan)
                C_modes.append(np.nan)
                C_medians.append(np.nan)
                profile_total.append(np.nan)

        # if there is data to save
        if num_files_present > 0:
            # save the year's data as a netCDF file in the ANNUAL folder
            lcu.netCDF_save_calibration(C_modes_wv, C_medians_wv, C_modes, C_medians, profile_total, date_range_netcdf,
                                        site_id, site, year)



# # quick compare of the old calibrated data and the ones made by this script
# import matplotlib.pyplot as plt
# plt.figure()
# plt.plot_date(c_wv_old_kss45w['dates'][:20], c_wv_old_kss45w['c_wv'][:20], label='old modes (EH)')
# plt.plot_date(date_range, C_modes_wv, label='new modes (EW)')
# plt.plot_date(date_range, C_medians, label='new median no wv')
# plt.plot_date(date_range, C_medians_wv, label='new med')
# plt.plot_date(date_range, C_stdevs_wv, label='new stdev')
# plt.legend()


# date_range[4]
# C_modes_wv[4]
#vs
# A_KSS45W.Dates[1410]
# A_KSS45W.C_modes_wv[1410]























print 'END PROGRAM'
