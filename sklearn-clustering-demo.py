#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
---------------------------------------------------
Scikit-learn OAI Linear Regression Demo
---------------------------------------------------

@author: Jason Alan Fries <jfries [at] stanford.edu>

'''
import sys
import argparse
import psycopg2

import numpy as np
import math
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.ticker import NullFormatter

from sklearn import manifold, datasets
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans,SpectralClustering

# By default psycopg2 converts postgresql decimal/numeric types to 
# Python Decimal objects. This function forces a float type cast instead
DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    'DEC2FLOAT',
    lambda value, curs: float(value) if value is not None else None)
psycopg2.extensions.register_type(DEC2FLOAT)


def ses( v, idx, alpha=0.1 ) :
    if idx == 0:
        return
    ses(v, idx-1, alpha );
    v[idx] = ( alpha *  v[idx] ) + ( 1.0 - alpha ) * v[idx-1];


def interpolate(v):
    '''Interpolate missing values in column. Compute the mean 
    of the nearest pre and post observation values. 
    NOTE: We could also use the mean, some sort of exponential
    smoothing, etc. here if we like
    '''
    for j in range(0,v.shape[1]):
        
        row = v[...,j]    
        for i in range(1,len(row)-1):
            if not np.isnan(row[i]):
                continue
            a = row[i-1]
            b = row[i+1]
            k = i + 1
            
            while np.isnan(b) and k < len(row)-1:
                k += 1
                b = row[k]
            row[i] = (a+b)/2.0
        v[...,j] = row
    
        
def main(args):
    
    np.random.seed(123456)
    con = psycopg2.connect(database=args.dbname, user='') 
    cur = con.cursor()
    
    # Select all features related to WOMAC/KOOS pain subcategories
    ftr_cats = ["womac pain","koos pain"]
    
    query = "SELECT var_id FROM varcategories WHERE varcategories.cat_id IN "
    query += "(SELECT id FROM categorydefs WHERE name in (%s) AND type=2);"
    query = query % ",".join(map(lambda x:"'%s'" % x,ftr_cats))
    cur.execute(query)          
    results = [x[0] for x in cur.fetchall()]
    
    # get variable types (nominal or continuous)
    query = "SELECT var_id,type,labeln FROM vardefs WHERE var_id in (%s);"
    query = query % ",".join(map(lambda x:"'%s'" % x,results))
    cur.execute(query)  
    results = cur.fetchall()
    
    # sort by data type
    dtype = {}
    dtype["nominal"] = {var:labeln for var,t,labeln in results if t == "nominal"}
    dtype["continuous"] = {var:labeln for var,t,labeln in results if t == "continuous"}
    
    # KOOS and WOMAC pain scores measure similar things (essentially)
    vars = ["id",'vid'] + sorted(dtype["continuous"].keys())
    query = "SELECT %s FROM jointsx ORDER BY id,vid;" % ",".join(vars)
    cur.execute(query)  
    results = cur.fetchall()
    
    # create subjects
    subjects = {}
    for row in results:
        id,row = row[0],row[1:]
        subjects[id] = subjects.get(id,[]) + [row]
        
    # create a numpy tensor of pain data (4796, 10, 4)
    X = []
    MIN_NAN_THRESHOLD  = 0.5
    func = np.vectorize(interpolate)
    
    for id in subjects:
        m = np.empty((10,4),dtype=np.float64)
        m.fill(np.nan)
        
        #vid, kooskpl, kooskpr, womkpl, womkpr = row
        for row in subjects[id]:
            vid,tmp = row[0],row[1:]
            m[vid] = tmp
            
        n = np.count_nonzero(~np.isnan(m))
        if n/40.0 < MIN_NAN_THRESHOLD:
            continue
        
        # interpolate missing values
        interpolate(m)
        
        
        X += [m]
           
    X = np.array(X)
    
    # invert KOOS scale
    # 0 = no problems  1 = extreme problems
    X[...,...,0:2] = 100 - X[...,...,0:2]
    
    # Standardize to 0..1 range
    X[...,...,0:2] /= 100
    X[...,...,2:] /= 20
    
    # for each subject, create a pain progression time series
    # calculated as the max of the sum of R+L KOOS/WOMAC scores
    repl_n = 0
    pain = [] #np.empty((X.shape[0],X.shape[1]))
    for i in range(0,X.shape[0]):
        koos =  X[i][...,0] + X[i][...,1]
        womac = X[i][...,2] + X[i][...,3]
        x = (koos + womac) / 2.0
        
        # replace NaN with the mean for this row
        # REMOVE FOR NOW
        if np.count_nonzero(~np.isnan(x)) != 10:
            continue
            repl_n += 1
            x[np.isnan(x)] = np.nanmean(x)
         
        pain += [x]
        
    pain = np.array(pain)  
 
    # cluster using SpectralClustering
    k = 5
    clstr = SpectralClustering(n_clusters=k) 
    clstr.fit(pain)   
       
    for i in range(0,k):
        
        axes = plt.gca()
        axes.set_ylim([0.0,2.0])
        
        for j in range(0,pain.shape[0]):
            if clstr.labels_[j] != i:
                continue
            plt.plot(range(0,10), pain[j], color='blue', linewidth=0.1)
        
        plt.savefig("/users/fries/desktop/kmeans/%s.pdf" % i)
        plt.clf()
    
    sys.exit()
    
    '''
    # Principle Components Analysis
    pca = PCA(n_components=2)
    px  = pca.fit_transform(pain)
    print(pca.explained_variance_ratio_) 
    
    plt.scatter(px[:, 0], px[:, 1])
    plt.show()
    sys.exit()
    '''
    
    '''
    # Stochastic Neighbor Embedding
    tsne = TSNE(n_components=2, random_state=0, init='pca')
    y = tsne.fit_transform(pain)
    
    plt.scatter(y[:, 0], y[:, 1])
    ax.xaxis.set_major_formatter(NullFormatter())   
    ax.yaxis.set_major_formatter(NullFormatter())
    plt.axis('tight')
    plt.show()
    '''
     
    
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-d","--dbname", type=str, help="OAI database name", 
                        default="oai2")                    
    args = parser.parse_args()

    main(args)