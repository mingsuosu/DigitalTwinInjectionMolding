#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 24 13:25:16 2020

@author: alexander
"""

from sys import path
path.append(r"C:\Users\LocalAdmin\Documents\casadi-windows-py38-v3.5.5-64bit")

import os

import casadi as cs
import matplotlib.pyplot as plt
import numpy as np
import math
import pandas as pd
import pickle as pkl

from DIM.optim.DiscreteBoundedPSO import DiscreteBoundedPSO
from .common import OptimValues_to_dict,BestFitRate

# Import sphere function as objective function
#from pyswarms.utils.functions.single_obj import sphere as f

# Import backend modules
# import pyswarms.backend as P
# from pyswarms.backend.topology import Star
# from pyswarms.discrete.binary import BinaryPSO

# Some more magic so that the notebook will reload external python modules;
# see http://stackoverflow.com/questions/1907993/autoreload-of-modules-in-ipython


# from miscellaneous import *


# def SimulateModel(model,x,u,params=None):
#     # Casadi Function needs list of parameters as input
#     if params==None:
#         params = model.Parameters
    
#     params_new = []
        
#     for name in  model.Function.name_in():
#         try:
#             params_new.append(params[name])                      # Parameters are already in the right order as expected by Casadi Function
#         except:
#             continue
    
#     x_new = model.Function(x,u,*params_new)     
                          
#     return x_new

def ControlInput(ref_trajectories,opti_vars,k):
    """
    Übersetzt durch Maschinenparameter parametrierte
    Führungsgrößenverläufe in optimierbare control inputs
    """
    
    control = []
            
    for key in ref_trajectories.keys():
        control.append(ref_trajectories[key](opti_vars,k))
    
    control = cs.vcat(control)

    return control   
    
def CreateOptimVariables(opti, Parameters):
    """
    Defines all parameters, which are part of the optimization problem, as 
    opti variables with appropriate dimensions
    """
    
    # Create empty dictionary
    opti_vars = {}
    
    for param in Parameters.keys():
        dim0 = Parameters[param].shape[0]
        dim1 = Parameters[param].shape[1]
        
        opti_vars[param] = opti.variable(dim0,dim1)
    
    return opti_vars


def ModelTraining(model,data,initializations=10, BFR=False, 
                  p_opts=None, s_opts=None):
    
   
    results = [] 
    
    for i in range(0,initializations):
        
        # initialize model to make sure given initial parameters are assigned
        model.ParameterInitialization()
        
        # Estimate Parameters on training data
        new_params = ModelParameterEstimation(model,data,p_opts,s_opts)
        
        # Assign estimated parameters to model
        model.AssignParameters(new_params)
        
        # Evaluate on Validation data
        u_val = data['u_val']
        y_ref_val = data['y_val']
        init_state_val = data['init_state_val']

        # Evaluate estimated model on validation data        
        e_val = 0
        
        for j in range(0,len(u_val)):   
            # Simulate Model
            pred = model.Simulation(init_state_val[j],u_val[j])
            
            if isinstance(pred, tuple):
                pred = pred[1]

            # Calculate simulation error            
            # Check for the case, where only last value is available
            if y_ref_val[j].shape[0]==1:
                e_val = e_val + cs.sumsqr(y_ref_val[j] - pred[-1,:])
            else:
                e = e + cs.sumsqr(y_ref_val[i] - pred)

        
        # Calculate mean error over all validation batches
        e_val = e_val / len(u_val)
        e_val = float(np.array(e_val))
        
        print('Validation error: '+str(e_val))
        
        # # Evaluate estimated model on test data
        
        # u_test = data['u_test']
        # y_ref_test = data['y_test']
        # init_state_test = data['init_state_test']
            
        # pred = model.Simulation(init_state_test[0],u_test[0])
        
        # if isinstance(pred, tuple):
        #     pred = pred[1]
        
        # y_est = np.array(pred)
        
        # BFR = BestFitRate(y_ref_test[0],y_est)
        
        # # save parameters and performance in list
        # results.append([e_val,BFR,model.name,i,model.Parameters])
        results.append([e_val,model.name,i,model.Parameters])
         
    # results = pd.DataFrame(data = results, columns = ['loss_val','BFR_test',
    #                     'model','initialization','params'])
    
    results = pd.DataFrame(data = results, columns = ['loss_val',
                        'model','initialization','params'])
    return results 

def HyperParameterPSO(model,data,param_bounds,n_particles,options,
                      initializations=10,p_opts=None,s_opts=None):
    """
    Binary PSO for optimization of Hyper Parameters such as number of layers, 
    number of neurons in hidden layer, dimension of state, etc

    Parameters
    ----------
    model : model
        A model whose hyperparameters to be optimized are attributes of this
        object and whose model equations are implemented as a casadi function.
    data : dict
        A dictionary with training and validation data, see ModelTraining()
        for more information
    param_bounds : dict
        A dictionary with structure {'name_of_attribute': [lower_bound,upper_bound]}
    n_particles : int
        Number of particles to use
    options : dict
        options for the PSO, see documentation of toolbox.
    initializations : int, optional
        Number of times the nonlinear optimization problem is solved for 
        each particle. The default is 10.
    p_opts : dict, optional
        options to give to the optimizer, see Casadi documentation. The 
        default is None.
    s_opts : dict, optional
        options to give to the optimizer, see Casadi documentation. The 
        default is None.

    Returns
    -------
    hist, Pandas Dataframe
        Returns Pandas dataframe with the loss associated with each particle 
        in the first column and the corresponding hyperparameters in the 
        second column

    """
    
    path = 'temp/PSO_param/'
    
    # Formulate Particle Swarm Optimization Problem
    dimensions_discrete = len(param_bounds.keys())
    lb = []
    ub = []
    
    for param in param_bounds.keys():
        
        lb.append(param_bounds[param][0])
        ub.append(param_bounds[param][1])
    
    bounds= (lb,ub)
    
    # Define PSO Problem
    PSO_problem = DiscreteBoundedPSO(n_particles, dimensions_discrete, 
                                     options, bounds)

    # Make a directory and file for intermediate results 
    try:
        os.makedirs(path+model.name)
    
        for key in param_bounds.keys():
            param_bounds[key] = np.arange(param_bounds[key][0],
                                          param_bounds[key][1]+1,
                                          dtype = int)
        
        index = pd.MultiIndex.from_product(param_bounds.values(),
                                           names=param_bounds.keys())
        
        hist = pd.DataFrame(index = index, columns=['cost','model_params'])    
        
        pkl.dump(hist, open(path + model.name +'/' + 'HyperParamPSO_hist.pkl','wb'))
    
    except:
        print('Found data, PSO continues...')
        
    # Define arguments to be passed to vost function
    cost_func_kwargs = {'model': model,
                        'param_bounds': param_bounds,
                        'n_particles': n_particles,
                        'dimensions_discrete': dimensions_discrete,
                        'initializations':initializations,
                        'p_opts': p_opts,
                        's_opts': s_opts,
                        'path':path}
    
    # Create Cost function
    def PSO_cost_function(swarm_position,**kwargs):
        
        # Load training history to avoid calculating stuff muliple times
        hist = pkl.load(open(path+ model.name +'/' +
                             'HyperParamPSO_hist.pkl','rb'))
            
       
        # Initialize empty array for costs
        cost = np.zeros((n_particles,1))
    
        for particle in range(0,n_particles):
            
            # Check if results for particle already exist in hist
            idx = tuple(swarm_position[particle].tolist())
            
            if (math.isnan(hist.loc[idx,'cost']) and
            math.isnan(hist.loc[idx,'model_params'])):
                
                # Adjust model parameters according to particle
                for p in range(0,dimensions_discrete):  
                    setattr(model,list(param_bounds.keys())[p],
                            swarm_position[particle,p])
                
                model.Initialize()
                
                # Estimate parameters
                results = ModelTraining(model,data,initializations, 
                                        BFR=False, p_opts=p_opts, 
                                        s_opts=s_opts)
                
                # Save all results of this particle in a file somewhere so that
                # the nonlinear optimization does not have to be done again
                
                pkl.dump(results, open(path + model.name +'/' + 'particle' + 
                                       str(swarm_position[particle]) + '.pkl',
                                       'wb'))
                
                # calculate best performance over all initializations
                cost[particle] = results.loss_val.min()
                
                # Save new data to dictionary for future iterations
                hist.loc[idx,'cost'] = cost[particle]
                
                # Save model parameters corresponding to best performance
                idx_min = results['loss_val'].idxmin()
                hist.loc[idx,'model_params'] = \
                [results.loc[idx_min,'params']]
                
                # Save DataFrame to File
                pkl.dump(hist, open(path + model.name +'/' +
                                    'HyperParamPSO_hist.pkl','wb'))
                
            else:
                cost[particle] = hist.loc[idx].cost.item()
                
        
        
        
        cost = cost.reshape((n_particles,))
        return cost
    
    
    # Solve PSO Optimization Problem
    PSO_problem.optimize(PSO_cost_function, iters=100, n_processes=None,**cost_func_kwargs)
    
    # Load intermediate results
    hist = pkl.load(open(path + model.name +'/' + 'HyperParamPSO_hist.pkl','rb'))
    
    # Delete file with intermediate results
    # os.remove(path + model.name +'/' + 'HyperParamPSO_hist.pkl')
    
    return hist

def ModelParameterEstimation(model,data,p_opts=None,s_opts=None):
    """
    

    Parameters
    ----------
    model : model
        A model whose hyperparameters to be optimized are attributes of this
        object and whose model equations are implemented as a casadi function.
    data : dict
        A dictionary with training and validation data, see ModelTraining()
        for more information
    p_opts : dict, optional
        options to give to the optimizer, see Casadi documentation. The 
        default is None.
    s_opts : dict, optional
        options to give to the optimizer, see Casadi documentation. The 
        default is None.

    Returns
    -------
    values : dict
        dictionary with either the optimal parameters or if the solver did not
        converge the last parameter estimate

    """
    
    
    u = data['u_train']
    y_ref = data['y_train']
    init_state = data['init_state_train']
    
    try:
        x_ref = data['x_train']
    except:
        x_ref = None
        
    # Create Instance of the Optimization Problem
    opti = cs.Opti()
    
    # Create dictionary of all non-frozen parameters to create Opti Variables of 
    OptiParameters = model.Parameters.copy()
   
    for frozen_param in model.FrozenParameters:
        OptiParameters.pop(frozen_param)
        
    
    params_opti = CreateOptimVariables(opti, OptiParameters)
    
    e = 0
    
    ''' Depending on whether a reference trajectory for the hidden state is
    provided or not, the model is either trained in parallel (recurrent) or 
    series-parallel configuration'''
    
    # Training in parallel configuration 
    if x_ref is None:
        
        # Loop over all batches 
        for i in range(0,len(u)):   
            
            try:
                model.switching_instances = data['switch_train'][i]
            except NameError:
                pass
            
            # Simulate Model
            pred = model.Simulation(init_state[i],u[i],params_opti)
            
            
            
            if isinstance(pred, tuple):
                pred = pred[1]
            
            # Calculate simulation error            
            # Check for the case, where only last value is available
            if y_ref[i].shape[0]==1:
                e = e + cs.sumsqr(y_ref[i] - pred[-1,:])
            else:
                e = e + cs.sumsqr(y_ref[i] - pred)
            
            
    # Training in series parallel configuration        
    else:
        # Loop over all batches 
        for i in range(0,len(u)):  
            
            # One-Step prediction
            for k in range(u[i].shape[0]-1):  
                # print(k)
                x_new,y_new = model.OneStepPrediction(x_ref[i][k,:],u[i][k,:],
                                                      params_opti)
                
                # Calculate one step prediction error
                e = e + cs.sumsqr(y_ref[i][k,:]-y_new) + \
                    cs.sumsqr(x_ref[i][k+1,:]-x_new) 
    
    opti.minimize(e)
        
    # Solver options
    if p_opts is None:
        p_opts = {"expand":False}
    if s_opts is None:
        s_opts = {"max_iter": 3000, "print_level":2}

    # Create Solver
    opti.solver("ipopt",p_opts, s_opts)
    
    # Set initial values of Opti Variables as current Model Parameters
    for key in params_opti:
        opti.set_initial(params_opti[key], model.Parameters[key])
    
    
    # Solve NLP, if solver does not converge, use last solution from opti.debug
    try: 
        sol = opti.solve()
    except:
        sol = opti.debug
        
    values = OptimValues_to_dict(params_opti,sol)
    
    return values