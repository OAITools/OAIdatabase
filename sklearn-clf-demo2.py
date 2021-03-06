#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
---------------------------------------------------
Scikit-learn OAI Linear Regression Demo
---------------------------------------------------

**** WORK IN PROGRESS **** 

@author: Jason Alan Fries <jfries [at] stanford.edu>

'''
import sys
import argparse
import psycopg2
import operator
import numpy as np
import math
import datetime

from scipy import stats
import statsmodels.api as sm
import matplotlib.pyplot as plt
from statsmodels.distributions.mixture_rvs import mixture_rvs

from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import MinMaxScaler
from sklearn.cross_validation import KFold
from sklearn.cross_validation import train_test_split
from sklearn.cross_validation import cross_val_score
from sklearn.metrics import mean_squared_error,r2_score
from sklearn.learning_curve import learning_curve
from sklearn.metrics import make_scorer
from sklearn.preprocessing import OneHotEncoder

# -------------------------------------------------------------------
# By default psycopg2 converts postgresql decimal/numeric types to 
# Python Decimal objects. This code forces a float type cast instead
DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    'DEC2FLOAT',
    lambda value, curs: float(value) if value is not None else None)
psycopg2.extensions.register_type(DEC2FLOAT)
# -------------------------------------------------------------------

def sm_histogram(X,bins=10):
    
    # kernel density estimation
    kde = sm.nonparametric.KDEUnivariate(X)
    kde.fit()
    
    fig = plt.figure(figsize=(12,8))
    ax = fig.add_subplot(111)
    ax.hist(X, bins=bins, normed=True, color='white')
    ax.plot(kde.support, kde.density, lw=2, color='black');
    plt.show()

def get_table_names():
    
    con = psycopg2.connect(database=args.dbname, user='') 
    cur = con.cursor()
    sql = "SELECT DISTINCT(table_name) FROM information_schema.columns"
    sql += " WHERE table_schema='public';"
    cur.execute(sql)
    results = cur.fetchall()
    
    return results

def query_db(sql):
    
    con = psycopg2.connect(database=args.dbname, user='') 
    cur = con.cursor()
    cur.execute(sql)
    return cur.fetchall()

def main(args):
    
    np.random.seed(123456)
    con = psycopg2.connect(database=args.dbname, user='') 
    cur = con.cursor()
    
    # ===============================================
    #
    # Simple Binary Classification Example
    #
    # ===============================================
    # Q: Will subject will undergo a R or L TKA 
    #    by their next OAI visit?
 
    
    # -----------------------------------------------
    #
    # STEP 1: Data Set 
    #
    # -----------------------------------------------
    
    # Identify our subjects (anyone with a R or L TKA)
    query = "SELECT ID,v99erkfldt,v99elkfldt FROM outcomes99;"
    cur.execute(query)          
    results = cur.fetchall()

    # 342/4552 Subjects: 203 Right, 210 Left, 71 R+L
    subjects = {id:[rtka,ltka] for id,rtka,ltka in results 
                if rtka != None or ltka != None }
    
    # Visit Dates
    visit_defs = {0:0, 1:12, 2:18 ,3:24, 4:30, 5:36, 6:48, 7:60, 8:72, 9:84}
    
    ids = ["'%s'" % id for id in subjects]
    query = "SELECT ID,V99ELKVSPR,V99ELKVSAF,V99ERKVSPR,V99ERKVSAF "
    query += "FROM outcomes99 WHERE ID in (%s);"
    query = query % ",".join(ids)
    cur.execute(query) 
    results = cur.fetchall()
    
    # ID: Left-Before, Left-After, Right-Before, Right-After
    before_after_dates = {x[0]:x[1:] for x in results}
    min_before_dates = {}
    for id in before_after_dates:
        v1 = before_after_dates[id][0] 
        v2 = before_after_dates[id][2]
        v1 = v1 if v1 != None else 999
        v2 = v2 if v2 != None else 999
        # remove subjects who had a TKA at baseline 
        # but (at present) no TKA for the other knee
        if (v1 == 0 and v2 == 999) or (v1 == 999 and v2 == 0):
            continue
        min_before_dates[id] = min(v1,v2)
    
    #
    # Build Subject Features
    #
        
    # Select all features from the JointSx data set
    query = """
        SELECT column_name,vardefs.type
        FROM information_schema.columns, vardefs
        WHERE table_schema='public' AND table_name SIMILAR TO '%jointsx%'
        AND column_name=lower(vardefs.var_id);
    """
    cur.execute(query) 
    results = cur.fetchall()
    joint_vars = {x[0]:x[1] for x in results}
    
    tbl = "jointsx"
    c_jnt_vars = [var_id for var_id in joint_vars if joint_vars[var_id]=="Continuous"]
    tbl_names = [x[0] for x in get_table_names()]
    tbl_names = sorted([x for x in tbl_names if tbl in x])
    
    # P01 = Screening         |
    # P02 = Eligibility       |-- 
    # V00 = Enrollment Visit  |
    # VXX = Visit Num
    ftrs = [(x[0:3],x) for x in c_jnt_vars if x] 
    ftrs_by_visit = {}
    for visit_id,value in ftrs:
        ftrs_by_visit[visit_id] = ftrs_by_visit.get(visit_id,[]) + [value]
    
    ftrs_by_visit["v00"] += ftrs_by_visit["p01"]
    del ftrs_by_visit["p01"]
    
    var_idx = {}
    for visit_id in sorted(ftrs_by_visit.keys()):
        var_idx.update([(x[3:],1) for x in ftrs_by_visit[visit_id]])    
    var_idx = {key:i for i,key in enumerate(var_idx)}
    
    visit_data = {}
    for visit_id in ftrs_by_visit:
        vid = visit_id[1:]
        query = "SELECT ID,%s FROM %s%s;" % (",".join(ftrs_by_visit[visit_id]),tbl,vid)
        visit_data[vid] = query_db(query)
    
    ftrs_by_id = {}
    for i in range(0,10):
        vid = ("00%s" % i)[-2:]
        header = ["id"] + [ x[3:] for x in ftrs_by_visit["v"+vid]]
        
        for row in visit_data[vid]:
            print zip(header,row)
    
    
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-d","--dbname", type=str, help="OAI database name", 
                        default="oai")                    
    args = parser.parse_args()

    main(args)