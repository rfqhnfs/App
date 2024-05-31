import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import AzureChatOpenAI
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv
load_dotenv()

# Initialize LLM
llm = AzureChatOpenAI(
    deployment_name=os.getenv('deployment_name'),
    openai_api_version=os.getenv('openai_api_version'),
    openai_api_key=os.getenv('openai_api_key'),
    azure_endpoint=os.getenv('azure_endpoint')
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


# Define chat prompt template for generate sql query
db_template = """
Dibawah ini adalah sebuah database schema, tulislah MySQL query berdasarkan text yang diinput, selalu nama tabel ketika memilih kolom untuk menghindari ambiguitas.
Kamu harus menimbang Message History ketika membuat SQL query untuk berjaga-jaga jika pertanyaan tersebut adalah follow-up question:
{schema}

Question: {question}
Message History: {history_message}
SQL Query:
"""
db_prompt = ChatPromptTemplate.from_template(db_template)

# Define chat prompt template for natural language response
sql_template = """
Berdasarkan table schema, sql qeury, dan sql response dibawah ini, buatlah sebuah respon untuk merespon dari semua input yang ada.
{schema}

Question: {question}
SQL Query: {query}
SQL Response: {response}
respon:
"""
sql_prompt = ChatPromptTemplate.from_template(sql_template)

# Create chain for generate sql query
sql_chain = (
    db_prompt
    | llm.bind(stop="\nSQL Result:")
    | StrOutputParser()
)

# Create chain for generate natural language response
full_chain = (
    sql_prompt
    | llm
    | StrOutputParser()
)

# create table to store question and answer
if "riwayat" not in st.session_state:
    st.session_state.riwayat = pd.DataFrame(columns=['questions', 'answers'])


########################## MAIN APP #####################################
st.set_page_config(
    page_title="DATABOT"
)
st.title("Main Page")

# display sidebar
with st.sidebar:
    st.subheader("Settings")
    st.write("Connect to the database and start chatting.")
    
    st.text_input("Host", value="localhost", key="Host")
    st.text_input("Port", value="3306", key="Port")
    st.text_input("User", value="root", key="User")
    st.text_input("Password", type="password", value="123456r", key="Password")
    st.text_input("Database", value="sakila", key="Database")
    
    if st.button("Connect"):
        with st.spinner("Connecting to database..."):
            # Connect to database
            cnx = mysql.connector.connect(
                host=st.session_state["Host"],
                user=st.session_state["User"],
                port = st.session_state["Port"],
                password=st.session_state["Password"],
                database=st.session_state["Database"]
            )

            # get database schema
            db = SQLDatabase.from_uri(f"mysql+mysqlconnector://{st.session_state['User']}:{st.session_state['Password']}@{st.session_state['Host']}:{st.session_state['Port']}/{st.session_state['Database']}")
            db_schema = db.get_table_info()
            st.session_state.db_schema = db_schema
            st.session_state.cnx = cnx
            st.session_state.db = db
            st.success("Connected to database!")

# Accept user input
user_input = st.chat_input("Enter your message:")


if user_input:
    st.session_state.messages.append({"role": "User", "content": user_input})
    questions = user_input

    # run the first chain (generate sql query)
    with st.spinner("Processing..."):
        query_response = sql_chain.invoke({"schema": st.session_state.db_schema, "question": user_input, "history_message": st.session_state.riwayat})
        st.session_state.messages.append({"role": "Chatbot (SQL Response)", "content": query_response})

        # Execute generated query and get response
        cursor = st.session_state.cnx.cursor()
        if "UPDATE" not in query_response:
            cursor.execute(query_response)
            df = pd.DataFrame(cursor.fetchall(), columns=cursor.column_names)
            st.session_state.messages.append({"role": "Database Output", "content": df})
            # run second chain to generate natural language response
            natural_response = full_chain.invoke({"question": user_input, "query": query_response, "response": df, "schema": st.session_state.db_schema})
            st.session_state.messages.append({"role": "Chatbot (Natural Language Response)", "content": natural_response})
        else:
            natural_response = "Tidak dapat merubah isi database"
            df = []
            st.session_state.messages.append({"role": "Chatbot (Natural Language Response)", "content": natural_response})
        answers = natural_response
    if len(st.session_state.riwayat) < 10:
        st.session_state.riwayat.loc[len(st.session_state.riwayat.index)] = [questions, answers]
    else:
        st.session_state.riwayat = st.session_state.riwayat.drop(index=0).reset_index(drop=True)
        st.session_state.riwayat.loc[len(st.session_state.riwayat.index)] = [questions, answers]

# Display chat history
for message in st.session_state.messages:
    if message["role"] == "User":
        st.session_state.messages.append({"role": "user", "content": message["content"]})
        with st.chat_message("user"):
            st.markdown(message["content"])

    elif message["role"] == "Chatbot (SQL Response)":
        st.session_state.messages.append({"role": "assistant", "content": message["content"]})
        with st.chat_message("assistant"):
            st.code(message["content"], language="sql")

    elif message["role"] == "Database Output":
        st.session_state.messages.append({"role": "assistant", "content": message["content"]})
        with st.chat_message("assistant"):
            st.dataframe(message["content"],use_container_width=True)

    elif message["role"] == "Chatbot (Natural Language Response)":
        st.session_state.messages.append({"role": "assistant", "content": message["content"]})
        with st.chat_message("assistant"):
            st.write("Response:")
            st.write(message["content"])

