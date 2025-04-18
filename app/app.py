import streamlit as st
from ui_components import login_form, registration_form, job_preferences_form, career_insights_page, resume_management_page, translate_audio_bytes_to_english # Adjust imports as needed
import time # If you use time.sleep
from dotenv import load_dotenv # Import dotenv
import os # Import os if not already

# --- Load Environment Variables ---
load_dotenv() # Make sure this runs early

# Set page config - initial state auto
st.set_page_config(layout="wide", initial_sidebar_state="auto")

# --- THIS NAVIGATION HANDLING BLOCK MUST BE HERE ---
query_params = st.query_params
if "action" in query_params:
    action = query_params.get("action")
    page_changed = False
    # Only allow these actions if NOT logged in
    if not st.session_state.get("user_id"):
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

# --- Page Definitions ---
pages = {
    "login": login_form,
    "register": registration_form,
    "resume_management": resume_management_page,
    "job_preferences": job_preferences_form,
    "career_insights": career_insights_page,
}

# --- Main App Logic ---
def main():
    # --- SESSION STATE INITIALIZATION (Moved inside main) ---
    default_session_state = {
        "current_page": "login",
        "user_id": None,
        "auth_token": None,
        "suggested_titles": [],
        "extracted_skills": [],
        "pref_text_area_value": "",
        "resume_upload_success": False,
        "just_processed_audio": False,
        # Add user_email if you plan to display it after login
        "user_email": None
    }
    for key, default_value in default_session_state.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    # --- END SESSION STATE INITIALIZATION ---

    # No global title here anymore

    # --- AUTHENTICATED VIEW (with Sidebar) ---
    if st.session_state.user_id:
        # Ensure current page is valid for logged-in user
        if st.session_state.current_page not in ["resume_management", "job_preferences", "career_insights"]:
             st.session_state.current_page = "resume_management" # Default to resume page maybe?

        # --- Sidebar Navigation ---
        with st.sidebar:
            # Add Sidebar Title
            st.title("AI-Boosted Job Search Agent") # Use st.title for sidebar main heading
            # Removed Navigation Header

            # Determine button types
            resume_type = "primary" if st.session_state.current_page == "resume_management" else "secondary"
            profile_type = "primary" if st.session_state.current_page == "job_preferences" else "secondary"
            insights_type = "primary" if st.session_state.current_page == "career_insights" else "secondary"

            # Updated Button Labels
            if st.button("📄 Upload Resume", use_container_width=True, type=resume_type):
                if st.session_state.current_page != "resume_management":
                    st.session_state.current_page = "resume_management"
                    st.rerun()

            if st.button("🔍 Search Jobs", use_container_width=True, type=profile_type):
                if st.session_state.current_page != "job_preferences":
                    st.session_state.current_page = "job_preferences"
                    st.rerun()

            if st.button("📈 Career Insights", use_container_width=True, type=insights_type):
                 if st.session_state.current_page != "career_insights":
                    st.session_state.current_page = "career_insights"
                    st.rerun()

            # --- Spacer to push logout down ---
            st.markdown("<br>" * 10, unsafe_allow_html=True) # Adjust multiplier for spacing
            # --- End Spacer ---

            # --- Logout Section (Moved to Bottom) ---
            st.divider()
            
            if st.button("🚪 Logout", use_container_width=True):
                # Clear all session state keys on logout
                keys_to_clear = list(st.session_state.keys()) # Get keys before iterating
                for key in keys_to_clear:
                    # Optionally keep some keys if needed, e.g., theme settings
                    del st.session_state[key]

                # Re-initialize minimal state for login page
                st.session_state.current_page = "login"
                st.session_state.user_id = None # Explicitly set logged out state
                st.success("Logged out successfully.")
                time.sleep(1)
                st.rerun()

        # --- Main Page Area (Authenticated) ---
        # Use smaller header for authenticated pages
        if st.session_state.current_page in pages:
            pages[st.session_state.current_page]()
        else:
            st.error("Page not found.") # Should not happen if state is managed correctly
            st.session_state.current_page = "resume_management" # Reset to default
            st.rerun()


    # --- UNAUTHENTICATED VIEW (Login/Register) ---
    else:
        # Use the original large title for login/register
        app_title = "AI-Boosted Job Search Agent"
        st.markdown(f"<h1 style='text-align: center;'>{app_title}</h1>", unsafe_allow_html=True)
        # --- Add vertical space ---
        st.markdown("<br>", unsafe_allow_html=True) # Add a line break for spacing
        # --- End Add ---

        # Reset to login/register if needed
        if st.session_state.current_page not in ["login", "register"]:
             st.session_state.current_page = "login"

        # Display login or register form
        if st.session_state.current_page == "register":
            pages["register"]()
        else:
            pages["login"]()


if __name__ == "__main__":
    main()