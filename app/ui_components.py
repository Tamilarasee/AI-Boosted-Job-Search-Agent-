import streamlit as st
import requests

API_URL = "http://localhost:8000"

# Function for the login form
def login_form():
    st.subheader("User Login")
    with st.form(key='login_form'):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            try:
                response = requests.post(
                    f"{API_URL}/auth/login",
                    json={"email": email, "password": password}
                )
                if response.status_code == 200:
                    st.success("Login successful!")
                    st.session_state.current_page = "user_details"
                    st.rerun()
                else:
                    st.error("Login failed. Please check your credentials.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

    if st.button("Sign Up"):
        st.session_state.current_page = "register"
        
        
# Function for the registration form
def registration_form():
    st.subheader("Create a New Account")
    new_email = st.text_input("Email")
    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    register_button = st.button("Sign Up")

    if register_button:
        if new_password == confirm_password:
            # Register user with Supabase using email
            try:
                response = requests.post(
                    f"{API_URL}/auth/register",
                    json={"email": new_email, "password": new_password}
                )
                if response.status_code == 200:
                    st.success(f"Account created for: {new_email}")
                    st.success("You can now log in with your new account!")
                    st.session_state.current_page = "login"
                    st.rerun()
                else:
                    st.error("Registration failed. Please try again.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Passwords do not match. Please try again.")

    # Button to go back to login
    if st.button("Login"):
        st.session_state.current_page = "login"

def user_details_form():
    st.subheader("User Details")
    full_name = st.text_input("Full Name")
    
    resume = st.text_input("Resume Content (Copy and paste from your resume)")
    target_roles = st.text_input("Target roles (comma separated)")
    preferences = st.text_area("Instructions/Preferences")

    submit_button = st.button("Submit")

    if submit_button:
        if full_name and resume:
            try:
                response = requests.post(
                    f"{API_URL}/users/details",
                    json={
                        "name": full_name,
                        "resumes": resume,
                        "preferences": preferences,
                        "target_roles": target_roles
                    }
                )
                if response.status_code == 200:
                    st.success("Details submitted successfully!")
                    
                    # Store user data in session state for later use
                    st.session_state.user_data = {
                        "name": full_name,
                        "target_roles": target_roles,
                        "preferences": preferences
                    }
                else:
                    st.error("Failed to save user details. Please try again.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please fill in all required fields.")
    
    # Put the button outside the submit button condition, but after form processing
    if st.button("Start Job Search"):
        st.session_state.current_page = "job_search"
        st.rerun()

# def upload_resume_to_supabase(resume, user_id):
#     # Upload the resume to Supabase storage
#     file_name = f"{user_id}/{resume.name}"  # Create a unique file path
#     response = supabase.storage.from_("resumes").upload(file_name, resume)

#     if response.status_code == 200:
#         # Get the public URL of the uploaded file
#         public_url = supabase.storage.from_("resumes").get_public_url(file_name)
#         return public_url
#     else:
#         st.error("Failed to upload resume. Please try again.")
#         return None

def job_search_form():
    st.subheader("Job Search")
    
    # Get user's target roles from session if available
    default_roles = ""
    if "user_data" in st.session_state and "target_roles" in st.session_state.user_data:
        default_roles = st.session_state.user_data["target_roles"]
    
    with st.form(key="job_search_form"):
        job_title = st.text_input("Job Title", value=default_roles)
        location = st.text_input("Location", value="United States")
        description = st.text_input("Keywords in Description (optional)")
        
        submit_button = st.form_submit_button("Search Jobs")
        
    if submit_button:
        if job_title and location:
            with st.spinner("Searching for jobs..."):
                try:
                    response = requests.post(
                        f"{API_URL}/jobs/search",
                        json={
                            "title": job_title,
                            "location": location,
                            "description": description
                        }
                    )
                    
                    if response.status_code == 200:
                        jobs_data = response.json()
                        if jobs_data["success"] and "jobs" in jobs_data:
                            display_jobs(jobs_data["jobs"])
                        else:
                            st.error("No jobs found. Try different search terms.")
                    else:
                        st.error(f"Failed to search jobs. Status code: {response.status_code}")
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please enter a job title and location.")

def display_jobs(jobs_data):
    st.subheader("Jobs Found")
    
    # Show number of jobs found
    total_jobs = len(jobs_data)
    st.write(f"Found {total_jobs} matching positions")
    
    # Add filtering options
    col1, col2 = st.columns(2)
    with col1:
        sort_option = st.selectbox("Sort by", ["Date posted (newest)", "Company name", "Job title"])
    with col2:
        filter_remote = st.checkbox("Remote jobs only")
    
    # Sort the jobs based on selection
    if sort_option == "Date posted (newest)":
        jobs_data = sorted(jobs_data, key=lambda x: x.get("date_posted", ""), reverse=True)
    elif sort_option == "Company name":
        jobs_data = sorted(jobs_data, key=lambda x: x.get("organization", "").lower())
    elif sort_option == "Job title":
        jobs_data = sorted(jobs_data, key=lambda x: x.get("title", "").lower())
    
    # Filter for remote if selected
    if filter_remote:
        jobs_data = [job for job in jobs_data if job.get("remote_derived", False)]
    
    # Display each job in a card-like format
    for job in jobs_data:
        # Create a card with border
        st.markdown("---")
        
        # Job title and company in header
        title = job.get("title", "Unknown Position")
        company = job.get("organization", "Unknown Company")
        st.markdown(f"## {title}")
        
        # Company with logo if available
        col1, col2 = st.columns([1, 3])
        with col1:
            logo_url = job.get("organization_logo", "")
            if logo_url:
                st.image(logo_url, width=80)
        with col2:
            st.markdown(f"**Company:** {company}")
            
            # Location information
            locations = job.get("locations_derived", [])
            if locations:
                st.markdown(f"**Location:** {', '.join(locations)}")
            
            # Remote indicator
            if job.get("remote_derived", False):
                st.markdown("**🏠 Remote position**")
            
            # Employment type
            emp_types = job.get("employment_type", [])
            if emp_types:
                st.markdown(f"**Type:** {', '.join(emp_types)}")
            
            # Date posted
            date_posted = job.get("date_posted", "").split("T")[0] if job.get("date_posted", "") else "N/A"
            st.markdown(f"**Posted:** {date_posted}")
        
        # Apply button
        job_url = job.get("url", "")
        if job_url:
            st.markdown(f"[Apply on LinkedIn]({job_url})")
        
        # Job description in expander
        with st.expander("View Full Description"):
            description = job.get("description_text", "No description available")
            st.markdown(description)
        
        # Save button
        if st.button(f"Save Job", key=f"save_{job.get('id', '')}"):
            st.success("Job saved to your profile!")
    
    # Add raw data in expander at the bottom for debugging
    with st.expander("View Raw JSON Data"):
        st.json(jobs_data)
