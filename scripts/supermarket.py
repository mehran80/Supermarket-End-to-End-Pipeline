import pandas as pd
from sqlalchemy import create_engine
import numpy as np



def clean_data_robust(df):
   

    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace(r'[ -]', '_', regex=True)
        .str.replace(r'[()]', '', regex=True)

    )

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    text_cols = df.select_dtypes(include=['object', 'string']).columns
    df[text_cols] = df[text_cols].fillna('Unknown')

    if 'order_date' in df.columns and 'ship_date' in df.columns:

        df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
        df['ship_date'] = pd.to_datetime(df['ship_date'], errors='coerce')

        # Heal dates bi-directionally: if order_date is missing, impute it as ship_date - 3 days;
        #  if ship_date is missing, impute it as order_date + 3 days

        df['order_date'] = df['order_date'].fillna(df['ship_date'] - pd.Timedelta(days=3))
        df['ship_date'] = df['ship_date'].fillna(df['order_date'] + pd.Timedelta(days=3))

        # drop the rows where both order_date and ship_date are still NaT after imputation
        df = df.dropna(subset=['order_date', 'ship_date'], how='all')

    df.drop_duplicates(inplace=True)


    return df

def validate_data(df):
    if df.empty:
        raise ValueError("DataFrame is empty after cleaning")
    
    if (df.isnull().sum().sum() > 0):
        raise ValueError("DataFrame still contains null values after cleaning")
    
    required_columns = ['order_date', 'ship_date']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    return True
    

def extract_and_load_data():
    input_file = f"f:/SQL/supermarket.csv"
    engine = create_engine('postgresql://postgres:1234@localhost:5432/supermarket')
    
    try:
        df = pd.read_csv(input_file)
        print("Data loaded successfully")

        df_cleaned = clean_data_robust(df)
        print("Data cleaned successfully")

        if validate_data(df_cleaned):
            print("Data Validation passed")

            df_cleaned.to_sql('silver_supermarket_orders', engine, if_exists='replace', index=False)
            print("Data inserted into database sucessfully")

    except Exception as e:
        print(f"An error occurred: {e}")
    


def report_genrator():
    engine = create_engine('postgresql://postgres:1234@localhost:5432/supermarket')
    try :
        df = pd.read_sql("SELECT * FROM silver_supermarket_orders", engine)

        df['order_date'] = pd.to_datetime(df['order_date'])
        monthly_trend = df.resample('ME', on='order_date')['sales'].sum().reset_index()
        monthly_trend.to_sql('gold_monthly_sales_trend', engine, if_exists='replace', index=False)

        cat_performace = df.groupby(['category', 'sub_category',])['sales'].agg(['sum', 'count', 'mean']).reset_index()
        cat_performace.to_sql('gold_cat_performance', engine, if_exists='replace', index=False)

        df['ship_date'] = pd.to_datetime(df['ship_date'])
        df['days_to_ship'] = (df['ship_date'] - df['order_date']).dt.days
        ship_report = df.groupby(['ship_mode', 'region'])['days_to_ship'].mean().reset_index()
        ship_report.to_sql('gold_shipping_report', engine, if_exists='replace', index=False)

        segment_analysis = df.groupby(['segment']).agg({'sales':'sum', 'customer_name' : 'nunique'}).reset_index()
        segment_analysis['avg_per_customer'] = (segment_analysis['sales'] / segment_analysis['customer_name']).round(2)
        segment_analysis.columns = [
            'customer_segment',
            'total_segment_sales',
            'unique_customers_count',
            'avg_per_customer'
        ]
        segment_analysis.to_sql('gold_valued_customer', engine, if_exists='replace', index=False)

        top_cites_revenue = df.groupby(['country', 'region', 'state', 'city'])['sales'].sum().reset_index().sort_values('sales',ascending=False).head(10)
        top_cites_revenue.to_sql('gold_geo_sales_map', engine, if_exists='replace', index=False)

    except Exception as e:
        print(f"Error in Report Generator: {e}")


if __name__ == "__main__":
    extract_and_load_data()
    report_genrator()


