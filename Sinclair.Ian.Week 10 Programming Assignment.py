# -*- coding: utf-8 -*-
"""
Author:                 Ian Sinclair
Date Created:           08/20/2021
Functionality:          Maintains stocks and bonds portfolio information.
                        Including updating reports from daily stock data,
                        and writting a view for clients change in stock value
                        accross their portfolio over time. Additionally, is setup
                        to request data from yahoo finance API, and run linear
                        regression analysis to predict closing prices.
"""


import sqlite3
from prettytable import PrettyTable
import json
import requests
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
from sklearn import linear_model
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


#  Investor Class, stores information about each investor and automatically
#  adds a new investor to the database in the investor table.
class investor() :
    def __init__( self, first_name : str, last_name : str, 
                  address : str, phone_number : str ) :
        """
        Parameters
        ----------
        Returns
        -------
        Automatically adds investor information to database 
        in investor table.

        """
        #  Adds investor information to the investor table.
        try : 
            c.execute("""CREATE TABLE IF NOT EXISTS Investors (
                investor_ID integer PRIMARY KEY AUTOINCREMENT,
                first_name text,
                last_name text,
                phone_number text,
                address text
                )""")
            
            c.execute('''INSERT INTO Investors(
                    first_name,
                    last_name,
                    phone_number,
                    address )
              VALUES (?,?,?,?)''',
                 (first_name,
                  last_name,
                  address,
                  phone_number)
                  )
            c.execute("""SELECT * FROM Investors ORDER BY investor_ID DESC LIMIT 1""")
            self.investor_ID = c.fetchone()[0]
            self.first_name = first_name
            self.last_name = last_name
            self.address = address
            self.phone_number = phone_number
            
        except :
            print("Unable to process new investor in database.\n\
                      Ensure information is entored correctly in string format.\n\
                      Or try writing sql query directly.")


    def stock_value_analysis_view ( self ) :
        """
        Returns
        -------
        Prints to png a diagram/view of the value of each stock in the 
        investors portfolio over time (spans entire database).

        """
        #  Retrieves information from stocks_info table in database
        #  returns a tuple in the form (SYMBOL, DATE, Close)
        try:
            c.execute("SELECT SYMBOL, DATE, Close FROM stocks_info")
            stock_information_update = c.fetchall()
            
            
            #  Retrieves information from stocks_MASTER table in database
            #  for a particular investor.
            #  Returns a tuple in the form (SYMBOL, No_SHARES, PURCHASE_DATE)
            c.execute("""SELECT SYMBOL, No_SHARES, PURCHASE_DATE 
                          FROM stocks_MASTER 
                          WHERE investor_ID is '%s'""" % self.investor_ID)
            stock_in_portfolio = c.fetchall()
        except :
            print('Process FAILED: unable to retrieve from table stocks_info.')
 
               
        plt.figure(figsize=(17,8))
               
        #  Developes view for stock report for portfolio under investor object.
        #  NOTE: stock = (SYMBOL, No_SHARES, PURCHASE_DATE)
        #        stock_update = (SYMBOL, DATE, Close)
        for stock in stock_in_portfolio :
            stock_value_y_axis = []
            dates_x_axis = []
            
            for stock_update in stock_information_update :
                
                if stock[0] == stock_update[0] :
                    purchase_date = datetime.strptime(stock[2], "%m/%d/%Y")
                    x_axis_date = datetime.strptime(stock_update[1], "%d-%b-%y")
                    if (purchase_date - x_axis_date).days <= 0 :
                        current_stock_value = float(stock[1])*float(stock_update[2])
                        stock_value_y_axis.append(round(current_stock_value,2))
                        dates_x_axis.append(x_axis_date)
            plt.plot(dates_x_axis, stock_value_y_axis, label=stock[0])
        
        plt.legend(loc="upper left")
        
        plt.savefig('simplePlot.png')
        


    #  Returns a dictionary of all investor class attributes with the key,
    #  [investor_ID, first_name, last_name, address, phone_number]
    def get_investor_INFO( self ) :
        """        
        Returns
        -------
        dict
            [investor_ID, first_name, last_name, address, phone_number]

        """
        return { 'investor_ID' : self.investor_ID, 
                'first_name' : self.first_name, 
                'last_name' : self.last_name, 
                'address' : self.address, 
                'phone_number' : self.phone_number }



