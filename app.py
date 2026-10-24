import json
import os
import re

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)

from satyam_prompt import SATYAM_SYSTEM_PROMPT

load_dotenv()

# Provider -> (base_url, env var for key, suggested models)
PROVIDERS = {
    "Groq": (
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
        ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"],
    ),
    "OpenRouter": (
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        ["meta-llama/llama-3.3-70b-instruct"],
    ),
    "Together": (
        "https://api.together.xyz/v1",
        "TOGETHER_API_KEY",
        ["meta-llama/Llama-3.3-70B-Instruct-Turbo"],
    ),
}
MAX_HISTORY = 20  # last N messages bhejte hain, taaki lamba chat na phate

st.set_page_config(page_title="Satyam", page_icon="🤝", layout="centered")
st.title("Satyam 🤝")
st.caption("Tera AI dost, jo seedha aur sahi jawab de")


def clean_for_speech(text):
    """Markdown ke symbols aur emoji hata deta hai, taaki awaaz saaf bole."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[`*_#>~|]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def speak_button(text, rate=1.0):
    """Browser ki apni awaaz se jawab bolta hai (free, koi extra key nahi)."""
    spoken = clean_for_speech(text)
    if not spoken:
        return
    lang = "hi-IN" if re.search(r"[\u0900-\u097F]", spoken) else "en-IN"
    payload = json.dumps({"text": spoken, "lang": lang, "rate": rate}).replace("</", "<\\/")
    components.html(
        f"""
        <button id="b" style="font:15px sans-serif;padding:6px 14px;border-radius:18px;
                border:1px solid #bbb;background:#f6f6f8;cursor:pointer;">🔊 Suno</button>
        <script>
        const d = {payload};
        const b = document.getElementById("b");
        const synth = window.speechSynthesis;
        function reset() {{ b.textContent = "🔊 Suno"; }}
        b.onclick = () => {{
          if (synth.speaking) {{ synth.cancel(); reset(); return; }}
          const parts = d.text.match(/[^.!?।]+[.!?।]*/g) || [d.text];
          b.textContent = "⏹ Ruko";
          parts.forEach((p, i) => {{
            const u = new SpeechSynthesisUtterance(p.trim());
            u.lang = d.lang; u.rate = d.rate;
            if (i === parts.length - 1) u.onend = reset;
            synth.speak(u);
          }});
        }};
        </script>
        """,
        height=44,
    )


if "messages" not in st.session_state:
    st.session_state.messages = []  # sirf user/assistant, system prompt bhejte waqt judta hai

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Settings")
    provider = st.selectbox("Provider", list(PROVIDERS.keys()), index=0)
    base_url, key_env, models = PROVIDERS[provider]

    # Server pe secret mein key ho toh usse box mein kabhi mat dikha (public link se leak ho jati hai)
    api_key = os.getenv(key_env, "")
    if api_key:
        st.success(f"{provider} ki key set hai ✅")
    else:
        api_key = st.text_input(f"API Key ({key_env})", type="password")
    model = st.selectbox("Model", models, index=0)
    custom_model = st.text_input(
        "Ya apna model naam likh (optional)",
        help="Agar upar wala model band ho gaya ho toh yahan naya naam daal.",
    ).strip()
    if custom_model:
        model = custom_model

    temperature = st.slider("Temperature (mazaa)", 0.3, 1.2, 0.7, 0.05)
    voice_on = st.toggle("🔊 Bolne ka button dikha", value=True)
    voice_rate = st.slider("Awaaz ki speed", 0.7, 1.4, 1.0, 0.05)

    if st.button("Chat clear kar"):
        st.session_state.messages = []
        st.rerun()

# ---------- History ----------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if voice_on and msg["role"] == "assistant":
            speak_button(msg["content"], voice_rate)

if not api_key:
    st.warning(f"Sidebar mein API key daal pehle bhai (ya .env mein {key_env} daal).")
    st.stop()

client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)


def stream_reply(messages):
    """Tokens yield karta hai taaki jawab dheere-dheere likhta dikhe."""
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=2048,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ---------- Chat ----------
if prompt := st.chat_input("Satyam se baat kar..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    to_send = [{"role": "system", "content": SATYAM_SYSTEM_PROMPT}] + st.session_state.messages[-MAX_HISTORY:]

    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(stream_reply(to_send))
            st.session_state.messages.append({"role": "assistant", "content": reply})
            if voice_on:
                speak_button(reply, voice_rate)
        except APIConnectionError:
            st.error("Net nahi chal raha bhai 😅 Connection check kar, phir dobara bhej.")
            st.session_state.messages.pop()
        except APITimeoutError:
            st.error("Server ne bahut der laga di. Thodi der baad try kar.")
            st.session_state.messages.pop()
        except AuthenticationError:
            st.error("API key galat hai ya expire ho gayi. Nayi key bana ke daal.")
            st.session_state.messages.pop()
        except NotFoundError:
            st.error(f"Model `{model}` nahi mila. Sidebar mein koi aur model chun ya naam check kar.")
            st.session_state.messages.pop()
        except RateLimitError:
            st.error("Limit khatam ho gayi (rate limit). Thodi der ruk ke try kar.")
            st.session_state.messages.pop()
        except Exception as e:  # koi aur gadbad
            st.error(f"Kuch gadbad ho gayi: {e}")
            st.session_state.messages.pop()
