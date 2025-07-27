from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import numpy as np
import json
from typing import Dict, Tuple, Any
import os
import json
import re
import google.generativeai as genai

# Your Data_Processor class (as provided)
class Data_Processor:
    def __init__(self, data: pd.DataFrame) -> pd.DataFrame:
        self.data = data
        [x.pop('parsed') for  x in self.data]
        self.data= pd.DataFrame(self.data)
        # self.data.drop(columns='Unnamed: 0', inplace=True, errors='ignore')
        self.data.set_index('timestamp', drop=False, inplace=True)
        self.data['amount'] = np.log(self.data['amount'])
        # self.data['timestamp'] = pd.to_datetime(self.data['timestamp'].apply(lambda x: pd)
        self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
        self.data['month'] = self.data['timestamp'].dt.month
        self.data['week'] = np.int64(self.data['timestamp'].dt.strftime('%U'))
        self.data['day'] = self.data['timestamp'].dt.day
        self.data['transaction_hour'] = self.data['timestamp'].dt.hour
        self.data['week_day'] = self.data['timestamp'].dt.weekday
        self.data['binned_hour'] = self.data['transaction_hour'] // 3
        self.data['timestamp_lag'] = self.data['timestamp'].shift(1)
        self.data['time_diff'] = self.data['timestamp'] - self.data['timestamp_lag']
        self.data['time_diff'] = self.data['time_diff'].apply(lambda x: x.total_seconds())
        self.freq_per_day = np.int64(self.data.groupby(['day'])['day'].count().mean())

    def calculate_z_score(self, value: np.array, mean: np.float64, std: np.float64, att_name: str) -> tuple:
        z = (value - mean) / std
        stat = f'Mean and Standard deviation for {att_name} are {mean}, {std} respectively.'
        return z, stat

    def calculate_rolling_stats(self, data: pd.Series, window: np.int64) -> tuple:
        rolling_mean = data.rolling(window, min_periods=1).mean()
        rolling_std = data.rolling(window, min_periods=1).std()
        avg = np.nanmean(rolling_mean)
        std = rolling_std.values[-1]
        stat = f'The rolling avg and standard deviation of amount in last {window} transactions are {avg}, {std} respectively.'
        return ((avg, std), stat)

    def flag_freq_volume(self, data: pd.DataFrame, timestamp: datetime, hour_bin: np.int64, amount: np.float64):
        velo_df = data.groupby(['day', 'binned_hour'], as_index=False).agg(
            avg_amount=('amount', 'mean'), avg_time_diff=('time_diff', 'mean'))
        velo_df[['day', 'binned_hour']] = velo_df[['day', 'binned_hour']].astype('int32')
        time_delta = timestamp - data.iloc[len(data)-1, data.columns.get_loc('timestamp')]
        time_delta = time_delta.total_seconds()
        time_avg = velo_df['avg_time_diff'].mean()
        time_std = velo_df['avg_time_diff'].std()
        Z_time, _ = self.calculate_z_score(time_delta, time_avg, time_std, 'Time Difference')
        amount_avg = velo_df['avg_amount'].mean()
        amount_std = velo_df['avg_amount'].std()
        Z_amount, _ = self.calculate_z_score(amount, amount_avg, amount_std, 'Time Difference Amount')
        freq_violation = Z_time < -2
        amount_violation = Z_amount < -3
        freq_vol_stats = f'Average & standard deviation for time difference and amount spent during binned hour {hour_bin} are ({time_avg}, {time_std}), ({amount_avg}, {amount_std}) respectively.'
        return ((freq_violation & amount_violation), freq_vol_stats)

    def calculate_stats(self, json_input):
        try:
            total_amount = np.log(np.float64(json_input['amount']).item())
            timestamp = json_input.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            timestamp = pd.to_datetime(timestamp)
            week = timestamp.week
            hour = timestamp.hour
            hour_bin = hour // 3
            merchant = json_input.get('merchant', 'Unknown').lower()
            merchant_cat = json_input.get('merchant_category', 'Unknown').lower()
        except Exception as e:
            raise e

        window = self.freq_per_day
        prior_week = week
        week_data = pd.DataFrame()
        while week_data.shape[0] < window:
            week_data = self.data[self.data['week'] >= prior_week]
            prior_week = prior_week - 1

        rolling_mean, rolling_std = self.calculate_rolling_stats(week_data['amount'], window=window)[0]
        bin_hour_mean = week_data[(week_data['binned_hour'] == hour_bin)]['amount'].mean()
        bin_hour_std = week_data[(week_data['binned_hour'] == hour_bin)]['amount'].std()
        merchant_cat_mean = week_data[(week_data['merchant_category'].str.lower() == merchant_cat)]['amount'].mean()
        merchant_cat_std = week_data[(week_data['merchant_category'].str.lower() == merchant_cat)]['amount'].std()
        merchant_mean = week_data[(week_data['merchant'].str.lower() == merchant)]['amount'].mean()
        merchant_std = week_data[(week_data['merchant'].str.lower() == merchant)]['amount'].std()

        hig_freq_low_volume_flag, hig_freq_low_volume_stats = self.flag_freq_volume(week_data, timestamp, hour_bin, total_amount)
        z_rolling_amount = self.calculate_z_score(total_amount, rolling_mean, rolling_std, 'Z_Rolling_Amount')
        z_bin_hr_amount = self.calculate_z_score(total_amount, bin_hour_mean, bin_hour_std, 'Z_Bin_hour_Amount')
        z_merchant_cat_amount = self.calculate_z_score(total_amount, merchant_cat_mean, merchant_cat_std, 'Z_Merchant_Cat_Amount')
        z_merchant_amount = self.calculate_z_score(total_amount, merchant_mean, merchant_std, 'Z_Merchant_Amount')

        return ((z_rolling_amount, z_bin_hr_amount, z_merchant_cat_amount, z_merchant_amount), (hig_freq_low_volume_flag, hig_freq_low_volume_stats))
    
