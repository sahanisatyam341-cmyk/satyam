# Satyam 🤝

Ek simple AI chat app jo Streamlit pe bana hai. Jis bhasha mein tu likhe (Hindi, Hinglish, English) usi mein seedha, honest aur helpful jawab deta hai.

## Features

- Hinglish / Hindi / English, jo bhi tu bole
- Groq, OpenRouter aur Together AI support (OpenAI-compatible API)
- Jawab dheere-dheere likhta dikhta hai (streaming)
- Net, key, model ya rate limit ki dikkat par saaf message, crash nahi
- Sidebar mein provider, model aur temperature badal sakte ho
- Model band ho jaye toh apna model naam daal sakte ho

## Project structure

```
satyam/
├── app.py              # Streamlit UI aur chat logic
├── satyam_prompt.py    # Satyam ka system prompt
├── requirements.txt    # Python packages
├── .env.example        # API key ka template
├── .gitignore
├── LICENSE
└── README.md
```

## Setup

```bash
git clone https://github.com/<tera-username>/satyam.git
cd satyam
pip install -r requirements.txt
cp .env.example .env
```

`.env` mein apni key daal, `=` ke turant baad (beech mein space ya quotes nahi):

```
GROQ_API_KEY=gsk_...
```

Free Groq key: https://console.groq.com

## Run

```bash
streamlit run app.py
```

Browser mein `http://localhost:8501` khol.

## Notes

- `.env` kabhi GitHub pe upload mat karna. `.gitignore` ise already bahar rakhta hai.
- Satyam ek AI hai aur galti kar sakta hai. Zaroori cheezein ek baar khud bhi check kar lena.

## License

MIT, details `LICENSE` file mein.
