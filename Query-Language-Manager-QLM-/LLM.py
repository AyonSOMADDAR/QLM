from dotenv import load_dotenv
import os
import google.generativeai as genai
import mysql.connector
import streamlit as st
import logging
import pandas as pd
from collections import deque
import seaborn as sns
import matplotlib.pyplot as plt


class AIModel:
    def __init__(self, api_key, model_name, generation_config, safety_settings):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=model_name, safety_settings=safety_settings)
        self.generation_config = generation_config

    def get_response(self, prompt):
        responses = self.model.generate_content(
            prompt,
            generation_config=self.generation_config,
            stream=True,
        )
        query = ""
        for response in responses:
            query += response.text
        return query

class DatabaseManager:
    def __init__(self, host, user, password, database):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.cursor = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.cursor=self.connection.cursor(buffered=True)
            logging.info("Successfully connected to the database.")
        except mysql.connector.Error as err:
            logging.error(f"Error: {err}")
            st.error(f"Database connection failed: {err}")

    def execute_query(self, query):
        try:
            self.cursor.execute(query)
            self.connection.commit()
            columns = []
            if self.cursor!= []:
                for x in self.cursor:
                    columns.append(x)
            df=pd.DataFrame(columns)
            st.write(df)
            logging.info("Query executed successfully.")
            return "Query executed successfully."
        
        except mysql.connector.Error as err:
            logging.error(f"Error: `{err}`")
            st.error(f"Some error raised, check log file")
        except:
            st.write("`executed`")
            

def setup_logging():
    logging.basicConfig(filename="app.log", 
                        level=logging.INFO, 
                        format="%(asctime)s:%(levelname)s:%(message)s")
def read_last_lines(filename, lines_count):
    with open(filename, 'r') as file:
        return ''.join(deque(file, maxlen=lines_count))
    


def main():
    load_dotenv()
    setup_logging()
    tab1, tab2 = st.tabs(["Query Language Model (QLM)", "Financial Data Visualization"])

    database=st.text_input("Enter Database")
    

    
    if database:
            
        st.write(f"*`Working on {database} database`*")
        with tab1:
            api_key = os.getenv("GOOGLE_API_KEY")
            ai_model = AIModel(
                api_key=api_key,
                model_name="gemini-pro",
                generation_config=genai.types.GenerationConfig(
                    temperature=0.5,
                    top_p=0.5,
                    top_k=32,
                    candidate_count=1,
                    max_output_tokens=1000,
                ),
                safety_settings=[
                    {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
            )
            
            db_manager = DatabaseManager(
                host="localhost",
                user="root",
                password="ayon_0611",
                database=database
                )
    
            db_manager.connect()
            
            st.title("Query Language Generator (QLG)")
            if 'chat_history' not in st.session_state:
                st.session_state['chat_history'] = []


            with st.form("sql_form"):
                user_input = st.text_area("Enter your prompt:")
                submit_button = st.form_submit_button(label="Generate and Execute SQL")

            if submit_button and user_input:
                prompt = f"""
                {user_input}
                Generate a valid SQL command based on the above description that I can directly paste in SQL sheet.
                - Output the SQL command only, with no additional text or explanations.
                - Ensure the command is a single line without any newline or escape sequences.
                - Do not include any comments or unnecessary whitespace or quotes.
                """
                st.session_state['chat_history'].append(("``USER``", user_input))
                query = ai_model.get_response(prompt)
                st.write(f"Generated SQL Query:`{query}`")

                execution_result = db_manager.execute_query(query)
                st.write(execution_result)
                st.session_state['chat_history'].append(("``QLG``", f"`{query}`"))
        
        
        with tab2:
                conn = db_manager.connection
                query = "SELECT account_id, user_id, account_type, balance FROM accounts"
                account_data = pd.read_sql(query, conn)
                
                conn = db_manager.connection
                query = "SELECT transaction_id, account_id, amount, transaction_type, transaction_date FROM transactions"
                transaction_data= pd.read_sql(query, conn)
                
                st.title("Financial Management Dashboard")
                
                st.header("Account Balances")
                st.write(account_data)


                st.subheader("Account Balances by Account Type (Bar Chart)")
                account_balance_by_type = account_data.groupby("account_type")['balance'].sum().reset_index()
                account_balance_by_type_chart = account_balance_by_type.plot(kind='bar', x='account_type', y='balance', color='lightblue')
                st.pyplot(plt.gcf())


                transaction_data['transaction_date'] = pd.to_datetime(transaction_data['transaction_date'])

                st.header("Transactions")
                st.write(transaction_data)


                st.subheader("Transaction Amounts Over Time (Line Chart)")
                transaction_over_time = transaction_data.groupby('transaction_date')['amount'].sum().reset_index()
                plt.figure(figsize=(10, 5))
                sns.lineplot(data=transaction_over_time, x='transaction_date', y='amount', color='green')
                plt.title('Transaction Amounts Over Time')
                st.pyplot(plt.gcf())

                st.subheader("Monthly Transaction Volume (Area Chart)")
                transaction_data['month'] = transaction_data['transaction_date'].dt.to_period('M')
                monthly_transaction_volume = transaction_data.groupby('month')['transaction_id'].count().reset_index()
                monthly_transaction_volume['month'] = monthly_transaction_volume['month'].dt.to_timestamp()  # Convert period to timestamp for plotting
                st.area_chart(monthly_transaction_volume.set_index('month'))

                st.subheader("Account Balance Distribution (Pie Chart)")
                plt.figure(figsize=(7, 7))
                plt.pie(account_data['balance'], labels=account_data['account_type'], autopct='%1.1f%%', startangle=140, colors=sns.color_palette("Set3"))
                plt.axis('equal')  
                st.pyplot(plt.gcf())

                st.subheader("Top 5 Accounts by Balance (Bar Chart)")
                top_accounts = account_data.nlargest(5, 'balance')[['account_id', 'balance']].set_index('account_id')
                top_accounts_chart = top_accounts.plot(kind='barh', color='coral')
                plt.title("Top 5 Accounts by Balance")
                st.pyplot(plt.gcf())


                st.subheader("Transaction Type Distribution (Pie Chart)")
                transaction_type_dist = transaction_data['transaction_type'].value_counts()
                plt.figure(figsize=(7, 7))
                plt.pie(transaction_type_dist, labels=transaction_type_dist.index, autopct='%1.1f%%', startangle=90, colors=sns.color_palette("pastel"))
                plt.axis('equal') 
                st.pyplot(plt.gcf())

                st.subheader("Transactions by Account (Area Chart)")
                transactions_by_account = transaction_data.groupby('account_id')['amount'].sum().reset_index()
                st.area_chart(transactions_by_account.set_index('account_id'))
                            
        with st.sidebar:
            on=st.toggle("View Conversation History")
            if on:
                for role, text in st.session_state['chat_history']:
                    st.write(f"{role}: {text}")

        with st.sidebar:
            on=st.toggle("View Logs")
            if on:
                st.title("Logs")
                last_lines = read_last_lines("app.log", 5)
                st.text(last_lines)
        
        with st.sidebar:
            
            st.write("*`Developed by Ayon`*")
    
if __name__ == "__main__":
    main()
