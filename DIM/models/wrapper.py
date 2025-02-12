# -*- coding: utf-8 -*-

from sys import path
path.append(r"C:\Users\LocalAdmin\Documents\casadi-windows-py38-v3.5.5-64bit")

import casadi as cs
import matplotlib.pyplot as plt
import numpy as np

# from miscellaneous import *


class ProcessModel():
    '''
    Container for the model which estimates the quality of the part given 
    trajectories of the process variables
    '''
    def __init__(self,subsystems,name):
        """
        Initialization routine for the QualityModel class. 
    
        Parameters
        ----------
        subsystems : list,
             list of models, each model describing a disctinct phase of the
             injection molding process 
        name : string, name of the model
    
        Returns
        -------    
        """

        # self.reference = []
        # self.ref_params = {}       
        # self.subsystems = []
        # self.switching_instances = []
              
        self.subsystems = subsystems
        self.switching_instances = []
        self.name = name
        self.frozen_params = []
        
        dim_out = []
        u_label = []
        y_label = []

        
        for subsystem in self.subsystems:
            dim_out.append(subsystem.dim_out)
            u_label.extend(subsystem.u_label)
            y_label.extend(subsystem.y_label)
            
            object.__setattr__(self, 'dim_u'+'_'+subsystem.name, 
                                subsystem.dim_u)
            object.__setattr__(self, 'dim_hidden'+'_'+subsystem.name, 
                                subsystem.dim_hidden)
        
        # Check consistency      
        if sum(dim_out)/len(dim_out)==dim_out[0]:
            self.dim_out = dim_out[0]
        else:
            raise ValueError('State dimension of all subsystems needs to be equal')
        self.u_label = list(set(u_label))
        self.y_label = list(set(y_label))
        
        self.Initialize()
    
    def Initialize(self):
        """
        Re-Initializes each of the subsystems according to its own 
        initialization routine. Model structure parameters for re-initialization
        are taken from the attributes of the QualityModel instance. This
        routine is called during multi-start parameter optimization when random
        initialization of the subsystems is necessary.
        
        Parameters
        ----------
    
        Returns
        ----
        """
       
        # Update attributes of each subsystem
        for subsystem in self.subsystems:
            
            setattr(subsystem, 'dim_u', 
                    object.__getattribute__(self,'dim_u'+'_'+subsystem.name))
            setattr(subsystem, 'dim_hidden', 
                    object.__getattribute__(self,'dim_hidden'+'_'+subsystem.name))
            setattr(subsystem, 'dim_out',
                    object.__getattribute__(self,'dim_out'))
            
            # Call Initialize function of each subsystem
            subsystem.Initialize()
            
        self.ParameterInitialization()
        
        return None
    
    def Simulation(self,x0,u,params=None,switching_instances=None,**kwargs):
        """
        Simulates the quality model for a given input trajectory u and an initial
        hidden state (cell state of RNN) 
    
        Parameters
        ----------
        c0 : array-like,
             Initial hidden state (cell state), i.e. the internal state of the 
             GRU or LSTM, e.g. if dim_c = 2 then c0 is a 2x1 vector
        u : array-like with dimension [N,self.dim_u]
            trajectory of input signal, i.e. a vector with dimension N x dim_u
    
        Returns
        -------
        c : array-like,
            Vector containing trajectory of simulated hidden cell state, e.g.
            for a simulation over N time steps and dim_c = 2 c is a Nx2 vector
        y : array-like,
            Vector containing trajectory of simulated output, e.g. for
            a simulation over N time steps and dim_out = 3 y is a Nx3 vector
    
        """
        self.switching_instances = switching_instances
        
        
        
        if self.switching_instances is not None:
            switching_instances = [u.index.get_loc(s) for s in self.switching_instances]
            
            switching_instances = [0] + switching_instances + [len(u)]
            # switching_instances = [0] + switching_instances + [u.index[-1]]
            u_switched = []
            
            for s in range(len(switching_instances)-1):
                
                u_switched.append(u.iloc[switching_instances[s]:switching_instances[s+1]])
                # u_switched.append(u.loc[switching_instances[s]:switching_instances[s+1]].values)
                # u_switched.append(u.loc[switching_instances[s]:switching_instances[s+1]])
            u = u_switched
        
        # Create empty arrays for output y and hidden state c
        y = []
        x = []   
        
        # System Dynamics as Path Constraints
        for system,u_sys in zip(self.subsystems,u):
            
            # Do a one step prediction based on the model
            sim = system.Simulation(x0,u_sys,params)
            
            # OneStepPrediction can return a tuple, i.e. state and output. The 
            # output is per convention the second entry
            if isinstance(sim,tuple):
                x.append(sim[0])
                y.append(sim[1])    
                
                # Last hidden state is inital state for next model
                x0 = sim[0][-1,:].T

        y = cs.vcat(y)  
        x = cs.vcat(x)          
            
        return x,y  

    def parallel_mode(self,data,params=None):
          
        loss = 0
    
        simulation = []
        
        # Loop over all batches 
        for i in range(0,len(data['data'])):
            
            io_data = data['data'][i]
            x0 = data['init_state'][i]
            try:
                switch = data['switch'][i]
                # switch = [io_data.index.get_loc(s) for s in switch]
                kwargs = {'switching_instances':switch}
                            
                # print('Kontrolliere ob diese Zeile gewünschte Indizes zurückgibt!!!')               
            except KeyError:
                switch = None
            
            
            u = io_data.iloc[0:-1][self.u_label]
            # u = io_data[self.u_label]
    
            
            # Simulate Model        
            pred = self.Simulation(x0,u,params,**kwargs)
            
            
            y_ref = io_data[self.y_label].values
            
            
            if isinstance(pred, tuple):           
                x_est= pred[0]
                y_est= pred[1]
            else:
                y_est = pred
                
            # Calculate simulation error            
            # Check for the case, where only last value is available
            
            if np.all(np.isnan(y_ref[1:])):
                
                y_ref = y_ref[[0]]
                y_est=y_est[-1,:]
                e= y_ref - y_est
                loss = loss + cs.sumsqr(e)
                
                idx = [i]
        
            else :
                
                y_ref = y_ref[1:1+y_est.shape[0],:]                                                 # first observation cannot be predicted
                
                e = y_ref - y_est
                loss = loss + cs.sumsqr(e)
                
                idx = io_data.index
            
            if params is None:
                y_est = np.array(y_est)
                
                df = pd.DataFrame(data=y_est, columns=self.y_label,
                                  index=idx)
                
                simulation.append(df)
            else:
                simulation = None
                
        return loss,simulation
    
    def ParameterInitialization(self):
        
        self.Parameters = {}
        self.frozen_params = []
        
        for system in self.subsystems:
            system.ParameterInitialization()
            self.Parameters.update(system.Parameters)                                  # append subsystems parameters
            self.frozen_params.extend(system.frozen_params)

    def SetParameters(self,params):
        
        self.Parameters = {}
        
        for system in self.subsystems:
            system.SetParameters(params)
            self.Parameters.update(system.Parameters)
            
        
