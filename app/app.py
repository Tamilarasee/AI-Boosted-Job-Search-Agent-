import streamlit as st
from ui_components import *

# Set page config as the first Streamlit command
st.set_page_config(layout="wide")

def main():
    st.title("AI-Boosted Job Search Agent")

    # Initialize session state for navigation
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "login"  # Default to login page
    
    # Page mapping
    pages = {
        "login": login_form,
        "register": registration_form,
        "user_details": user_details_form,
        "job_preferences": job_preferences_form,
        "career_insights": career_insights_page
    }

    # Display the current page
    pages[st.session_state.current_page]()


if __name__ == "__main__":
    main()