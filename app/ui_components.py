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
                    data = response.json()
                    st.session_state.auth_token = data.get("user", {}).get("access_token")
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
    
    uploaded_resumes = st.file_uploader(
        "Upload your Resumes (PDF)",
        type = ["pdf"],
        accept_multiple_files= True)

    submit_button = st.button("Next")

    if submit_button:
        if full_name and uploaded_resumes:
            with st.spinner("Processing resumes..."):
                try:
                    name = {"name": full_name}
                    pdf_files = [
                        ("resumes", (resume.name, resume.getvalue(), resume.type))
                        for resume in uploaded_resumes
                    ]
                    
                    # Include auth token if available
                    if "auth_token" in st.session_state:
                        name["token"] = st.session_state.auth_token
                    
                    response = requests.post(
                        f"{API_URL}/users/details",                            
                        data=name,
                        files=pdf_files                            
                    )
                    if response.status_code == 200:
                        st.success("Details submitted successfully!")
                        # Store user ID in session state from the response
                        response_data = response.json()
                        if 'user_id' not in st.session_state:   
                            st.session_state.user_id = response_data["user_id"]
                        st.session_state.current_page = "job_preferences"
                        st.rerun()
                    else:
                        st.error("Failed to save user details. Please try again.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please fill the Name and upload your Resumes.")



