import streamlit as st
from PIL import Image

st.title("Database Schema")

image = Image.open("pages\SampleSakila.png")
st.image(image, caption='Sakila Schema')

with open ("pages\SampleSakila.png", "rb") as file:
    btn = st.download_button(
        label="download image",
        data=file,
        file_name="pages\SampleSakila.png",
        mime = "image/png"

    )

st.write("For more information about database, visit the link below")
st.link_button("Go to database information", "https://dev.mysql.com/doc/sakila/en/sakila-structure.html")