class QualityModel():
    '''
    Container for the model which estimates the quality of the part given 
    trajectories of the process variables
    '''
    def __init__(self,subsystems,name):
        """
        Initialization routine for the QualityModel class. 
    
        Parameters
        ----------
        subsystems : list,
             list of models, each model describing a disctinct phase of the
             injection molding process 
        name : string, name of the model
    
        Returns
        -------    
        """
              
        self.subsystems = subsystems
        self.switching_instances = []
        self.name = name
        self.frozen_params = []
        
        dim_c = []
        dim_out = []
        u_label = []
        y_label = []
        
        for subsystem in self.subsystems:
            dim_c.append(subsystem.dim_c)
            dim_out.append(subsystem.dim_out)
            
            u_label.extend(subsystem.u_label)
            y_label.extend(subsystem.y_label)
            
            object.__setattr__(self, 'dim_u'+'_'+subsystem.name, 
                                subsystem.dim_u)
            object.__setattr__(self, 'dim_hidden'+'_'+subsystem.name, 
                                subsystem.dim_hidden)
        
        # Check consistency
        if sum(dim_c)/len(dim_c)==dim_c[0]:
            self.dim_c = dim_c[0]
        else:
            raise ValueError('Cell state of all subsystems needs to be equal')
        
        if sum(dim_out)/len(dim_out)==dim_out[0]:
            self.dim_out = dim_out[0]
        else:
            raise ValueError('Dimension of output all subsystems needs to be equal')
            
        self.u_label = list(set(u_label))
        self.y_label = list(set(y_label))
            
        self.Initialize()

    def Initialize(self):
        """
        Re-Initializes each of the subsystems according to its own 
        initialization routine. Model structure parameters for re-initialization
        are taken from the attributes of the QualityModel instance. This
        routine is called during multi-start parameter optimization when random
        initialization of the subsystems is necessary.
        
        Parameters
        ----------
    
        Returns
        ----
        """
       
        # Update attributes of each subsystem
        for subsystem in self.subsystems:
            
            setattr(subsystem, 'dim_u', 
                    object.__getattribute__(self,'dim_u'+'_'+subsystem.name))
            setattr(subsystem, 'dim_c', 
                    object.__getattribute__(self,'dim_c'))
            setattr(subsystem, 'dim_hidden', 
                    object.__getattribute__(self,'dim_hidden'+'_'+subsystem.name))
            setattr(subsystem, 'dim_out',
                    object.__getattribute__(self,'dim_out'))
            
            # Call Initialize function of each subsystem
            subsystem.Initialize()
            
        self.ParameterInitialization()
        
        return None
    
    def Simulation(self,c0,u,params=None,switching_instances=None):
        """
        Simulates the quality model for a given input trajectory u and an initial
        hidden state (cell state of RNN) 
    
        Parameters
        ----------
        c0 : array-like,
             Initial hidden state (cell state), i.e. the internal state of the 
             GRU or LSTM, e.g. if dim_c = 2 then c0 is a 2x1 vector
        u : array-like with dimension [N,self.dim_u]
            trajectory of input signal, i.e. a vector with dimension N x dim_u
    
        Returns
        -------
        c : array-like,
            Vector containing trajectory of simulated hidden cell state, e.g.
            for a simulation over N time steps and dim_c = 2 c is a Nx2 vector
        y : array-like,
            Vector containing trajectory of simulated output, e.g. for
            a simulation over N time steps and dim_out = 3 y is a Nx3 vector
    
        """
        self.switching_instances = switching_instances
        
        
        
        if self.switching_instances is not None:
            switching_instances = [u.index.get_loc(s) for s in self.switching_instances]
            
            switching_instances = [0] + switching_instances + [len(u)]
            
            lower_b = switching_instances[0:-1]
            upper_b = switching_instances[1::]
            
            u_switched = []
            
            # if the model has external dynamics it needs delayed inputs
            if self.subsystems[0].dynamics == 'external':
                lower_b = [max(0,lb-self.subsystems[0].dim_c+1) for lb in lower_b]
            
            
            for (lb,ub) in zip(lower_b,upper_b):
                    u_switched.append(u.iloc[lb:ub])        
        
        # Create empty arrays for output y and hidden state c
        y = []
        c = []   
        
        # System Dynamics as Path Constraints
        for system,u_sys in zip(self.subsystems,u_switched):
            
            # Do a one step prediction based on the model
            sim = system.Simulation(c0,u_sys,params)
            
            # Last hidden state is inital state for next model
            c0 = sim[0][-1,:].T
            
            # OneStepPrediction can return a tuple, i.e. state and output. The 
            # output is per convention the second entry
            if isinstance(sim,tuple):
                c.append(sim[0])
                y.append(sim[1])        

        y = cs.vcat(y)  
        c = cs.vcat(c)          
            
        return c,y  

    def parallel_mode(self,data,params=None):
          
        loss = 0
    
        simulation = []
        
        # Loop over all batches 
        for i in range(0,len(data['data'])):
            
            io_data = data['data'][i]
            x0 = data['init_state'][i]
            try:
                switch = data['switch'][i]
                # switch = [io_data.index.get_loc(s) for s in switch]
                kwargs = {'switching_instances':switch}
                            
                # print('Kontrolliere ob diese Zeile gewünschte Indizes zurückgibt!!!')               
            except KeyError:
                switch = None
            
            
            u = io_data.iloc[0:-1][self.u_label]
            # u = io_data[self.u_label]
    
            
            # Simulate Model        
            pred = self.Simulation(x0,u,params,**kwargs)
            
            
            y_ref = io_data[self.y_label].values
            
            
            if isinstance(pred, tuple):           
                x_est= pred[0]
                y_est= pred[1]
            else:
                y_est = pred
                
            # Calculate simulation error            
            # Check for the case, where only last value is available
            
            if np.all(np.isnan(y_ref[1:])):
                
                y_ref = y_ref[[0]]
                y_est=y_est[-1,:]
                e= y_ref - y_est
                loss = loss + cs.sumsqr(e)
                
                idx = [i]
        
            else :
                
                y_ref = y_ref[1:1+y_est.shape[0],:]                                                 # first observation cannot be predicted
                
                e = y_ref - y_est
                loss = loss + cs.sumsqr(e)
                
                idx = io_data.index
            
            if params is None:
                y_est = np.array(y_est)
                
                df = pd.DataFrame(data=y_est, columns=self.y_label,
                                  index=idx)
                
                simulation.append(df)
            else:
                simulation = None
                
        return loss,simulation
    
    def ParameterInitialization(self):
        
        self.Parameters = {}
        self.frozen_params = []
        
        for system in self.subsystems:
            system.ParameterInitialization()
            self.Parameters.update(system.Parameters)                                  # append subsystems parameters
            self.frozen_params.extend(system.frozen_params)

    def SetParameters(self,params):
        
        self.Parameters = {}
        
        for system in self.subsystems:
            system.SetParameters(params)
            self.Parameters.update(system.Parameters)

