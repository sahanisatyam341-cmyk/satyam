import json
import os
import re
import time

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
from supabase import create_client

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
MAX_HISTORY = 20       # last N messages model ko bhejte hain
MAX_PROMPT_CHARS = 2000
RATE_MAX_MSGS = 15     # itne messages...
RATE_WINDOW_SEC = 60   # ...itne seconds me

st.set_page_config(page_title="Satyam", page_icon="🤝", layout="centered")


# ---------- Helpers ----------
def secret(name, default=""):
    """Pehle Streamlit secrets, phir .env / environment se value uthata hai."""
    try:
        val = st.secrets[name]
    except Exception:
        val = os.getenv(name, default)
    # key ke andar ya aage-peeche ke saare space, line break aur quote hata deta hai
    return "".join(str(val).split()).strip('"').strip("'")


def check_rate_limit():
    now = time.time()
    times = [t for t in st.session_state.get("msg_times", []) if now - t < RATE_WINDOW_SEC]
    if len(times) >= RATE_MAX_MSGS:
        st.session_state.msg_times = times
        return False
    times.append(now)
    st.session_state.msg_times = times
    return True


def clean_for_speech(text):
    """Bolne se pehle markdown, code block aur emoji hata deta hai."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[*_`#>~|]", "", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def speak_button(text, rate=1.0):
    """Browser ki apni awaaz se jawab bolta hai (dobara dabane pe rukta hai)."""
    spoken = clean_for_speech(text)
    if not spoken:
        return
    lang = "hi-IN" if re.search(r"[\u0900-\u097F]", spoken) else "en-IN"
    payload = json.dumps({"text": spoken, "lang": lang, "rate": rate}).replace("</", "<\\/")
    components.html(
        f"""
        <button id="b" style="font:15px sans-serif;padding:6px 14px;
          border:1px solid #bbb;background:#fff;border-radius:20px;cursor:pointer;">
          🔊 Suno</button>
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


# ---------- Supabase (har user ka apna client, share nahi hota) ----------
def get_sb():
    if "sb" not in st.session_state:
        url, key = secret("SUPABASE_URL"), secret("SUPABASE_KEY")
        if not url or not key:
            st.error("SUPABASE_URL aur SUPABASE_KEY secrets mein daal pehle bhai.")
            st.stop()
        st.session_state.sb = create_client(url, key)
    return st.session_state.sb


