# **Install the required python libraries:**
"""

#pymcdm installation
!pip install pymcdm

#pyomo installation for optimization
!pip install pyomo
import matplotlib.pyplot as plt

# Install Python API for AMPL
!pip install amplpy --upgrade

# Install solvers (e.g., HiGHS, Gurobi, COIN-OR)
! python -m amplpy.modules install highs gurobi coin baron conopt knitro

# Activate your license (e.g., free https://ampl.com/ce license)
#! python -m amplpy.modules activate https://ampl.com/ce

## Check the installed modules

from amplpy import modules
modules.installed()

## Some required libraries:

import numpy as np
import pandas as pd
from itertools import permutations

from pymcdm import methods as mcdm_methods
from pymcdm import weights as mcdm_weights
from pymcdm import normalizations as norm
from pymcdm import helpers as hlp
from pymcdm import correlations as corr
from pymcdm.helpers import rankdata, rrankdata

from google.colab import files

## Set the precision:

np.set_printoptions(suppress=True, precision=4)

"""## **DATA INPUTS: DECISION MATRIX AND OTHER INFORMATIONS:**"""

### Write the decision matrix in the format given below, where each coloum represent a criterion:
#In our example, seven criteria and four alternatives are there, where the second, fourth, and sixth criteria are beneficial.

matrix = np.array([[250.000, 10000, 37, 40, 4, 135, 20],
                   [315.000, 12000, 19, 20, 3, 80,  10],
                   [273.600, 15000, 8,  16, 6, 90,  50],
                   [303.386, 8000,  10, 19, 8, 95,  30]], dtype='float')

### Write the types of the criteria: 1 for beneficial criteria and -1 for cost criteria:

types = np.array([-1, 1, -1, 1, -1, 1, -1])

### Write the set of ordered pairs, denoted by OHM, from the DM: np.array([[e],[f]]), where alternative e is preferred over alternative f:
### The alternatives are 0, 1, 2, ... :
# Maximum (4*(4-1))/2=6 ordered pairs are possible.

Ohm = np.array([[0, 0, 3, 1, 3, 2],
               [1, 2, 0, 2, 1, 3]])

### Write the corresponding number of ordered pairs exactly as follows:

SET_OHMS = ['1', '2', '3', '4', '5', '6']

### Write the corresponding number of criteria exactly as follows:

SET_CRITERIA = ['1', '2', '3', '4', '5', '6', '7']

### Identify the best and worst criteria:

bestCri = '7'    #Best criteria
worstCri = '2'    #Worst criteria

### Write the pairwise comparisons between the “best and the other criteria (BTO)”, and the “others and worst criteria (OTW)”:

BTO = {'1': 2, '2': 9, '3': 7, '4': 5, '5': 3, '6': 6, '7': 1}
OTW = {'1': 5, '2': 1, '3': 4, '4': 2, '5': 4, '6': 3, '7': 9}

"""## **OSWMI MCDM Method:**"""

from pyomo.environ import *
from amplpy import modules
import numpy as np

### Create the normalized decision matrix using vector normalization:
nmatrix = hlp.normalize_matrix(matrix, norm.vector_normalization, types)

### Objective weights evaluation:
def _cov(x, y):
    return np.cov(x, y, bias=True)[0][1]

def pearson(x, y):
    return (_cov(x, y)) / (np.std(x) * np.std(y))

def correlation_matrix(rankings, columns=False):

    if columns:
        rankings = rankings.T
    n = rankings.shape[0]
    corr = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            corr[i, j] = pearson(rankings[i], rankings[j])
    return corr

def improved_critic_weights(nmatrix):
    std = np.std(nmatrix, axis=0, ddof=1)
    coef = correlation_matrix(nmatrix, True)
    C = std * np.sum(1 - coef, axis=0)
    Wg = C / np.sum(C)
    G = 1 + np.sqrt(Wg)
    return G / np.sum(G)

objective_weights = improved_critic_weights(nmatrix)

#LINMAP II:
Ee = Ohm[0]      #e in set of paired comparisons: first row of Ohm
Ff = Ohm[1]      #f in set of paired comparisons: second row of Ohm