class staticQualityModel():
    '''
    Container for the model which estimates the quality of the part given 
    trajectories of the process variables
    '''
    
    def __init__(self,setpoint_model,temp_model,lookup,name):
        """
        Initialization routine for the QualityModel class. 
    
        Parameters
        ----------
        subsystems : list,
             list of models, each model describing a disctinct phase of the
             injection molding process 
        name : string, name of the model
    
        Returns
        -------    
        """
              
        self.setpoint_model = setpoint_model
        self.temp_model = temp_model
        
        self.lookup=lookup
        self.name = name
        self.frozen_params = []
        
        # dim_c = []
        # dim_out = []
        self.u_label = setpoint_model.u_label + \
                        temp_model[lookup.index[0]].u_label
        self.y_label = temp_model[lookup.index[0]].y_label
               
        self.Initialize()

    def Initialize(self):
        """
        Re-Initializes each of the subsystems according to its own 
        initialization routine. Model structure parameters for re-initialization
        are taken from the attributes of the QualityModel instance. This
        routine is called during multi-start parameter optimization when random
        initialization of the subsystems is necessary.
        
        Parameters
        ----------
    
        Returns
        ----
        """
        
              
        self.setpoint_model.Initialize()
        
        for key,mod in self.temp_model.items():
            mod.Initialize()
                   
        self.ParameterInitialization()
        
        return None
    
    def OneStepPrediction(self,u,params=None):
        """
        Simulates the quality model for a given input trajectory u and an initial
        hidden state (cell state of RNN) 
    
        Parameters
        ----------
        c0 : array-like,
             Initial hidden state (cell state), i.e. the internal state of the 
             GRU or LSTM, e.g. if dim_c = 2 then c0 is a 2x1 vector
        u : array-like with dimension [N,self.dim_u]
            trajectory of input signal, i.e. a vector with dimension N x dim_u
    
        Returns
        -------
        c : array-like,
            Vector containing trajectory of simulated hidden cell state, e.g.
            for a simulation over N time steps and dim_c = 2 c is a Nx2 vector
        y : array-like,
            Vector containing trajectory of simulated output, e.g. for
            a simulation over N time steps and dim_out = 3 y is a Nx3 vector
    
        """
        
        setpoint_model = self.setpoint_model
        temp_model = self.temp_model 
        lookup = self.lookup
        
        # Find temperature model that belongs to this setpoint
        u_series = u[list(lookup.keys())].squeeze(0)
        set_idx = (lookup==u_series).all(axis='columns')
        set_idx = lookup.loc[set_idx].index
        
        t_model = temp_model[set_idx[0]]
        
        # Lookup which setpoint is used and normalize data accordingly
        u_norm = t_model.scale_data(u)       
        
        # predict parameters of temp model
        temp_params = setpoint_model.OneStepPrediction(u,params)
                
        if params is None:    
            # convert to numpy dict
            temp_params = np.array(cs.DM(temp_params))
        
        # write parameters estimated by setpoint model in dictionary
        est_params = temp_model[set_idx[0]].Parameters.copy()
        
        est_params = {key:temp_params[p] for key,p in 
                      zip(est_params.keys(),range(0,5))}   
        
        t_model.Parameters = est_params

        y = t_model.OneStepPrediction(u_norm)
        
        # rescale output 
        y = y + temp_model[set_idx[0]].norm_y
            
         
            
           
        return y
    
    def ParameterInitialization(self):
        '''
        Routine for parameter initialization. Takes input_names from the Casadi-
        Function defining the model equations self.Function and defines a 
        dictionary with input_names as keys. According to the initialization
        procedure defined in self.init_proc each key contains 
        a numpy array of appropriate shape

        Returns
        -------
        None.

        '''
        self.Parameters = {}
        self.frozen_params = []
        
        self.setpoint_model.ParameterInitialization()
        self.Parameters.update(self.setpoint_model.Parameters)  
        self.frozen_params.extend(self.setpoint_model.frozen_params)
        
        for key,mod in self.temp_model.items():
            mod.ParameterInitialization()
            
    def SetParameters(self,params):
        
        self.Parameters = {}
        
        self.setpoint_model.Parameters = params
        self.Parameters.update(params)

