import os
import streamlit as st
from openai import OpenAI
from satyam_prompt import SATYAM_SYSTEM_PROMPT

st.set_page_config(page_title="Satyam AI", page_icon="🤝", layout="centered")

# Simple Login
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.subheader("🔐 Satyam AI Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "satyam" and password == "baby123":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Galat username ya password hai bhai!")
    st.stop()

st.title("Satyam 🤝")
st.caption("Tera AI dost, jo seedha aur sahi jawab de")

api_key = st.sidebar.text_input("Groq API Key", type="password", value=os.getenv("GROQ_API_KEY", ""))
model = st.sidebar.selectbox("Model", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"])
temperature = st.sidebar.slider("Temperature", 0.3, 1.2, 0.7)

if st.sidebar.button("Chat clear kar"):
    st.session_state.messages = []
    st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if not api_key:
    st.warning("Pehle sidebar mein API key daal bhai.")
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1", timeout=60.0)

if prompt := st.chat_input("Satyam se baat kar..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    to_send = [{"role": "system", "content": SATYAM_SYSTEM_PROMPT}] + st.session_state.messages[-20:]

    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=to_send,
                temperature=temperature,
                max_tokens=1024,
                stream=True,
            )
            def generate():
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            reply = st.write_stream(generate())
            st.session_state.messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            st.error(f"Kuch gadbad ho gayi: {e}")
            st.session_state.messages.pop()