class EvaluationAgent:
    '''
    Agent to flag transaction based on stats and its pretrained knowledge
    '''
    def __init__(self):
        GOOGLE_API_KEY = "AIzaSyCq4k-_rJVMpaF8znEIJNFAsMhJj_3OmNk"
        genai.configure(api_key=GOOGLE_API_KEY)

        self.model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")

    def eval(self, stats_output: Tuple, current_transaction: json)-> str:
        prompt = """
        You're an expert in analysing financial spending behaviour of individuals and have years of research knowledge
        in this field, provided with the transaction receipt from an ididvidual and some important stats from his historical
        transaction data you can understand whether it is a case of any of the following:
        Stress Eating or Impulsive buying.
        While judging you take into account the fields from the current transaction receipt like,
        merchant category, merchant, time, amount, etc along with historical transactional stats provided of the User.

        Add a top-level include the following three additional fields:
        - "anomaly": Boolean
        - "anomaly_type": one of "stress eating", "impulse buying", "high frequency anomaly"
        - "reason": The reason should be non mathematical/statistical and rather more on psychological reasoning for why the user might have done orders signifying stress eating or 
            why it could be case of impulsive buying in brief (within 2 lines).


        The stats of historical transaction will be a summary in a tuple of tuples object.
        There will be 5 tuples inside a tuple of two items where the first index item would be z-score of current value 
        and at the second index we will have avg and mean value of a prticular attribute as sentence having some information
        on the filter/subset data set used. 

        (
        (Z_Rolling_Amt, "mean and average of rolling window over last 24 hrs of all transactions in all category"), 
        (Z_Bin_Hour_Amt, "mean and average is calculated based on transactiosn of last 24hrs for the particular hour slot in which current transaction falls in."), 
        (Z_Merchant_Cat_Amt, "mean and average is calculated based on transactiosn of last 24hrs for the particular merchant cat"),
        (Z_Merchant_Amt, "mean and average is calculated based on transactiosn of last 24hrs for the particular merchant")
        ),
        (
        high_frequency_low_volume_flag: boolean (decided by logic if the transaction is within vey little time gap with respectto last transaction and trana=saction amount is low),  
        "mean and standard deviation of time elapsed(sec) between current and last transaction, average transaction amount respectively in last 24 hrs transactions filtered on the hour slot in which the current transaction is falling in." 
        )

        # 1st index of tuple has z-score for the curent amount and 2nd index has the std and meanon which the z-score was calculated and keywords signifying the subset data used. 
        # the hour slot is between 0-7 (3 hour interval)
        # use you understanding to define the z-score threshold for each of these attributes in tuple, in some cases it could be +1, -1 or +1.5, -1.5, +2, -2 etc.  
        # If the anomaly flag is 'False' then reason should be 'Normal Transaction' and anomaly type should be 'None' else provide the reason.

        EXAMPLE-
            {
            "user_id": "user_024",
            "merchant": "Domino's Pizza",
            "merchant_category": "Food & Beverage",
            "amount": 18.75,
            "timestamp": "2024-07-01T04:46:00",
            "parsed": {
                "items": [
                {"item": "Pepperoni Pizza", "price": "9.99"},
                {"item": "Choco Lava Cake", "price": "4.49"},
                {"item": "Garlic Bread", "price": "4.27"}
                ],
                "subtotal": "18.75",
                "order_number": "84",
                "payment_method": "UPI",
                "location": "MG Road",
                "timestamp": "2024-07-01 04:46"
            },
            "anomaly": false,
            "anomaly_type": "None",
            "reason": "Normal Transaction"
        }""" + f'''Historical stats: {str(stats_output)}
        Current transaction details: {str(current_transaction)}

        ### 
        '''

        try:
            response = self.model.generate_content(prompt)
            content = response.text.strip()

            content = re.sub(r"^```json|```$", "", content.strip(), flags=re.MULTILINE).strip("` \n")
            return content
        except Exception as e:
            return {"error": str(e), "raw_response": response.text if 'response' in locals() else None}
            