# ---------- Chats / Messages (hamesha sirf apne user_id ka data) ----------
def list_chats():
    uid = st.session_state.user.id
    res = (
        get_sb()
        .table("chats")
        .select("id,title")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def load_messages(chat_id):
    uid = st.session_state.user.id
    res = (
        get_sb()
        .table("messages")
        .select("role,content")
        .eq("chat_id", chat_id)
        .eq("user_id", uid)
        .order("id")
        .execute()
    )
    return res.data or []


def create_chat(title):
    uid = st.session_state.user.id
    res = get_sb().table("chats").insert({"title": title[:40], "user_id": uid}).execute()
    return res.data[0]["id"]


def save_messages(chat_id, rows):
    uid = st.session_state.user.id
    get_sb().table("messages").insert(
        [{"chat_id": chat_id, "role": r, "content": c, "user_id": uid} for r, c in rows]
    ).execute()


def delete_chat(chat_id):
    uid = st.session_state.user.id
    get_sb().table("chats").delete().eq("id", chat_id).eq("user_id", uid).execute()


# ---------- Login / Signup ----------
def auth_screen():
    st.title("Satyam 🤝")
    st.caption("Tera AI dost, jo seedha aur sahi jawab de")
    tab_login, tab_signup = st.tabs(["Login", "Signup"])
    sb = get_sb()

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login", type="primary"):
            if not email or not password:
                st.warning("Email aur password dono daal bhai.")
            else:
                try:
                    res = sb.auth.sign_in_with_password(
                        {"email": email.strip(), "password": password}
                    )
                    st.session_state.user = res.user
                    st.rerun()
                except Exception as e:
                    st.error(f"Login nahi hua: {e}")

    with tab_signup:
        email = st.text_input("Email", key="su_email")
        password = st.text_input("Password (kam se kam 6 akshar)", type="password", key="su_pw")
        if st.button("Account bana"):
            if not email or len(password) < 6:
                st.warning("Sahi email daal aur password kam se kam 6 akshar ka rakh.")
            else:
                try:
                    res = sb.auth.sign_up({"email": email.strip(), "password": password})
                    if res.session:  # email confirm band hai toh seedha login
                        st.session_state.user = res.user
                        st.rerun()
                    else:
                        st.success(
                            "Account ban gaya! Email pe confirm link aaya hoga, "
                            "usse confirm karke login kar."
                        )
                except Exception as e:
                    st.error(f"Signup nahi hua: {e}")


if "user" not in st.session_state:
    auth_screen()
    st.stop()

# ---------- Main app ----------
st.title("Satyam 🤝")
st.caption("Tera AI dost, jo seedha aur sahi jawab de")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_id" not in st.session_state:
    st.session_state.chat_id = None  # None = nayi chat, pehle message pe ban jayegi

# ---------- Sidebar ----------
with st.sidebar:
    st.caption(f"👤 {st.session_state.user.email}")

    if st.button("➕ Nayi chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_id = None
        st.rerun()

    st.subheader("Purani chats")
    try:
        chats = list_chats()
    except Exception as e:
        chats = []
        st.error(f"Chats load nahi hui: {e}")

    if not chats:
        st.caption("Abhi koi chat nahi hai. Pehla message bhej! 😉")

    for c in chats:
        col1, col2 = st.columns([5, 1])
        is_open = c["id"] == st.session_state.chat_id
        if col1.button(
            ("▶ " if is_open else "") + c["title"],
            key=f"open_{c['id']}",
            use_container_width=True,
        ):
            st.session_state.chat_id = c["id"]
            st.session_state.messages = load_messages(c["id"])
            st.rerun()
        if col2.button("🗑", key=f"del_{c['id']}"):
            delete_chat(c["id"])
            if is_open:
                st.session_state.chat_id = None
                st.session_state.messages = []
            st.rerun()

    st.divider()
    with st.expander("Settings"):
        provider = st.selectbox("Provider", list(PROVIDERS.keys()), index=0)
        base_url, key_env, models = PROVIDERS[provider]

        # Server pe key hai toh use chhupa ke rakhte hain, user ko dikhate nahi
        server_key = secret(key_env)
        if server_key:
            api_key = server_key
            st.caption("✅ API key set hai")
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

    if st.button("Logout", use_container_width=True):
        try:
            get_sb().auth.sign_out()
        except Exception:
            pass
        st.session_state.clear()
        st.rerun()

# ---------- History ----------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            speak_button(msg["content"])

if not api_key:
    st.warning(f"Sidebar > Settings mein API key daal pehle bhai (ya secrets mein {key_env} daal).")
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
if raw_prompt := st.chat_input("Satyam se baat kar..."):
    prompt = raw_prompt.strip()[:MAX_PROMPT_CHARS]

    if not prompt:
        st.warning("Khaali message nahi bhej sakte bhai 😄")
    elif not check_rate_limit():
        st.error("Thoda aaram se! Bahut jaldi-jaldi messages aa rahe hain, thodi der ruk ke bhej.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        to_send = [{"role": "system", "content": SATYAM_SYSTEM_PROMPT}] + [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[-MAX_HISTORY:]
        ]

        with st.chat_message("assistant"):
            try:
                reply = st.write_stream(stream_reply(to_send))
                st.session_state.messages.append({"role": "assistant", "content": reply})
                speak_button(reply)

                # jawab aa gaya, ab database mein save karo
                try:
                    is_new = st.session_state.chat_id is None
                    if is_new:
                        st.session_state.chat_id = create_chat(prompt)
                    save_messages(
                        st.session_state.chat_id,
                        [("user", prompt), ("assistant", reply)],
                    )
                    if is_new:
                        st.rerun()  # sidebar mein nayi chat dikhane ke liye
                except Exception as e:
                    st.warning(f"Chat save nahi ho payi: {e}")

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
                st.error(f"Model `{model}` nahi mila. Settings mein koi aur model chun ya naam check kar.")
                st.session_state.messages.pop()
            except RateLimitError:
                st.error("API provider ki limit khatam ho gayi. Thodi der ruk ke try kar.")
                st.session_state.messages.pop()
            except Exception as e:
                st.error(f"Kuch gadbad ho gayi: {e}")
                st.session_state.messages.pop()
    
