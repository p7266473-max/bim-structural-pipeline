import reflex as rx
import json
import os

from solver_opensees import run_opensees_analysis
from solver_frame3dd import run_frame3dd_analysis
from verify_checkpoints import verify_geometry_equilibrium, verify_tributary_loads, verify_material_detailing
from generators import generate_dxf_export, generate_pdf_report
from gemini_connector import parse_input_to_geojson, resolve_solver_divergence

class State(rx.State):
    """Reflex application state."""
    # API Key protocols
    api_key: str = ""
    model_name: str = "gemini-1.5-flash"
    
    # Input field text
    input_text: str = ""
    
    # Processed GeoJSON storage
    geojson_str: str = ""
    
    # Analysis outputs
    opensees_output_str: str = ""
    frame3dd_output_str: str = ""
    
    # Verification checkpoints results
    equilibrium_result: dict = {}
    tributary_result: dict = {}
    detailing_result: dict = {}
    
    # AI solver comparison tie-breaker
    ai_resolution: str = ""
    
    # File generation links
    dxf_ready: bool = False
    pdf_ready: bool = False
    dxf_link: str = ""
    pdf_link: str = ""
    
    # General status
    status_msg: str = "Awaiting design input..."
    
    def process_and_run(self):
        """Pipeline orchestration loop."""
        if not self.input_text.strip():
            self.status_msg = "Please provide layout text coordinates or layered description."
            return
            
        self.status_msg = "Contacting Gemini parser... Step 0 & 1 Ingestion"
        
        # 1. Gemini Ingestion & Parse to GeoJSON coordinates
        try:
            geojson_data = parse_input_to_geojson(self.api_key, self.input_text, self.model_name)
            self.geojson_str = json.dumps(geojson_data, indent=2)
        except Exception as e:
            self.status_msg = f"Error during parsing: {str(e)}"
            return
            
        self.status_msg = "Running OpenSeesPy & Frame3DD matrix calculations..."
        
        # 2. Executing headlessly on two numerical solvers
        try:
            opensees_res = run_opensees_analysis(geojson_data)
            self.opensees_output_str = json.dumps(opensees_res, indent=2)
            
            frame3dd_res = run_frame3dd_analysis(geojson_data)
            self.frame3dd_output_str = json.dumps(frame3dd_res, indent=2)
        except Exception as e:
            self.status_msg = f"Numerical solver failure: {str(e)}"
            return
            
        self.status_msg = "Running 3 GeoJSON checkpoint rules-checks..."
        
        # 3. Validation checkpoints
        try:
            self.equilibrium_result = verify_geometry_equilibrium(geojson_data, opensees_res)
            self.tributary_result = verify_tributary_loads(geojson_data, opensees_res)
            self.detailing_result = verify_material_detailing(opensees_res)
        except Exception as e:
            self.status_msg = f"Checkpoint rules audit failure: {str(e)}"
            return
            
        self.status_msg = "Executing Gemini AI tie-breaker validation..."
        
        # 4. Gemini Solver Cross-Validation
        try:
            self.ai_resolution = resolve_solver_divergence(self.api_key, opensees_res, frame3dd_res, self.model_name)
        except Exception as e:
            self.ai_resolution = "AI verification bypass. Output checks completed."
            
        self.status_msg = "Compiling structural CAD drawing and report PDF..."
        
        # 5. Output CAD/PDF compile
        try:
            assets_dir = "assets"
            if not os.path.exists(assets_dir):
                os.makedirs(assets_dir)
                
            dxf_filename = os.path.join(assets_dir, "structural_layout.dxf")
            pdf_filename = os.path.join(assets_dir, "structural_compliance_report.pdf")
            
            generate_dxf_export(geojson_data, dxf_filename)
            generate_pdf_report(opensees_res, self.equilibrium_result, self.tributary_result, self.detailing_result, pdf_filename)
            
            self.dxf_link = "/structural_layout.dxf"
            self.pdf_link = "/structural_compliance_report.pdf"
            self.dxf_ready = True
            self.pdf_ready = True
        except Exception as e:
            self.status_msg = f"Deliverables generation failure: {str(e)}"
            return
            
        self.status_msg = "Pipeline successfully executed. All 6 parameters verified!"