alpha = np.zeros((len(Ee), nmatrix.shape[1]))
beta1 = np.zeros((len(Ee), nmatrix.shape[1]))
for i in range(nmatrix.shape[1]):
        for e in range(len(Ee)):
            alpha[e, i] = (nmatrix[Ff[e],i])**2 - (nmatrix[Ee[e],i])**2
            beta1[e, i] = -2*((nmatrix[Ff[e],i]) - (nmatrix[Ee[e],i]))

T = alpha.sum(axis = 0)
D = beta1.sum(axis = 0)

# model formulation
model = ConcreteModel();

#set declaration
model.OHMS = Set(initialize = SET_OHMS);
model.CRIT = Set(initialize = SET_CRITERIA);

#Variable declaration

model.w = Var(model.CRIT, domain=NonNegativeReals)
model.u = Var(model.CRIT, domain=NonNegativeReals)
model.z1 = Var(model.OHMS, domain=NonNegativeReals)
model.z2 = Var(model.OHMS, domain=NonNegativeReals)
model.x1m = Var([1], domain=NonNegativeReals)
model.x1p = Var([1], domain=NonNegativeReals)
model.varp11 = Var(model.CRIT, domain=NonNegativeReals)
model.varm12 = Var(model.CRIT, domain=NonNegativeReals)
model.varp21 = Var(model.CRIT, domain=NonNegativeReals)
model.varm22 = Var(model.CRIT, domain=NonNegativeReals)
model.varp2 = Var([1], domain=NonNegativeReals)
model.varm2 = Var([1], domain=NonNegativeReals)
model.varp3 = Var(model.CRIT, domain=NonNegativeReals)
model.varm3 = Var(model.CRIT, domain=NonNegativeReals)
model.delta = Var(model.CRIT, domain=NonNegativeReals)
model.v1 = Var(model.CRIT, domain=Reals)
model.v2 = Var(model.CRIT, domain=Reals)

#Parameter declaration

# BTO:
model.hb = Param(model.CRIT, initialize = BTO);

# OTW:
model.hw = Param(model.CRIT, initialize = OTW);

## alpha_efi
OHM_CRIT_Alpha = {}
for i in SET_OHMS:
  for j in SET_CRITERIA:
    OHM_CRIT_Alpha[(i,j)] = alpha[int(i) - 1][int(j) - 1]

model.alpha = Param(model.OHMS, model.CRIT, initialize = OHM_CRIT_Alpha);

#Beta_efj
OHM_CRIT_Beta = {}
for i in SET_OHMS:
  for j in SET_CRITERIA:
    OHM_CRIT_Beta[(i,j)] = beta1[int(i) - 1][int(j) - 1]

model.beta = Param(model.OHMS, model.CRIT, initialize = OHM_CRIT_Beta);

#T_j
T_values = {}
for i in SET_CRITERIA:
  T_values[i] = T[int(i) - 1]

model.T = Param(model.CRIT, initialize = T_values);

# D_j
D_values = {}
for i in SET_CRITERIA:
  D_values[i] = D[int(i) - 1]

model.D = Param(model.CRIT, initialize = D_values);

#Objective criteria weights
OBJ_Wt_values = {}
for i in SET_CRITERIA:
  OBJ_Wt_values[i] = objective_weights[int(i) - 1]

model.wo = Param(model.CRIT, initialize = OBJ_Wt_values);

# Constraints declaration

def rule1(model,CRIT):
  return model.delta[CRIT] + model.varm3[CRIT] - model.varp3[CRIT] == ((model.wo[CRIT]+model.w[CRIT])/2)-(0.5 * (model.wo[CRIT] + model.w[CRIT] - sqrt((model.wo[CRIT] - model.w[CRIT])**2 + (1e-4)**2)))
model.eq1 = Constraint(model.CRIT, rule = rule1);

def rule2(model,CRIT):
  return model.w[bestCri] - (model.hb[CRIT] * model.w[CRIT]) + model.varm12[CRIT] - model.varp11[CRIT] == 0
model.eq2 = Constraint(model.CRIT, rule = rule2);

def rule3(model,CRIT):
  return model.w[CRIT] - (model.hw[CRIT] * model.w[worstCri]) + model.varm22[CRIT] - model.varp21[CRIT] == 0
