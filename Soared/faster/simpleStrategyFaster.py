# -*- coding: utf-8 -*-
"""
Created on Fri Mar 26 16:51:37 2021

@author: Longer
"""

import pandas as pd
import numpy as np
from datetime import datetime

#index_col=0get rid of "Unnamed: 0" column in a pandas 
#index_col=0 : 避免讀取csv後出現unnamed欄位
df = pd.read_csv('./raw_m.csv', index_col=0)

#儲存交易紀錄
#recording each transaction
record = pd.DataFrame()

'''
================= preprocess =================
'''

#String to datetime
#轉換字串為時間格式
df['time']= pd.to_datetime(df['time']).dt.time
df['date']= pd.to_datetime(df['date']).dt.date

#to get "last candle stick closing price" for this strategy
#新增column，紀錄前1根K棒收盤價
df['prev_c'] = df['c'].shift()

#got 1 row of NA at column "prev_c", drop it
#首筆資料沒有前面的K棒資料，drop
df = df.dropna()

#calculate the volatility of price (closing price)
#計算漲跌幅(未轉換為百分比)
df['vol'] = (df['c'].astype(int) - df['prev_c'].astype(int))/ df['prev_c'].astype(int)

#將分K資料以日為單位分組，方便後續當沖策略操作
#grouped by date for the day trading strategy
grouped = list(df.groupby("date"))

'''
================= trading parameter =================
'''
#虧損20點停損
#set stop loss price
stop_loss = 20

#設定觸發交易的閾值
#threshold that triggered the trading signal
threshold = 0.003

#for settlement date
settlement_date = ['2017-01-18', '2017-02-15', '2017-03-15', '2017-04-19', '2017-05-17', '2017-06-21', '2017-07-19', '2017-08-16', '2017-09-20', '2017-10-18', '2017-11-15', '2017-12-20', '2018-01-17', '2018-02-21', '2018-03-21', '2018-04-18', '2018-05-16', '2018-06-20', '2018-07-18', '2018-08-15', '2018-09-19', '2018-10-17', '2018-11-21', '2018-12-19', '2019-01-16', '2019-02-20', '2019-03-20', '2019-04-17', '2019-05-15', '2019-06-19', '2019-07-17', '2019-08-21', '2019-09-18', '2019-10-16', '2019-11-20', '2019-12-18', '2020-01-15', '2020-02-19', '2020-03-18', '2020-04-15', '2020-05-20', '2020-06-17', '2020-07-15', '2020-08-19', '2020-09-16', '2020-10-21', '2020-11-18', '2020-12-16', '2021-01-20', '2021-02-17', '2021-03-17', '2021-04-21', '2021-05-19', '2021-06-16', '2021-07-21', '2021-08-18', '2021-09-15', '2021-10-20']