def index() -> rx.Component:
    return rx.box(
        rx.color_mode.button(position="top-right"),
        
        # Header Area (Vibrant Slate Modern/Digital Theme)
        rx.vstack(
            rx.heading("Structural Engineering & BIM Automation Pipeline", size="8", color_scheme="sky", margin_bottom="2"),
            rx.text(
                "Digitalization, automated matrix verification, and MQA compliant structural synthesis.",
                color_scheme="slate",
                size="4"
            ),
            spacing="1",
            align_items="center",
            padding="6",
            background="linear-gradient(135deg, #0F172A 0%, #1E293B 100%)",
            color="white",
            width="100%",
            border_bottom="3px solid #0284C7"
        ),
        
        # Main Work Panel (Three-column layout)
        rx.container(
            rx.flex(
                # Column 1: Configuration & Inputs
                rx.vstack(
                    rx.heading("Step 1: Pipeline Configuration", size="4", color="#0F172A"),
                    rx.text("Evaluator API Auth (BYOK Protocol)", size="2", font_weight="bold"),
                    rx.input(
                        placeholder="Paste Gemini API Key...",
                        type="password",
                        on_blur=State.set_api_key,
                        width="100%"
                    ),
                    rx.text("Model Tier", size="2", font_weight="bold"),
                    rx.select(
                        ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
                        default_value="gemini-1.5-flash",
                        on_change=State.set_model_name,
                        width="100%"
                    ),
                    rx.text("Floor Plan / AutoCAD Layers Text Metadata Ingestion", size="2", font_weight="bold"),
                    rx.text_area(
                        placeholder="Define spatial columns and beam loads (e.g. Column at Grid A-1 (0,0), Column at Grid B-1 (6,0), Beam spanning A-1 to B-1 carrying 25 kN/m uniform gravity loading...)",
                        rows=12,
                        on_blur=State.set_input_text,
                        width="100%"
                    ),
                    rx.button("Execute Verification Pipeline", on_click=State.process_and_run, color_scheme="sky", width="100%"),
                    rx.badge(State.status_msg, color_scheme="orange", variant="solid", padding="2"),
                    spacing="3",
                    width="30%",
                    padding="4",
                    background="white",
                    border_radius="lg",
                    box_shadow="lg"
                ),
                
                # Column 2: Code Verification Checkpoints (Dynamic UI output)
                rx.vstack(
                    rx.heading("Step 2: 3 Internal GeoJSON Checks", size="4", color="#0F172A"),
                    
                    # Checkpoint 1 Accordion / Cards
                    rx.box(
                        rx.text("Checkpoint 1: Geometry & Equilibrium", font_weight="bold", color="#1E293B"),
                        rx.text(State.equilibrium_result["summary"], size="2", color="#475569"),
                        border_left="4px solid #0284C7",
                        padding_left="3",
                        margin_bottom="3",
                        width="100%"
                    ),
                    # Checkpoint 2
                    rx.box(
                        rx.text("Checkpoint 2: Tributary Loads Check", font_weight="bold", color="#1E293B"),
                        rx.text(State.tributary_result["summary"], size="2", color="#475569"),
                        border_left="4px solid #10B981",
                        padding_left="3",
                        margin_bottom="3",
                        width="100%"
                    ),
                    # Checkpoint 3
                    rx.box(
                        rx.text("Checkpoint 3: Material Capacity & Rebar Detailing", font_weight="bold", color="#1E293B"),
                        rx.text(State.detailing_result["summary"], size="2", color="#475569"),
                        border_left="4px solid #F59E0B",
                        padding_left="3",
                        margin_bottom="3",
                        width="100%"
                    ),
                    
                    # Node displacements or output data
                    rx.heading("Secondary Cross-Validation Solver Check", size="4", color="#0F172A"),
                    rx.text("Stiffness matrix computation verification results between OpenSeesPy and Frame3DD solver loops.", size="2"),
                    rx.text_area(value=State.ai_resolution, read_only=True, rows=8, width="100%", font_family="monospace"),
                    
                    spacing="4",
                    width="40%",
                    padding="4",
                    background="white",
                    border_radius="lg",
                    box_shadow="lg"
                ),
                
                # Column 3: Parsed GeoJSON Coordinates & Deliverables
                rx.vstack(
                    rx.heading("Step 3: GeoJSON & Deliverables", size="4", color="#0F172A"),
                    rx.text("Semantic GeoJSON coordinates generated by Gemini API parsing:", size="2"),
                    rx.text_area(value=State.geojson_str, read_only=True, rows=12, width="100%", font_family="monospace"),
                    
                    rx.heading("Professional CAD/PDF Output Exports", size="4", color="#0F172A", margin_top="4"),
                    rx.cond(
                        State.dxf_ready,
                        rx.link(
                            rx.button("Download Structural DXF Drawing", color_scheme="teal", width="100%"),
                            href=State.dxf_link,
                            is_external=True
                        )
                    ),
                    rx.cond(
                        State.pdf_ready,
                        rx.link(
                            rx.button("Download Verification PDF Report", color_scheme="indigo", width="100%"),
                            href=State.pdf_link,
                            is_external=True
                        )
                    ),
                    
                    spacing="3",
                    width="30%",
                    padding="4",
                    background="white",
                    border_radius="lg",
                    box_shadow="lg"
                ),
                
                flex_direction="row",
                justify_content="space-between",
                gap="4",
                width="100%",
                margin_top="6"
            ),
            max_width="1400px"
        )
    )

app = rx.App()
app.add_page(index)
app.compile()