def job_preferences_form():
    st.subheader("Job Search Preferences")
    
    # Get user name if available
    user_name = st.session_state.get("full_name", "")
    if user_name:
        st.write(f"Hello, {user_name}! Let's find the perfect job for you.")
    
    # Job preference fields
    target_roles = st.text_input(
        "Target Roles (comma separated)", 
        help="e.g., Machine Learning Engineer, Data Scientist"
    )
    
    primary_skills = st.text_input(
        "Primary Skills (comma separated) ",
        help="e.g., Python, SQL, Machine Learning"
    )
    
    preferred_location = st.text_input(
        "Preferred Locations (comma separated)",
        help="e.g., San Francisco, Remote, New York"
    )
    
    job_type = st.multiselect(
        "Job Type", 
        options=["Full-time", "Part-time", "Contract", "Internship"],
        default=["Full-time"]  # Set default value
    )
    
    additional_preferences = st.text_area(
        "Additional Preferences", 
        help="Any other requirements or preferences"
    )

    # Test endpoint button for debugging
    if st.button("Test API Connection"):
        try:
            response = requests.get(f"{API_URL}/api/test")
            if response.status_code == 200:
                st.success(f"API connection successful: {response.json()}")
            else:
                st.error(f"API connection failed: {response.status_code}")
        except Exception as e:
            st.error(f"API connection error: {str(e)}")

    # Sync Jobs to Pinecone button
    if st.button("Sync Jobs to Pinecone"):
        try:
            response = requests.post(f"{API_URL}/api/sync-pinecone")
            if response.status_code == 200:
                result = response.json()
                st.success(f"Jobs synced to Pinecone successfully: {result.get('count', 0)} jobs processed")
            else:
                st.error(f"Failed to sync jobs to Pinecone. Status code: {response.status_code}")
                try:
                    st.error(f"Error details: {response.json()}")
                except:
                    st.error(f"Raw response: {response.text}")
        except Exception as e:
            st.error(f"Error syncing to Pinecone: {str(e)}")

    # Search Pinecone button (New)
    if st.button("Search Pinecone"):
        try:
            response = requests.post(
                "http://localhost:8000/api/search-pinecone",
                json={
                    "user_id": st.session_state.user_id,
                    "target_roles": target_roles,
                    "primary_skills": primary_skills,
                    "preferred_location": preferred_location,
                    "job_type": job_type,
                    "additional_preferences": additional_preferences
                }
            )
            
            if response.status_code == 200:
                results_data = response.json()
                results = results_data.get("results", [])
                query_used = results_data.get("query", "N/A")

                st.info(f"Showing {len(results)} results for query: \"{query_used}\"")
                st.divider()

                if not results:
                    st.warning("No matching jobs found in the vector database for your profile and preferences.")
                else:
                    # Display results
                    for job in results:
                        with st.container(border=True): # Add a border for better separation
                            col1, col2 = st.columns([3, 1])

                            with col1:
                                st.subheader(f"{job.get('title', 'N/A')}")
                                st.write(f"🏢 {job.get('company', 'N/A')} | 📍 {job.get('location', 'N/A')}")
                                st.write(f"**Type:** {job.get('job_type', 'N/A')} | **Posted:** {job.get('date_posted', 'N/A')}")
                                if job.get('url'):
                                    st.link_button("Apply Now 🔗", job['url'])

                            with col2:
                                st.metric(
                                    "Resume Match",
                                    f"{job.get('match_percentage', 0):.1f}%", # Format to 1 decimal place
                                    delta=None
                                )
                                if job.get('skills_matched'): # Display skills matched from original filtering if available
                                     st.caption(f"Matched Skills: {job['skills_matched']}")


                            # --- Display Analysis Section ---
                            analysis = job.get('analysis', {})
                            print("\nAnalysis:", analysis)
                            if analysis: # Only show expander if analysis data exists
                                with st.expander("🔍 Show AI Analysis & Tips"):
                                    st.markdown("**Missing Skills & Learning Time:**")
                                    missing_skills = analysis.get('missing_skills', [])
                                    if missing_skills:
                                        for item in missing_skills:
                                            skill = item.get('skill', 'N/A')
                                            estimate = item.get('learn_time_estimate', 'N/A')
                                            st.write(f"- **{skill}:** {estimate}")
                                    else:
                                        st.write("_No specific skill gaps identified or analysis failed._")

                                    st.markdown("**Resume Tailoring Suggestions:**")
                                    suggestions = analysis.get('resume_suggestions', {})
                                    highlights = suggestions.get('highlight', [])
                                    removals = suggestions.get('consider_removing', [])

                                    if highlights:
                                        st.markdown("**Consider Highlighting:**")
                                        for item in highlights:
                                            st.write(f"- {item}")

                                    if removals:
                                         st.markdown("**Consider Removing/De-emphasizing:**")
                                         for item in removals:
                                             st.write(f"- {item}")

                                    if not highlights and not removals:
                                         st.write("_No specific resume tailoring suggestions provided._")
                            else:
                                 # Optionally indicate that analysis wasn't performed for this job
                                 st.caption("_AI analysis not available for this job._")

                            # Removed the extra st.divider() inside the loop for cleaner look
                    st.divider() # Keep one divider after the loop

            else:
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                except:
                    error_detail = response.text
                st.error(f"Failed to fetch search results ({response.status_code}): {error_detail}")
            
        except Exception as e:
            st.error(f"Error during search: {str(e)}")

    # Submit button
    if st.button("Search Jobs"):
        if target_roles and primary_skills:
            with st.spinner("Searching for matching jobs..."):
                try:
                    # convert string to list
                    target_roles_list = [role.strip() for role in target_roles.split(",")]
                    primary_skills_list = [skill.strip() for skill in primary_skills.split(",")]
                    
                    # Print debug info
                    st.write(f"Debug - Sending job_type: {job_type[0] if job_type else 'Full-time'}")
                    
                    # Create the request payload
                    payload = {
                        "user_id": st.session_state.user_id,
                        "target_roles": target_roles_list,
                        "primary_skills": primary_skills_list,
                        "preferred_location": preferred_location,
                        "job_type": job_type[0] if job_type else "Full-time",
                        "additional_preferences": additional_preferences
                    }
                    
                    # Display the full request for debugging
                    st.json(payload)
                    
                    response = requests.post(
                        f"{API_URL}/api/search",
                        json=payload
                    )
                    
                    # Display raw response for debugging
                    st.write(f"Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        results = response.json()
                        
                        # Display search statistics
                        st.success(f"Found {results.get('filtered_jobs_count', 0)} matching jobs out of {results.get('total_jobs_found', 0)} total jobs")
                        
                        # Get jobs or empty list if not present
                        jobs = results.get('jobs', [])
                        
                        # Sort jobs by date_posted if available
                        if jobs:
                            jobs = sorted(jobs, 
                                       key=lambda x: x.get('date_posted', ''),
                                       reverse=True)  # Most recent first
                        
                        # Display each job
                        for job in jobs:
                            with st.expander(f"{job.get('title', 'No title')} at {job.get('company', 'Unknown')} - {job.get('location', 'No location')}"):
                                st.write(f"**Posted:** {job.get('date_posted', 'Unknown')}")
                                st.write(f"**Company:** {job.get('company', 'Unknown')}")
                                st.write(f"**Location:** {job.get('location', 'Unknown')}")
                                st.write(f"**Apply:** {job.get('url', 'Unknown')}")
                                
                                # Display matched skills if available
                                if 'job_matched_skills' in job:
                                    st.write(f"**Skills Matched:** {len(job['job_matched_skills'])} skills")
                                    
                                    # Display matched skills
                                    st.write("**Matched Skills:**")
                                    for skill, terms in job['job_matched_skills'].items():
                                        st.write(f"- {skill}: {', '.join(terms)}")
                                
                                st.write("**Job Description:**")
                                st.write(job.get('description', 'No description available'))
                                
                                # Apply button
                                if st.button(f"Apply to {job.get('company', 'this job')}", key=job.get('apply_url', '')):
                                    st.markdown(f"[Apply Here]({job.get('url', '#')})")
                    else:
                        st.error(f"Failed to fetch job results. Status code: {response.status_code}")
                        try:
                            st.error(f"Error details: {response.json()}")
                        except:
                            st.error(f"Raw response: {response.text}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please enter at least one target role and primary skill.")
