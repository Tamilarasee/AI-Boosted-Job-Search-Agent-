import streamlit as st
from ui_components import login_form, registration_form, job_preferences_form, career_insights_page # Adjust imports as needed
import time # If you use time.sleep

# Set page config as the first Streamlit command
st.set_page_config(layout="wide")

# --- THIS NAVIGATION HANDLING BLOCK MUST BE HERE ---
query_params = st.query_params
if "action" in query_params:
    action = query_params.get("action")
    page_changed = False
    if action == "register" and st.session_state.get("current_page") != "register":
        st.session_state.current_page = "register"
        page_changed = True
    elif action == "login" and st.session_state.get("current_page") != "login":
        st.session_state.current_page = "login"
        page_changed = True

    if page_changed:
        st.query_params.clear() # Clear the action param to prevent loop
        st.rerun() # Rerun to load the new page
# --- END NAVIGATION HANDLING BLOCK ---

# --- SESSION STATE INITIALIZATION (If needed here) ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "login" # Default page
# --- END SESSION STATE INITIALIZATION ---

def main():
    # Define title text
    app_title = "AI-Boosted Job Search Agent"

    # Conditionally set title size based on the page
    if st.session_state.current_page in ["login", "register"]:
        # Use larger header (h1) for login/register
        st.markdown(f"<h1 style='text-align: center;'>{app_title}</h1>", unsafe_allow_html=True)
    elif st.session_state.current_page in ["job_preferences", "career_insights"]:
        # Use smaller header (h3) for other pages
        st.markdown(f"<h3 style='text-align: center;'>{app_title}</h3>", unsafe_allow_html=True)
    else:
        # Default fallback
        st.markdown(f"<h1 style='text-align: center;'>{app_title}</h1>", unsafe_allow_html=True)

    # Initialize session state for navigation
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "login"  # Default to login page
    
    # Page mapping
    pages = {
        "login": login_form,
        "register": registration_form,
        "job_preferences": job_preferences_form,
        "career_insights": career_insights_page
    }

    # Display the current page
    pages[st.session_state.current_page]()


if __name__ == "__main__":
    main()