#  Class to maintain information about stock updates overtime, not subject to
#  investors. This information includes the symbol of the stock, along with
#  the open/high/low/close price of the stock on a particular date.
#  Class automatically adds information to database in stocks_info table.
class stocks_INFO_report() :
    def __init__( self, SYMBOL : str, DATE : str, Open : str, 
                 High : str, Low : str, Close : float, Volume : float) :
        """
        Returns
        -------
        None. Automatically adds stock information to stock_info table
        in database.

        """
        #Adds investor information to the investor table.
        try : 
            c.execute("""CREATE TABLE IF NOT EXISTS stocks_info (
                Info_ID integer PRIMARY KEY AUTOINCREMENT,
                SYMBOL text,
                DATE text,
                Open text,
                High text,
                Low text,
                Close real,
                Volume real
                )""")
            
            c.execute('''INSERT INTO stocks_info(
                    SYMBOL,
                    DATE,
                    Open,
                    High,
                    Low,
                    Close,
                    Volume )
              VALUES (?,?,?,?,?,?,?)''',
                 ( SYMBOL,
                DATE,
                Open,
                High,
                Low,
                Close,
                Volume )
                  )
            c.execute("""SELECT * FROM stocks_info ORDER BY Info_ID DESC LIMIT 1""")
            self.Info_ID = c.fetchone()[0]
            self.SYMBOL = SYMBOL
            self.DATE = DATE
            self.Open = Open
            self.High = High
            self.Low = Low
            self.Close = Close
            self.Volume = Volume
        except :
            print("Unable to process new stock information at date in database:\n\
                      With Symbol:  " + SYMBOL + "On date:  " + DATE + ":\n\
                      Ensure information is entored correctly.\n\
                      Or try writing sql query to stocks_info table directly.")
                      
    @staticmethod
    def call_stock_API_closing_dates( symbol : str, interval : str, _range : str) :
        """
        Parameters
        ----------
        symbol : str
            Name of stock, as appears on Yahoo Finance API directory.
        interval : str
            time between datapoints.
            format. 1m|2m|5m|15m|60m|1d
        _range : str
            Amount of time to collect past datapoints.
            format. 1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max
        
        Returns
        -------
        NONE. Adds information from yahoo finance API directly into
        stocks_info table in database. (NOTE: repeated dates will not be added
                                        so interval must exceed 1 day.)

        """
        try: 
            #  Initializes API url from rapidAPI
            url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com/stock/v2/get-chart"
            
            #  Request parameters
            querystring = {"interval":interval,"symbol":symbol,
                           "range":_range,"region":"US"}
            
            #  rapidAPI access keys.
            headers = {
                'x-rapidapi-host': "apidojo-yahoo-finance-v1.p.rapidapi.com",
                'x-rapidapi-key': "a7fb0bfb59mshf43f793ac9a114dp1c3ed1jsn444a3ce15421"
                }
            
            #  API request
            response = requests.request("GET", url, headers=headers, params=querystring)
        except :
            print('Unable to connect to API: check internal access keys or interval/_range information.')
            
        #  Dictionary to store stock information from API request.
        API_INFO = response.json()['chart']['result'][0]['indicators']['quote'][0]
        
        #Timestamps for each stock from API request
        timestamps = response.json()['chart']['result'][0]["timestamp"]
        
        dates = []
        for timestamp in timestamps :
            date = datetime.fromtimestamp(timestamp)
            dates.append(date.strftime("%d-%b-%y"))
        
        #  Logic to add stock information from API request 
        #  to stocks_info table in database.
        try: 
            c.execute( """SELECT DATE FROM stocks_info 
                          WHERE SYMBOL='%s'""" % symbol )
    
            recorded_dates = []
    
            for item in c.fetchall() :
                recorded_dates.append(item[0])                
            
            
            for index, date in enumerate(dates) :
                #Code to add api information to database.
                
                if date not in recorded_dates :            
                    c.execute('''INSERT INTO stocks_info(
                                SYMBOL,
                                DATE,
                                Open,
                                High,
                                Low,
                                Close,
                                Volume )
                          VALUES (?,?,?,?,?,?,?)''',
                             ( symbol,
                            date,
                            API_INFO['open'][index],
                            API_INFO['high'][index],
                            API_INFO['low'][index],
                            API_INFO['close'][index],
                            API_INFO['volume'][index] )
                              )
        except ConnectionError() :
            print('Process FAILED: Unable to connect to stocks_info table in datbase')
        except :
            print('Process FAILED: Unable to fill data to stocks_info table in database.')
        
        
    #  Static method to preform linear regression on a passes stock using
    #  data from stock_info table in the database.    
    #  Prints linear regression result and a view of the process.
    @staticmethod
    def predict_close_LinReg( symbol : str , max_days : int ) :                
        """
        Parameters
        ----------
        symbol : str
            
        max_days : int
             Maximum number of days collectible by the algorithm.

        Returns
        -------
        dict
            ['today closing prediction'
                'Coefficients': regr.coef_ ,
                'Mean squared error',
                'Coefficient of determination']
            prints linear regression information from stock data and prints a view.

        """
       
        #  Collect stock data from info table.        
        try :
            X_Dataset = []
            y_Dataset = []
            
            c.execute( """SELECT Close, DATE FROM stocks_info 
                      WHERE SYMBOL='%s'""" % symbol )
            
            for item in c.fetchall() :
                x_axis_date = datetime.strptime(item[1], "%d-%b-%y")
                numDays = (x_axis_date - datetime.today()).days
                if numDays >= -max_days :
                    X_Dataset.append(int(numDays))
                    y_Dataset.append(item[0])
                        
            X_Dataset = np.reshape(X_Dataset, (-1,1))
            
            X_train, X_test, y_train, y_test = train_test_split(X_Dataset, y_Dataset, test_size=0.35, random_state=42)
        
        
        except ConnectionError :
            print('Unable to connect to database, check table name.')
        except :
            print('Table could not be printed.')
            pass
        
        #  Trains linear regression model from stock data.
        regr = linear_model.LinearRegression()
        regr.fit( X_train, y_train )
        
        y_pred = regr.predict(X_test)
        
        #This is the estimated closing for today.
        current_closing_pred = regr.predict([[0]])
        
        print('todays expected closing for ' + str(symbol) + ': \t' + str(current_closing_pred))
        
        print('Model Coefficient: \n', regr.coef_)      
        print('Mean squared error: %.2f' % mean_squared_error(y_test, y_pred))
        print('R2 Coefficient of determination: %.2f' % r2_score(y_test, y_pred))
        

        #  prints view of regression model.
        plt.figure(figsize=(17,8))
        plt.scatter(X_test.T[0], y_test,  color='black')
        plt.plot(X_test.T[0], y_pred, color='blue', linewidth=3)
        plt.scatter([0], [current_closing_pred],  color='red')
        
        plt.title("Linear Regression Closing Report for " + str(symbol))
        plt.xlabel("Days from present")
        plt.ylabel("Closing Value")
        #plt.xticks(())
        #plt.yticks(())
        
        plt.show()
        
        return {'today closing prediction' : current_closing_pred,
                'Coefficients': regr.coef_ ,
                'Mean squared error' : mean_squared_error(y_test, y_pred),
                'Coefficient of determination' : r2_score(y_test, y_pred)}
    
    #  Returns a dictionary containing all stock info class atributes.
    #  with Key:
    #  [Info_ID, SYMBOL, DATE, Open, High, Low, Close, Volume]
    def get_stocks_INFO( self ) :
        """
        Returns
        -------
        dict
           ['Info_ID', 'SYMBOL', 'DATE', 
            'Open', 'Low', 'Close', 'Volume']

        """
        return { 'Info_ID' : self.Info_ID, 
                'SYMBOL' : self.SYMBOL, 
                'DATE' : self.DATE, 
                'Open' : self.Open, 
                'Low' : self.Low, 
                'Close' : self.Close, 
                'Volume' : self.Volume 
                }