model.eq3 = Constraint(model.CRIT, rule = rule3);

def rule4(model,CRIT):
  return model.u[CRIT] >= (0.5 * (model.wo[CRIT] + model.w[CRIT] - sqrt((model.wo[CRIT] - model.w[CRIT])**2 + (1e-4)**2))) + model.delta[CRIT]
model.eq4 = Constraint(model.CRIT, rule = rule4);

def rule5(model,CRIT):
  return model.u[CRIT] <= (0.5 * (model.wo[CRIT] + model.w[CRIT] + sqrt((model.wo[CRIT] - model.w[CRIT])**2 + (1e-4)**2))) - model.delta[CRIT]
model.eq5 = Constraint(model.CRIT, rule = rule5);

def rule6(model,OHMS):
  return sum((model.alpha[(OHMS,CRIT)] * model.u[CRIT]) for CRIT in model.CRIT) + sum((model.beta[(OHMS,CRIT)] * model.v1[CRIT]) for CRIT in model.CRIT) + model.z1[OHMS] >= 0
model.eq6 = Constraint(model.OHMS, rule = rule6);

def rule7(model,OHMS):
  return sum((model.alpha[(OHMS,CRIT)] * model.u[CRIT]) for CRIT in model.CRIT) + sum((model.beta[(OHMS,CRIT)] * model.v2[CRIT]) for CRIT in model.CRIT) <= model.z2[OHMS]
model.eq7 = Constraint(model.OHMS, rule = rule7);

def rule8(model):
  return sum((model.z1[OHMS] + model.z2[OHMS]) for OHMS in model.OHMS) + model.x1m[1] - model.x1p[1] == 0
model.eq8 = Constraint(rule = rule8);

def rule9(model):
  return sum((model.T[CRIT] * model.u[CRIT]) for CRIT in model.CRIT) + sum((model.D[CRIT] * model.v1[CRIT]) for CRIT in model.CRIT) == 1
model.eq9 = Constraint(rule = rule9);

def rule10(model):
  return sum((model.T[CRIT] * model.u[CRIT]) for CRIT in model.CRIT) + sum((model.D[CRIT] * model.v2[CRIT]) for CRIT in model.CRIT) + 1 == 0
model.eq10 = Constraint(rule = rule10);

def rule11(model):
  return sum(model.w[CRIT] for CRIT in model.CRIT) == 1
model.eq11 = Constraint(rule = rule11);

def rule12(model):
  return sum(model.u[CRIT] for CRIT in model.CRIT) == 1
model.eq12 = Constraint(rule = rule12);

#Objective function
model.obj = Objective(expr = (model.x1m[1] + model.x1p[1] + sum((model.varm12[CRIT] + model.varp11[CRIT] + model.varm22[CRIT] + model.varp21[CRIT] + model.varm3[CRIT] + model.varp3[CRIT])
                              for CRIT in model.CRIT)), sense=minimize)

#Solve statement
results = SolverFactory(modules.find("ipopt"), solve_io="nl").solve(model, tee=False)  # use the solver ipopt

#Print the results
results.write()
print("\nRESULTS:");
print("\nObjective function value = ", model.obj());

subjective_weights = np.zeros((len(model.CRIT)))
final_weights = np.zeros((len(model.CRIT)))
delta_values = np.zeros((len(model.CRIT)))
V_pis = np.zeros((len(model.CRIT)))
V_nis = np.zeros((len(model.CRIT)))
y_plus_y_minus = np.zeros((len(model.CRIT)))
z_plus_z_minus = np.zeros((len(model.CRIT)))
for i,v in enumerate(model.CRIT):
  subjective_weights[i] = model.w[v]()
  final_weights[i] = model.u[v]()
  delta_values[i] = model.delta[v]()
  V_pis[i] = model.v1[v]()
  V_nis[i] = model.v2[v]()
  y_plus_y_minus[i] = model.varp11[v]() - model.varm12[v]()
  z_plus_z_minus[i] = model.varp21[v]() - model.varm22[v]()

