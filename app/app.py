import streamlit as st
from ui_components import *


def main():
    st.title("AI-powered Job Search Agent")

    # Initialize session state for navigation
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "login"  # Default to login page
    
    # Page mapping
    pages = {
        "login": login_form,
        "register": registration_form,
        "user_details": user_details_form,
        "job_search": job_search_form
    }

    # Display the current page
    pages[st.session_state.current_page]()


if __name__ == "__main__":
    main()