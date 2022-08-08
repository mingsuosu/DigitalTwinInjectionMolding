# -*- coding: utf-8 -*-
"""
Created on Tue Jan 25 15:16:22 2022

@author: LocalAdmin
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import pickle as pkl

import sys
sys.path.insert(0, "/home/alexander/GitHub/DigitalTwinInjectionMolding/")
sys.path.insert(0, 'C:/Users/rehmer/Documents/GitHub/DigitalTwinInjectionMolding/')
sys.path.insert(0, 'E:/GitHub/DigitalTwinInjectionMolding/')

from sklearn.feature_selection import SequentialFeatureSelector
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from DIM.miscellaneous.PreProcessing import LoadFeatureData
from sklearn.preprocessing import PolynomialFeatures



charges_train = list(range(1,275))
split = 'all'
del_outl = True

targets = ['Durchmesser_innen']

path_sys = 'C:/Users/rehmer/Documents/GitHub/DigitalTwinInjectionMolding/'
# path_sys = '/home/alexander/GitHub/DigitalTwinInjectionMolding/' 
# path_sys = 'E:/GitHub/DigitalTwinInjectionMolding/'

path = path_sys + 'data/Versuchsplan/normalized/'

data_train,_  = LoadFeatureData(path,charges_train,split,del_outl)
_,data_val  = LoadFeatureData(path,charges_train,split,del_outl)
# data = data_train.append(data_val)

inputs = ['Düsentemperatur', 'Werkzeugtemperatur',
            'Einspritzgeschwindigkeit', 'Umschaltpunkt', 'Nachdruckhöhe',
            'Nachdruckzeit', 'Staudruck', 'Kühlzeit','T_wkz_0','p_inj_0',
            'x_0']

data = []

for i in range(1,11):
    # Polynomial Model
    poly = PolynomialFeatures(i)
    X_poly_train = poly.fit_transform(data_train[inputs])
    X_poly_val = poly.transform(data_val[inputs])
    
    
    PolyModel = LinearRegression()
    PolyModel.fit(X_poly_train,data_train[targets])
    
    BFR = PolyModel.score(X_poly_val,data_val[targets])

    print('dim c:'+str(i)+' init:' + str(0) + ' BFR: ' + 
          str(BFR))

    data.append([BFR,'poly_set_x0',i,targets[0],0])

df = pd.DataFrame(data=data,columns=['BFR','model','complexity','target','init'])

pkl.dump(df,open('Poly_set_x0_Gewicht_all.pkl','wb'))