import time
import os
import json

import requests
from predictionguard import PredictionGuard
import streamlit as st
from langchain.prompts import PromptTemplate



client=PredictionGuard(api_key="SWT94mdIFk8BXXNVloFKH6x6MjbEk6Y51xiVBCkr")

#--------------------------#
# Login to Application     #
#--------------------------#
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error(":confused: Password incorrect")
        return False
    else:
        # Password correct.
        return True

#---------------------#
# Authentication      #
#---------------------#
if "login" not in st.session_state:
    st.session_state["login"] = False
if not check_password():
    st.stop()

#--------------------------#
# Prompt template          #
#--------------------------#

def demo_prompt(messages):

  for m in messages:
    if m['role'] == 'system':
      system_prompt = m['content']
      break

  prompt = '### System:\n' + system_prompt

  for m in messages:
    if m['role'] != 'system':
      if m['role'] == 'user':
        prompt = prompt + '### User:\n' + m['content'] + '\n'
      else:
        prompt = prompt + '### Assistant:\n' + m['content'] + '\n'

  prompt = prompt + '### Assistant:\n'
  return prompt

qa_template = """
Provide a concise and clear response without repeating information. Do not repeate yourself, if you have answered the question fully, stop outputing. Do not mention context or system."
 
Context: "{context}"
 
Question: "{query}"
"""
 
qa_prompt = PromptTemplate(
    input_variables=["context", "query"],
    template=qa_template
)


#---------------------#
# Streamlit config    #
#---------------------#

#st.set_page_config(layout="wide")

# Hide the hamburger menu
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


#--------------------------#
# RAG setup                #
#--------------------------#

def rag_answer(question, table):

    url = 'http://localhost:8000/' + '/answers'
    print(url)

    payload = json.dumps({
        "query": question,
        "table": table,
        "max_tokens": 2000,
        "temperature": .1,
    })
    headers = {
        'Content-Type': 'application/json'
    }
    print(payload)

    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.json())
    print(f" num 2{response.json()['answer']}")
    return response.json()['answer'], response.json()['injected_doc'],response.json()['metadata']


#--------------------------#
# Streamlit sidebar        #
#--------------------------#

logo_path = "logo.svg"  
st.sidebar.image(logo_path, width=200, use_column_width=False)

st.sidebar.markdown(
    "This chat interface uses [Prediction Guard](https://www.predictionguard.com) to answer questions based on uploaded Cultura documents."
)

model = "Hermes-3-Llama-3.1-8B"

st.sidebar.markdown("## 🛡️ Input Filters")
pii = st.sidebar.checkbox("PII", value=False)
injection = st.sidebar.checkbox("Prompt Injection", value=False)

st.sidebar.markdown("## 📝 Output checks")
factuality = st.sidebar.checkbox("Factuality", value=False)
toxicity = st.sidebar.checkbox("Toxicity", value=False)


#--------------------------#
# Streamlit app            #
#--------------------------#

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message(message["role"], avatar="person.png"):
            st.markdown(message["content"])
    else:
        with st.chat_message(message["role"], avatar="rook.png"):
            st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="person.png"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="rook.png"):
        message_placeholder = st.empty()
        full_response = ""

        # Check for PII
        if pii:
            with st.spinner("Checking for PII..."):
                pii_response = client.pii.check(
                    prompt=prompt,
                    replace=False,
                    replace_method="fake"
                )
                if "[" in pii_response['checks'][0]['pii_types_and_positions']:
                    pii_result = True
                    completion = "Warning! PII detected. Please avoid using personal information."
                else:
                    pii_result = False
        else:
            pii_result = False

        # Check for injection
        if injection:
            with st.spinner("Checking for security vulnerabilities..."):
                injection_response = client.injection.check(
                    prompt=prompt,
                    detect=True
                )
                if injection_response['checks'][0]['probability'] > 0.5:
                    injection_result = True
                    completion = "Warning! Security vulnerabilities detected. Please avoid using malicious prompts."
                else:
                    injection_result = False
        else:
            injection_result = False

        # generate response
        with st.spinner("Thinking..."):
            if not pii_result and not injection_result:
                completion, doc_use, metadata = rag_answer(prompt, 'ConfluenceData')

        fact_score = 0.0
        if factuality:
            if doc_use != "":
                fact_score = client.factuality.check(
                    reference=doc_use,
                    text=completion
                )['checks'][0]['score']*100.0
            else:
                fact_score = 0.0
        
        toxicity_score = 0.0
        if toxicity:
            toxicity_score = client.toxicity.check(
                text=completion
            )['checks'][0]['score']*100.0
        if toxicity_score > 75.0:
            completion= "[response censored]"

        for token in completion.split(" "):
            full_response += " " + token
            message_placeholder.markdown(full_response + "▌")
            time.sleep(0.075)

        if fact_score > 70.0:
            full_response += "\n\n**✅ Probability of being factual:** " + str("%0.1f" % fact_score) + "%"
        elif fact_score and fact_score <= 70.0 and fact_score > 0.0:
            full_response += "\n\n**⚠️ Probability of being factual:** " + str("%0.1f" % fact_score) + "%"
        elif fact_score == 0.0 and factuality:
            full_response += "\n\n**⚠️ Probability of being factual:** Could not check against external data."

        if toxicity_score > 75.0:
            full_response += "\n\n**⚠️ Probability of being toxic:** " + str("%0.1f" % toxicity_score) + "%"
        elif toxicity_score and toxicity_score <= 75.0 and toxicity:
            full_response += "\n\n**✅ Probability of being toxic:** " + str("%0.1f" % toxicity_score) + "%"

        full_response += f"\n\nLink:[{metadata}]({metadata})"

        message_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})