'''
================= strategy =================
'''
#從grouped資料當中依序遍歷每一天的資料
#traversal all element(date) in grouped data
for i in range(len(grouped)):  
    
    #處理結算日事件
    #deal with settlement date event
    #general days closing at 13:45, settlement date closing at 13:30
    #5 min early for convenience
    if str(grouped[i][0]) in settlement_date:
        end_time  = datetime.strptime('13:25', '%H:%M').time()
    else:
        end_time = datetime.strptime('13:40', '%H:%M').time()
    
    #當日分K資料
    #get daily data
    daily = grouped[i][1].reset_index(drop = True)
    
    #過濾出符合條件的資料
    #select data that meet the condition
    filted = daily[daily["vol"] > threshold]

    #新倉
    #filted無資料表示無觸發交易，掠過
    #filted有資料則取第一筆，做為今日交易
    #opening position
    #filted empty means there's no any transaction in this day
    #filted not empty means each possible transaction in this day 
    #we pick the first transaction here for convenience
    if (not filted.empty):
        
        #過濾符合新倉條件的資料
        #第一筆符合threshold
        long_data = filted.head(1)

        #紀錄新倉的index，後續停損判斷時僅需擷取此筆以後的資料進行計算
        #record the index which open a position 
        #and select the data after this index for stop loss condition determination
        index = long_data.index[0] 
           
        long_price = long_data["c"].values[0] 
       
        record = record.append({"date" : long_data["date"].values[0], "time" : long_data["time"].values[0], "long_price": long_price, "status" : "long"}, ignore_index=True)   
        
        
        # 平倉(停損)
        # 停損資料要在新倉之後、end_time之前、觸發停損條件
        #closing position(stop loss)
        #should be after open position, before end_time, and triggered the stoping loss condicion
        filted = daily[(daily.index >= index)  & (daily["time"] < end_time) & (daily["c"] <= (long_price - stop_loss))]
        
        if not filted.empty:
            #過濾符合停損條件的資料
            #第一筆符合threshold
            #select the data meet stoping loss condiction
            #and pick the first transaction
            short_data = filted.head(1)
            short_price = short_data["c"].values[0]  
            
            profit = short_price - long_price
            record = record.append({"date" : short_data["date"].values[0]  , "time" : short_data["time"].values[0]  , "short_price": short_price, "profit" : profit, "status" : "long_covered"}, ignore_index=True)   
        
        
        #平倉(收盤)
        #closing position(end of each date)
        else :
            
            #配合慢速版，尚未處理結算日問題，因此固定用13:29
            #use 13:29 as the last transaction each date
            short_data = daily[daily["time"] == end_time]
            short_price = short_data["c"].values[0]
            profit = short_price - long_price
            
            record = record.append({"date" : short_data["date"].values[0], "time" : short_data["time"].values[0], "short_price": short_price, "profit" : profit, "status" : "long_covered"}, ignore_index=True)   

'''
================= evaluate =================
'''

#generate profit list of each transaction
profit_list = record["profit"].dropna().reset_index(drop = True)

#total transaction times
num  = len(profit_list)
#record of profit >=0 in profit list
win_list  = profit_list[profit_list >= 0]
#record of profit <0 in profit list
lose_list = profit_list[profit_list < 0]
#number of win 
win  = len(win_list)
#number of lose
lose = len(lose_list)

print("Sum:", num)
print("Win:", win," Lose:", lose)
print("Odds:", win/num)
print("Cum:", sum(profit_list))
print("PF:",sum(win_list)/(sum(lose_list)*-1))


#計算MDD(Maximum Drawdown)
#先算DD並紀錄於list當中，再從中取出最大值即為MDD
#DD定義:「累計損益」距離上一次創新高後，回吐多少幅度才再創下一次新高
#calculate MDD
#tips: calculate each DD and append into a list first, then find the maximum one
#definition of drawdown: the distance between last peak and the next peak
cumsum_list = np.cumsum(profit_list)

#累計損益上一次新高
#last peak of cumsum profit
high = 0
#當前DD
#the currently dd 
dd = 0
dd_list=[]


for i in cumsum_list:
    #累計損益創新高，刷新high
    #if cumsum profit higher then last peak, then update the peak as currently value  
    if i > high:
        high = i
        #創下次新高，DD刷新為0
        #reach new peak, reset dd as 0 
        dd = 0
    
    #累計損益小於前一次新高，回檔開始
    #cumsum profit lower than last peak, means start drawing down
    if i < high:
        #累計損益持續往下才刷新dd
        #cumsum profit keep going down, update the dd value
        if (high - i) > dd:
            #dd即為上次新高距離現在的幅度
            #calculate the value of dd: "last peak - currently value"
            dd = high - i
            dd_list.append(dd)
            
print("MDD:", max(dd_list))
        

'''
================= cumsum line plot =================
'''
df_plot = record[["date", "profit"]].dropna().reset_index(drop = True)
df_plot["profit"] = np.cumsum(df_plot["profit"])
df_plot.plot(x = "date", y = "profit",rot=45)