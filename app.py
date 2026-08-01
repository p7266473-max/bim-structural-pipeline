import streamlit as st
import json
import os
import base64

# Import solver and verification scripts
from solver_opensees import run_opensees_analysis
from solver_frame3dd import run_frame3dd_analysis
from verify_checkpoints import verify_geometry_equilibrium, verify_tributary_loads, verify_material_detailing
from generators import generate_dxf_export, generate_pdf_report, render_dxf_to_png, export_drawing_to_pdf
from gemini_connector import parse_input_to_geojson, resolve_solver_divergence, perform_iteration_loop

# Define paths relative to the script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
secrets_toml_path = os.path.join(script_dir, ".streamlit", "secrets.toml")

# Load environment variables if a .env file exists (e.g. locally)
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key.strip()] = val.strip()

# Retrieve default key from environment/secrets, or fall back to file parsing
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or (st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else "")

if not GEMINI_API_KEY:
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "GEMINI_API_KEY=" in line:
                    GEMINI_API_KEY = line.split("=", 1)[1].strip()
                    break
    if not GEMINI_API_KEY and os.path.exists(secrets_toml_path):
        with open(secrets_toml_path, "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line and "=" in line:
                    GEMINI_API_KEY = line.split("=", 1)[1].replace('"', '').replace("'", '').strip()
                    break

# Obfuscate and decode the forced model name so it is not visible in the source code or app as plain text
# "Z2VtaW5pLTMuMS1mbGFzaC1saXRl" decodes to the required flash-lite model
GEMINI_MODEL_NAME = base64.b64decode("Z2VtaW5pLTMuMS1mbGFzaC1saXRl").decode("utf-8")

# Page config
st.set_page_config(
    page_title="BIM Structural Verification Pipeline",
    page_icon="🏗️",
    layout="wide"
)

# Header Section
st.markdown("""
<div style="background-color:#0F172A;padding:24px;border-radius:12px;border-bottom:4px solid #0284C7;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:2.2rem">🏗️ BIM Structural Verification Pipeline Dashboard</h1>
    <p style="color:#94A3B8;margin:6px 0 0 0;font-size:1.1rem">
        Automated structural matrix execution, multi-solver cross-validation, and three-checkpoint regulatory rule compliance.
    </p>
</div>
""", unsafe_allow_html=True)

# Three-column layout
col1, col2, col3 = st.columns([1.2, 1.6, 1.2])

with col1:
    st.subheader("Step 1: Configuration & Input")
    
    # Selection mode for API key
    key_mode = st.radio(
        "API Key Option",
        ["Use Default Key (Secure)", "Use Custom Key"],
        index=0
    )
    
    if key_mode == "Use Default Key (Secure)":
        active_api_key = GEMINI_API_KEY
        st.info("🔒 Default key loaded from environment secrets.")
    else:
        user_api_key = st.text_input("Custom Gemini API Key", type="password", placeholder="Paste custom API Key...")
        active_api_key = user_api_key
        
    if active_api_key:
        st.success("API Key loaded successfully.")
    else:
        st.warning("⚠️ No API key loaded. Please check your configuration.")
    
    st.markdown("---")
    st.markdown("**Construction Parameter Configuration**")
    num_floors = st.radio("How many floors do you want to construct?", [1, 2], index=0, help="Specifying 2 floors increases the design load vectors to verify double level load paths.")
    
    st.markdown("---")
    st.markdown("**Ingest Layout Blueprint Design**")
    
    uploaded_image = st.file_uploader("Upload 2D Plan Drawing Sketch / Blueprint Image", type=["png", "jpg", "jpeg"])
    if uploaded_image:
        st.image(uploaded_image, caption="Uploaded Plan Drawing Sketch", use_container_width=True)
        
    input_text = st.text_area(
        label="Additional Context / Override (Optional — leave blank if uploading a floor plan image)",
        value="",
        placeholder="e.g. 25' x 45' 2-bedroom ground floor plan. Focus on load-bearing walls only.",
        height=100
    )
    
    run_btn = st.button("Run Verification Pipeline", type="primary", use_container_width=True)

if run_btn:
    if not active_api_key:
        st.error("Please provide a Gemini API Key.")
    else:
        with st.spinner("Processing design details & iterating..."):
            try:
                image_bytes = None
                image_mime = None
                if uploaded_image:
                    image_bytes = uploaded_image.getvalue()
                    image_mime = uploaded_image.type
                    
                # Step 1: Parse input text via Gemini to GeoJSON
                raw_geojson = parse_input_to_geojson(
                    api_key=active_api_key, 
                    file_content_or_text=input_text, 
                    image_bytes=image_bytes,
                    image_mime=image_mime,
                    num_floors=num_floors,
                    model_name=GEMINI_MODEL_NAME
                )
                
                # Auto-iteration Correction Loop
                geojson_data, iteration_log, loop_success = perform_iteration_loop(
                    api_key=active_api_key,
                    initial_geojson=raw_geojson,
                    num_floors=num_floors,
                    model_name=GEMINI_MODEL_NAME
                )
                
                # Final Solver Pass on corrected geometry
                opensees_res = run_opensees_analysis(geojson_data)
                frame3dd_res = run_frame3dd_analysis(geojson_data)
                
                # Step 3: Run Validation Checks on Final Corrected Geometry
                check1 = verify_geometry_equilibrium(geojson_data, opensees_res)
                check2 = verify_tributary_loads(geojson_data, opensees_res)
                check3 = verify_material_detailing(opensees_res)
                
                # Step 4: Resolve Divergence
                ai_resolution = resolve_solver_divergence(active_api_key, opensees_res, frame3dd_res, GEMINI_MODEL_NAME)
                
                # Step 5: Deliverables
                os.makedirs("assets", exist_ok=True)
                dxf_path = os.path.join("assets", "structural_layout.dxf")
                png_path = os.path.join("assets", "structural_drawing.png")
                pdf_path = os.path.join("assets", "structural_compliance_report.pdf")
                drawing_pdf_path = os.path.join("assets", "drawing_layout.pdf")
                
                # Generate drawing files and PDFs
                generate_dxf_export(geojson_data, dxf_path)
                render_dxf_to_png(geojson_data, png_path)
                export_drawing_to_pdf(geojson_data, drawing_pdf_path)
                generate_pdf_report(opensees_res, check1, check2, check3, pdf_path)
                
                # Save variables in Streamlit session state
                st.session_state["geojson_data"] = geojson_data
                st.session_state["check1"] = check1
                st.session_state["check2"] = check2
                st.session_state["check3"] = check3
                st.session_state["ai_resolution"] = ai_resolution
                st.session_state["dxf_path"] = dxf_path
                st.session_state["png_path"] = png_path
                st.session_state["pdf_path"] = pdf_path
                st.session_state["drawing_pdf_path"] = drawing_pdf_path
                st.session_state["iteration_log"] = iteration_log
                st.session_state["loop_success"] = loop_success
                st.session_state["processed"] = True
            except Exception as e:
                st.error(f"Pipeline execution failed:\n\n{str(e)}")

# Display results in Column 2 & 3 if processed
if st.session_state.get("processed"):
    check1 = st.session_state["check1"]
    check2 = st.session_state["check2"]
    check3 = st.session_state["check3"]
    geojson_data = st.session_state["geojson_data"]
    ai_resolution = st.session_state["ai_resolution"]
    iteration_log = st.session_state["iteration_log"]
    loop_success = st.session_state["loop_success"]
    
    with col2:
        st.subheader("Step 2: 3 Internal GeoJSON Checkpoints")
        
        # Iteration Correction History
        st.markdown("**AI Auto-Correction Iteration History**")
        for log in iteration_log:
            if "Success" in log:
                st.success(log)
            else:
                st.error(log)
                
        # Checkpoint 1
        st.info(f"**Checkpoint 1: Spatial Geometry & Global Equilibrium**\n\n{check1['summary']}")
        st.json(check1["metrics"])
        
        # Checkpoint 2
        st.success(f"**Checkpoint 2: Tributary Loads & Load Paths**\n\n{check2['summary']}")
        st.write(check2["data"])
        
        # Checkpoint 3
        c3_status = st.warning if not check3["passed"] else st.success
        c3_status(f"**Checkpoint 3: Detailing & Capacity Limits**\n\n{check3['summary']}")
        st.write(check3["data"])
        
        st.markdown("---")
        st.subheader("Solver Cross-Validation Audits")
        st.write(ai_resolution)
        
    with col3:
        st.subheader("Step 3: Coordinates & Exports")
        
        # Render visual drawing preview in web interface
        st.markdown("**Structural Drawing Preview**")
        if os.path.exists(st.session_state["png_path"]):
            st.image(st.session_state["png_path"], caption="Rendered 2D Foundation & Beam Layout", use_container_width=True)
            
        st.markdown("**Extracted GeoJSON Model Coords**")
        st.json(geojson_data)
        
        st.markdown("---")
        st.subheader("Professional Deliverables")
        
        with open(st.session_state["dxf_path"], "rb") as dxf_file:
            st.download_button(
                label="📥 Download AutoCAD DXF Drawing",
                data=dxf_file,
                file_name="structural_layout.dxf",
                mime="application/dxf",
                use_container_width=True
            )
            
        with open(st.session_state["drawing_pdf_path"], "rb") as drawing_pdf_file:
            st.download_button(
                label="📥 Download AutoCAD Drawing as PDF",
                data=drawing_pdf_file,
                file_name="drawing_layout.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        with open(st.session_state["pdf_path"], "rb") as pdf_file:
            st.download_button(
                label="📥 Download Compliance PDF Report",
                data=pdf_file,
                file_name="structural_compliance_report.pdf",
                mime="application/pdf",
                use_container_width=True
            )
else:
    with col2:
        st.info("Awaiting pipeline execution to run checkpoints.")
    with col3:
        st.info("Awaiting pipeline execution to generate CAD/PDF.")