#Consistency ratio
ConsisMat = np.array([y_plus_y_minus,z_plus_z_minus])
epsilon_star = ConsisMat.max()
h_BW = model.hb[worstCri]
if h_BW == 1:
  ConsisIndex = 0
elif h_BW == 2:
  ConsisIndex = 0.44
elif h_BW == 3:
  ConsisIndex = 1
elif h_BW == 4:
  ConsisIndex = 1.63
elif h_BW == 5:
  ConsisIndex = 2.30
elif h_BW == 6:
  ConsisIndex = 3
elif h_BW == 7:
  ConsisIndex = 3.73
elif h_BW == 8:
  ConsisIndex = 4.47
elif h_BW == 9:
  ConsisIndex = 5.23

ConsisRatio = epsilon_star / ConsisIndex

N_pis = V_pis/final_weights  #Positive Ideal Solutions
N_nis = V_nis/final_weights  #Negative Ideal Solutions

#Ranking index:
Euclidean_PIS = np.zeros((nmatrix.shape[0], nmatrix.shape[1]))
S_PIS = np.zeros((nmatrix.shape[0]))
for i in range(nmatrix.shape[0]):
  for j in range(nmatrix.shape[1]):
    if final_weights[j] == 0:
      Euclidean_PIS[i,j] = -2*(V_pis[j]*nmatrix[i,j])
    else:
      Euclidean_PIS[i,j] = final_weights[j]*(nmatrix[i,j]-N_pis[j])**2
  S_PIS[i] = np.sum(Euclidean_PIS[i])

Euclidean_NIS = np.zeros((nmatrix.shape[0], nmatrix.shape[1]))
S_NIS = np.zeros((nmatrix.shape[0]))
for i in range(nmatrix.shape[0]):
  for j in range(nmatrix.shape[1]):
    if final_weights[j] == 0:
      Euclidean_NIS[i,j] = -2*(V_nis[j]*nmatrix[i,j])
    else:
      Euclidean_NIS[i,j] = final_weights[j]*(nmatrix[i,j]-N_nis[j])**2
  S_NIS[i] = np.sum(Euclidean_NIS[i])

OPS = S_NIS/(S_PIS+S_NIS)
ranking = rrankdata(OPS)

np.set_printoptions(precision=4)
print("\nNormalized matrix = ", nmatrix)
print("\nObjective weights = ", objective_weights)
print("\nSubjective weights = ", subjective_weights)
print("\nConsistency Ratio (CR) = ", ConsisRatio)
print("\nFinal integrated weights = ", final_weights)
print("\nSum of final integrated weights = ", round(np.sum(final_weights), 2))
print("\nDelta values = ", delta_values)
print("\nPositive Ideal Solution = ", N_pis)
print("\nNegative Ideal Solution = ", N_nis)
np.set_printoptions(precision=20)
print("\nOverall Performance Score (OPS) = ", OPS)
np.set_printoptions(precision=1)
print("\nOverall ranking = ", ranking)

"""## **Download the normalized matrix and OSWMI results in excel files:**"""

### Download the normalized matrix and OSWMI results in xlsx:

Normalized_Matrix_df = pd.DataFrame(nmatrix)
OSWMI_Results_df = pd.DataFrame({'Ob Wts.': objective_weights, 'Sub Wts.': subjective_weights, 'Final Wts.': final_weights, 'Delta': delta_values,
                                      'PIS': N_pis, 'NIS': N_nis})
OSWMI_Ranking_df = pd.DataFrame({'OPS': OPS, 'Ranking': ranking})

file_name_Normalized_Matrix = 'Normalized_Matrix_erp.xlsx'
file_name_OSWMI_Results = 'OSWMI_Results_erp.xlsx'
file_name_OSWMI_Ranking = 'OSWMI_Ranking_erp.xlsx'

# saving the excel
Normalized_Matrix_df.to_excel(file_name_Normalized_Matrix)
OSWMI_Results_df.to_excel(file_name_OSWMI_Results)
OSWMI_Ranking_df.to_excel(file_name_OSWMI_Ranking)

files.download('Normalized_Matrix_erp.xlsx')
files.download('OSWMI_Results_erp.xlsx')
files.download('OSWMI_Ranking_erp.xlsx')
