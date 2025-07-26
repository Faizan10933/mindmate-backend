from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Any

# Your Data_Processor class (as provided)
class Data_Processor:
    def __init__(self, data: pd.DataFrame) -> pd.DataFrame:
        self.data = data
        [x.pop('parsed') for  x in self.data]
        self.data= pd.DataFrame(self.data)
        # self.data.drop(columns='Unnamed: 0', inplace=True, errors='ignore')
        self.data.set_index('timestamp', drop=False, inplace=True)
        self.data['amount'] = np.log(self.data['amount'])
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
        time_delta = timestamp - data.loc[data.index.max(), 'timestamp']
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

# Pydantic model for input validation
class TransactionInput(BaseModel):
    merchant: str
    merchant_category: str
    amount: float
    timestamp: str

# FastAPI app
app = FastAPI(title="Transaction Analysis API", description="API to analyze transactions for anomalies")

@app.post("/analyze-transaction/", response_model=dict)
async def analyze_transaction(transaction: TransactionInput):
    try:
        # Fetch data from Firestore
        data = pd.read_csv('synthetic_transactions_v1.csv')
        
        # Initialize Data_Processor
        processor = Data_Processor(data)
        
        # Process the input JSON
        input_data = transaction.dict()
        result = processor.calculate_stats(input_data)
        
        # Format the response
        z_scores, (freq_flag, freq_stats) = result
        response = {
            "z_scores": {
                "rolling_amount": {"z_score": float(z_scores[0][0]), "stats": z_scores[0][1]},
                "bin_hour_amount": {"z_score": float(z_scores[1][0]), "stats": z_scores[1][1]},
                "merchant_cat_amount": {"z_score": float(z_scores[2][0]), "stats": z_scores[2][1]},
                "merchant_amount": {"z_score": float(z_scores[3][0]), "stats": z_scores[3][1]},
            },
            "high_freq_low_volume": {
                "flag": bool(freq_flag),
                "stats": freq_stats
            }
        }
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))