#  Class to store all stock purchases and maintain information about the
#  purchase including the investor ID, the stock symbol, the number of shares
#  and the purchase price and date.
class stock_purchase() :    
    def __init__( self, investorID : int, SYMBOL : str, num_shares : str, 
                  purchase_price : str, purchase_date : str, current_value : str ) :
        """
        Returns
        -------
        None. Automatically adds purchase information to stocks_MASTER table.

        """
        try :
            c.execute("""CREATE TABLE IF NOT EXISTS stocks_MASTER (
                stock_ID integer PRIMARY KEY AUTOINCREMENT,
                investor_ID integer,
                SYMBOL text,
                PURCHASE_DATE text,
                NO_SHARES text,
                PURCHASE_PRICE real,
                CURRENT_VALUE real
                )""")

            c.execute('''INSERT INTO stocks_MASTER(
                        investor_ID,
                        SYMBOL,
                        PURCHASE_DATE,
                        NO_SHARES,
                        PURCHASE_PRICE,
                        CURRENT_VALUE )
                  VALUES (?,?,?,?,?,?)''',
                     ( investorID,
                      SYMBOL,
                      purchase_date,
                      num_shares,
                      purchase_price,
                      current_value )
                      )
            
            c.execute("""SELECT * FROM stocks_MASTER 
                      ORDER BY stock_ID DESC LIMIT 1""")
            self.stock_ID = c.fetchone()[0]
            self.investorID = investorID
            self.SYMBOL = SYMBOL
            self.num_shares = num_shares
            self.purchase_price = purchase_price
            self.purchase_date = purchase_date
            self.current_value = current_value
            
        except :
            print("Unable to process new stock purchase in database: \n \
                      At: " + investorID + "\t" + SYMBOL + "\t" + purchase_date 
                      + "\t" + "number of shares: " + num_shares + "\t current value: " 
                      + current_value + ":\n\
                      Ensure information is entored correctly. \n \
                      Or try writing sql query to stocks_MASTER table directly."
                      )


    #  returns a dictionary containing all stock_purchase class atributes.
    #  with key:
    #  [stock_ID, investorID, SYMBOL, purchase_Date, num_Shares, purchase_price, current_value]
    def get_stock_INFO( self ) :
        return { 'stock_ID' : self.stock_ID, 
                'investorID' : self.investorID, 
                'SYMBOL' : self.SYMBOL, 
                'num_shares' : self.num_shares, 
                'purchase_price' : self.purchase_price, 
                'pruchase_date' : self.purchase_date, 
                'current_value' : self.current_value 
                }



