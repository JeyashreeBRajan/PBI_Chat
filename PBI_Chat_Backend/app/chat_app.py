# chat_app.py
import streamlit as st
import pandas as pd
from interactive_executor import fetch_dax_from_api, execute_dax_interactive

import logging
import sys
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# -----------------------------
# Page Config - Sidebar Look
# -----------------------------
st.set_page_config(
    page_title="Chat with Power BI",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Inject custom CSS to mimic Copilot sidebar
st.markdown(
    """
    <style>
    .block-container {
        max-width: 420px;
        margin-left: auto;
        margin-right: 0;
        padding: 1rem;
        border-left: 1px solid #ddd;
        background-color: #fafafa;
        height: 100vh;
    }
    .stChatMessage {
        padding: 0.6rem 0.8rem;
        border-radius: 10px;
        margin-bottom: 0.6rem;
    }
    .stChatMessage.user {
        background-color: #0078d4;
        color: white;
        text-align: right;
    }
    .stChatMessage.assistant {
        background-color: white;
        border: 1px solid #e5e5e5;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🤖 Chat with Your Power BI Report")

# -----------------------------
# State for Chat History
# -----------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# -----------------------------
# Chat Input
# -----------------------------
user_input = st.chat_input("I am an AI-powered chat assistant. Ask a question about your dataset...")

if user_input:
    # Save user message
    st.session_state["messages"].append({
        "role": "user",
        "content": user_input
    })

    logger.info(f"🟢 Sending question to API: {user_input}")
    response = fetch_dax_from_api(user_input)

    # If no DAX generated
    if not response.get("dax"):
        st.session_state["messages"].append({
            "role": "assistant",
            "content": {
                "answer": response.get("answer", "⚠️ Could not generate a DAX query."),
                "suggestions": response.get("suggestions", [])
            }
        })
    else:
        dax_query = response["dax"]
        try:
            # Execute DAX
            columns, data = execute_dax_interactive(dax_query)
            df = pd.DataFrame(data, columns=columns)

            # Save assistant response
            st.session_state["messages"].append({
                "role": "assistant",
                "content": {
                    "answer": response.get("answer", "Here’s your query result 👇"),
                    "dax": dax_query,
                    "data": df
                }
            })
        except Exception as e:
            st.session_state["messages"].append({
                "role": "assistant",
                "content": {"answer": f"❌ Error executing DAX: {e}"}
            })

# -----------------------------
# Chat Display
# -----------------------------
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            content = msg["content"]
            st.write(content["answer"])

            # Suggestions
            if "suggestions" in content and content["suggestions"]:
                st.write("👉 Did you mean:")
                for s in content["suggestions"]:
                    if st.button(s, key=f"suggestion_{s}"):
                        st.session_state["messages"].append({"role": "user", "content": s})
                        st.rerun()

            # Show DAX
            if "dax" in content:
                with st.expander("🔎 View generated DAX query"):
                    st.code(content["dax"], language="DAX")

            # Show results
            if "data" in content and not content["data"].empty:
                st.dataframe(content["data"], use_container_width=True)
