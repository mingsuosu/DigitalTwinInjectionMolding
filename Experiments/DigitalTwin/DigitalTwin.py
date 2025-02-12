# -*- coding: utf-8 -*-
"""
Created on Mon Oct 10 14:00:40 2022

@author: LocalAdmin
"""
import multiprocessing
from multiprocessing import Process, freeze_support

from threading import Thread
from pathlib import Path
import sys
import h5py
import tkinter as tk

path_dim = Path.cwd().parents[1]
sys.path.insert(0,path_dim.as_posix())


# import DigitalTwinFunctions as dtf
import time
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pickle as pkl
import numpy as np

from DIM.models.models import Static_MLP
from DIM.optim.param_optim import ParamOptimizer
from DIM.arburg470 import dt_functions as dtf


# %% User specified parameters
# rec_path = Path('C:/Users/rehmer/Desktop/DIM_09_11/setpoint_recording.pkl')
# dm_path = Path('C:/Users/rehmer/Desktop/DIM_09_11/dm_updated.pkl')
# source_live_h5 = Path('I:/Klute/DIM_Twin/DIM_20221109.h5')
# model_path = Path('C:/Users/rehmer/Desktop/DIM_09_11/models_Twkz/live_models.pkl')

rec_path = Path('/home/alexander/Desktop/DIM/setpoint_recording.pkl')
dm_path = Path('/home/alexander/Desktop/DIM/dm_updated.pkl')
source_live_h5 = Path('/home/alexander/Desktop/DIM/DIM_20221108.h5')
model_path = Path('/home/alexander/Desktop/DIM/models_Twkz/live_models.pkl')


# %%  Load DataManager specifically for this machine
# source_h5 = Path('I:/Klute/DIM_Twin/DIM_20221104.h5')
# target_h5 = Path('C:/Users/rehmer/Desktop/DIM_09_11/dm_Twkz.h5')

source_h5 = Path('/home/alexander/Desktop/DIM/DIM_20221104.h5')
target_h5 = Path('/home/alexander/Desktop/DIM/dm_Twkz.h5')

setpoints = ['v_inj_soll','V_um_soll','T_wkz_soll']
dm = dtf.config_data_manager(source_h5,target_h5,setpoints)
dm.get_cycle_data()

# %% Ändere Quelldatei für Live-Betrieb
dm.source_hdf5 = source_live_h5
# %% Load model bank
mb = dtf.model_bank(model_path=model_path)
y_label = mb.models[0].y_label[0]

# %% Initialize DataFrame for recording applied setpoints
rec = pd.DataFrame(data=None,columns=dm.setpoints+[y_label])


# %% Fonts for plots
font = {'weight' : 'normal',
        'size'   : 12}

matplotlib.rc('font', **font)
     
# %% Main program
    
if __name__ == '__main__':
    
    # dm.get_cycle_data()
    
    freeze_support()

    plt.close('all')
    
    MQPlot = dtf.ModelQualityPlot()
    SQPlot = dtf.SolutionQualityPlot()
    PPlot = dtf.PredictionPlot() 
    OSPlot = dtf.OptimSetpointsPlot(num_sol=10)
    
    # Slider Setup
    master = tk.Tk()
    slider_val = tk.DoubleVar()
    slider = tk.Scale(master, from_=8.0, to=8.5,length=500,width=50,
                  orient='vertical',digits=3,label='Durchmesser_innen',
                  resolution=0.05, tickinterval=0.1,variable=slider_val)
    slider.pack()
    
    
    # master.attributes("-topmost", True)
    # master.focus_force()
    
    while True:
        # Save an updated version of the data manager object
        pkl.dump(dm,open(dm_path,'wb'))
        
        # Check for new data
        new_data = dm.get_cycle_data(delay=0.0,num_cyc=1)
        
        
        # Read target quality value from slider
        master.lift()
        master.update_idletasks()
        master.update()
        # print(slider_val.get())
        # new_val = slider.get()
        
        new_val = 8.15
        new_data = True
        
        if new_data:
            
            # Save applied setpoints and target quality value
            modelling_data = pd.read_hdf(dm.target_hdf5,'modelling_data')
            idx_new = max(modelling_data.index)
            stp = modelling_data.loc[[idx_new],dm.setpoints]
            stp[y_label] = new_val
            
            rec = pd.concat([rec,stp])
            pkl.dump(rec,open(rec_path,'wb'))
            
            
            # Reload models
            mb.load_models()
                        
            # Predict new quality datum
            dtf.predict_quality(dm,mb)

            MQPlot.update(mb.stp_bfr[mb.idx_best])
            PPlot.update(dm,mb)
            master.lift()
            plt.pause(0.01)
                        
            Q_target =  pd.DataFrame.from_dict({y_label: [new_val]})
            
            # calculate optimal setpoints
            opti_setpoints = dtf.optimize_setpoints(dm,mb,Q_target,[])
            
            # Plot 
            # SQPlot.update(opti_setpoints.loc[0,'loss'])
            if opti_setpoints is not None:
                OSPlot.update(opti_setpoints[dm.setpoints+['loss']],stp)
                
            plt.pause(0.01)
            master.lift()
        else:
            
            print('Waiting for new data')
            
            time.sleep(1)
            




    
#     p_read.join(0)
    
    # data_manager.get_cycle_data()

# 1. Read Data continuosly, give signal if new data available

# 2. Predict new quality datum by multiple models, return best prediction

# 3. Estimate optimal setpoint given best model, if model is even accurate 