#  Given a table name, this function will print the table in the database to console.
def table_to_console( table_name : str ) :
    try :
        headers = []
        c.execute("PRAGMA table_info(%s)" % table_name)

        for item in c.fetchall() :
            headers.append(item[1])
            
        report = PrettyTable()
        report.title = "Stock INfo"
        report.field_names = headers
        c.execute("SELECT * FROM %s" % table_name)
        items = c.fetchall()
        for item in items :
            report.add_row( list(item) )
        print(report)
    except ConnectionError :
        print('Unable to connect to database, check table name.')
    except :
        print('Table could not be printed.')
        pass



def initialize_database ( ) :
    #  Connects to database in memory, and initializes cursor.
    global c
    try :
        conn = sqlite3.connect(':memory:')
        c = conn.cursor()
    except :
        print("Unable to connect to database.")


"""
        MAIN
"""
def main() :
    
    #  saves a database to memory.
    initialize_database()
    
    #  Adds an investor to the database and creates an investor object.
    New_investor = investor('Bob', 'Smith', '1 Main St.', '777-777-7777')
    
    
    #  Loads json file with stock update information and saves it to variable data_set.
    try :
        file_path = r"C:\Users\IanSi\Downloads\AllStocks.json"
        with open( file_path, 'r' ) as json_file :
           data_set = json.load(json_file)
    except :
        print("Unable to load file at: \t" + file_path)
    
    
    #  Reads stock purchase info from csv file.
    try: 
        text_file = r"C:\Users\IanSi\Downloads\Lesson6_Data_Stocks.csv"
        stock_purchase_file = open(text_file, 'r')
    except FileNotFoundError: 
        print("Unable to load file at: \t" + text_file)
        
    
    
    #  Initializes stock info and purchase dictionaries to store
    #  stock purchase and stock info objects.
    Stock_INFO_Dictionary = {}
    Stock_PURCHASE_Dictionary = {}
    
    
    #  Reads stock info from data_set and adds it to the database
    #  and creates new stock_info objects storing them in Stock_INFO_Dictionary
    try :
        for stock in data_set :
            new_stock_info = stocks_INFO_report(SYMBOL = stock['Symbol'], 
                                                DATE = stock['Date'], 
                                                Open = stock['Open'], 
                                                High = stock['High'], 
                                                Low = stock['Low'], 
                                                Close = stock['Close'], 
                                                Volume = stock['Volume']
                                                )
            Stock_INFO_Dictionary[str(new_stock_info.get_stocks_INFO()['Info_ID'])] = new_stock_info
    except :
        print("\n Unable to load stock data")
    
    
    #  Reads stock purchase information from stock_purchae_file.
    #  And stores the result in database and creates new stock_purchase objects.
    first_line = stock_purchase_file.readline().strip('\n')
    headers = first_line.split(',')
    
    SYMBOL = headers.index('SYMBOL')
    NO_SHARES = headers.index('NO_SHARES')
    PURCHASE_PRICE = headers.index('PURCHASE_PRICE')
    CURRENT_VALUE = headers.index('CURRENT_VALUE')
    PURCHASE_DATE = headers.index('PURCHASE_DATE')
    
    for line in stock_purchase_file :
        line = line.strip('\n')
        info = line.split(',')
        
        c.execute("select * from Investors WHERE investor_ID = 1")
        investor_ID = c.fetchone()[0]
        
        new_stock_purchase = stock_purchase( investorID = str(investor_ID), 
                                             SYMBOL=info[SYMBOL],
                                             purchase_date = info[PURCHASE_DATE],
                                             num_shares = info[NO_SHARES],
                                             purchase_price = info[PURCHASE_PRICE],
                                             current_value = info[CURRENT_VALUE] )
        Stock_PURCHASE_Dictionary[new_stock_purchase.get_stock_INFO()['stock_ID']] = new_stock_purchase
    
    stock_purchase_file.close()
    
    
    
    
    #  Runs different analysis on stock data.
    New_investor.stock_value_analysis_view()
    
    stocks_INFO_report.call_stock_API_closing_dates('RDS-A','1d','1y')
    
    stocks_INFO_report.predict_close_LinReg('RDS-A', 1000)






"""
    MAIN CALL
"""

if __name__ == "__main__" :
    main()




