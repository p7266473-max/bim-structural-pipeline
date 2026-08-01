import ezdxf
import matplotlib.pyplot as plt
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_dxf_export(geojson_data, filename="structural_layout.dxf"):
    """
    Generates a standard CAD-compatible 2D structural layout in AutoCAD DXF format.
    Includes columns, beams, and foundation pads.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Define layers
    doc.layers.new(name='COLUMNS', dxfattribs={'color': 1}) # Red
    doc.layers.new(name='BEAMS', dxfattribs={'color': 3})   # Green
    doc.layers.new(name='FOUNDATIONS', dxfattribs={'color': 5}) # Blue
    doc.layers.new(name='GRID_LINES', dxfattribs={'color': 8}) # Gray
    
    nodes = {}
    for feature in geojson_data.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})
        if geom.get("type") == "Point":
            coords = geom.get("coordinates")
            x, y = float(coords[0]), float(coords[1])
            nid = int(props.get("node_id"))
            nodes[nid] = (x, y)
            
            # Draw column indicator (small circle or point)
            if props.get("support") in ["pinned", "fixed"]:
                msp.add_circle((x, y), radius=0.15, dxfattribs={'layer': 'COLUMNS'})
                msp.add_text(f"C{nid}", dxfattribs={'layer': 'COLUMNS', 'height': 0.15}).set_placement((x + 0.2, y + 0.2))
                
                # Draw 2D structural Foundation Pad representation (1.2m x 1.2m concrete pad)
                half_w = 0.6
                p1 = (x - half_w, y - half_w)
                p2 = (x + half_w, y - half_w)
                p3 = (x + half_w, y + half_w)
                p4 = (x - half_w, y + half_w)
                msp.add_line(p1, p2, dxfattribs={'layer': 'FOUNDATIONS'})
                msp.add_line(p2, p3, dxfattribs={'layer': 'FOUNDATIONS'})
                msp.add_line(p3, p4, dxfattribs={'layer': 'FOUNDATIONS'})
                msp.add_line(p4, p1, dxfattribs={'layer': 'FOUNDATIONS'})
                msp.add_text(f"FND_{nid} (1.2x1.2m)", dxfattribs={'layer': 'FOUNDATIONS', 'height': 0.1}).set_placement((x - 0.5, y - 0.75))
                
    for feature in geojson_data.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})
        if geom.get("type") == "LineString":
            coords = geom.get("coordinates")
            p1, p2 = coords[0], coords[1]
            msp.add_line((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])), dxfattribs={'layer': 'BEAMS'})
            
            # Label the beam midpoint
            mid_x = (float(p1[0]) + float(p2[0])) / 2.0
            mid_y = (float(p1[1]) + float(p2[1])) / 2.0
            label = f"B_{props.get('beam_id', 'X')}"
            msp.add_text(label, dxfattribs={'layer': 'BEAMS', 'height': 0.15}).set_placement((mid_x, mid_y + 0.2))
            
    doc.saveas(filename)
    return filename

def render_dxf_to_png(geojson_data, output_png="assets/structural_drawing.png"):
    """
    Renders the 2D structural plan model visually into a clean high-resolution PNG using matplotlib.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_aspect('equal')
    ax.set_facecolor('#1E293B') # Slate background matching premium dashboard style
    fig.patch.set_facecolor('#0F172A')
    
    # Grid lines
    ax.grid(True, color='#334155', linestyle='--', linewidth=0.5)
    
    # 1. Plot Foundations and Columns
    for feature in geojson_data.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})
        if geom.get("type") == "Point":
            coords = geom.get("coordinates")
            x, y = float(coords[0]), float(coords[1])
            nid = int(props.get("node_id"))
            
            # Draw foundation pad for every column (Top View representation)
            half_w = 0.6
            rect = plt.Rectangle((x - half_w, y - half_w), 1.2, 1.2, 
                                 fill=True, color='#0284C7', alpha=0.3, label='Foundation Pad (1.2x1.2m)' if nid == 1 else "")
            rect_border = plt.Rectangle((x - half_w, y - half_w), 1.2, 1.2, 
                                        fill=False, color='#38BDF8', linewidth=1.5)
            ax.add_patch(rect)
            ax.add_patch(rect_border)
            
            # Draw column circle (Red dot)
            circle = plt.Circle((x, y), 0.15, color='#EF4444', zorder=5, label='Concrete Column' if nid == 1 else "")
            ax.add_patch(circle)
            ax.text(x + 0.2, y + 0.2, f"C{nid}", color='#F8FAFC', fontsize=10, fontweight='bold', zorder=6)
            ax.text(x - 0.5, y - 0.9, f"FND_{nid}\n1.2x1.2m", color='#38BDF8', fontsize=8, ha='center')
                
    # 2. Plot Beams
    for feature in geojson_data.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})
        if geom.get("type") == "LineString":
            coords = geom.get("coordinates")
            p1, p2 = coords[0], coords[1]
            ax.plot([float(p1[0]), float(p2[0])], [float(p1[1]), float(p2[1])], 
                    color='#10B981', linewidth=4, zorder=2, label='Structural Beam' if props.get('beam_id') == 1 else "")
            
            mid_x = (float(p1[0]) + float(p2[0])) / 2.0
            mid_y = (float(p1[1]) + float(p2[1])) / 2.0
            label = f"B_{props.get('beam_id', 'X')}\n({props.get('section_w_mm', 300)}x{props.get('section_h_mm', 600)}mm)"
            ax.text(mid_x, mid_y + 0.3, label, color='#34D399', fontsize=9, ha='center', fontweight='bold')
            
    ax.set_title("2D STRUCTURAL PLAN LAYOUT (TOP VIEW)", color='#F8FAFC', fontsize=14, fontweight='bold', pad=15)
    ax.tick_params(colors='#64748B')
    
    # Remove duplicates in legend
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='upper right', facecolor='#0F172A', edgecolor='#334155', labelcolor='#F8FAFC')
    
    plt.tight_layout()
    plt.savefig(output_png, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return output_png

def export_drawing_to_pdf(geojson_data, filename="assets/drawing_layout.pdf"):
    """
    Exports ONLY the AutoCAD structural layout design diagram as a standalone PDF sheet.
    """
    # Render drawing layout to temp PNG
    temp_png = "assets/temp_pdf_render.png"
    render_dxf_to_png(geojson_data, temp_png)
    
    # Place it inside a PDF document layout
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=18, leftMargin=18, topMargin=18, bottomMargin=18)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DrawingTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=10
    )
    story.append(Paragraph("AutoCAD 2D Plan Drawing Layout Sheet", title_style))
    story.append(Image(temp_png, width=540, height=432))
    
    doc.build(story)
    
    # Clean up temp file
    if os.path.exists(temp_png):
        os.remove(temp_png)
        
    return filename

def generate_pdf_report(opensees_results, check1, check2, check3, filename="structural_compliance_report.pdf"):
    """
    Generates a publication-grade structural compliance report detailing matrix outputs and rules checks.
    """
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=8
    )
    
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )
    
    story.append(Paragraph("Automated Structural Verification Report", title_style))
    story.append(Paragraph("Taylor's University | School of Architecture, Building & Design", body_style))
    story.append(Spacer(1, 10))
    
    # Summary Table
    story.append(Paragraph("1. Verification Executive Summary", h2_style))
    sum_data = [
        ["Checkpoint Parameter", "Evaluation Status", "Metrics & Description"],
        ["Checkpoint 1: Equilibrium", "PASSED" if check1["passed"] else "FAILED", check1["summary"]],
        ["Checkpoint 2: Tributary Loads", "PASSED" if check2["passed"] else "FAILED", check2["summary"]],
        ["Checkpoint 3: Detailing Check", "PASSED" if check3["passed"] else "FAILED", check3["summary"]]
    ]
    t_summary = Table(sum_data, colWidths=[150, 100, 290])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TEXTCOLOR', (1,1), (1,-1), colors.HexColor('#16A34A')),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 15))
    
    # Element Detailing Table
    story.append(Paragraph("2. Concrete Rebar & Capacity Detailing Output", h2_style))
    detail_data = [["Element ID", "Design Moment (kNm)", "Capacity (kNm)", "D/C Ratio", "Calculated Rebar Detail", "Status"]]
    for item in check3["data"]:
        status_text = "OK" if item["passed"] else "OVERSTRESSED"
        detail_data.append([
            f"Element {item['element_id']}",
            f"{item['max_moment_knm']:.2f}",
            f"{item['moment_capacity_knm']:.2f}",
            f"{item['dc_ratio']:.2f}",
            item["rebar_detail"],
            status_text
        ])
    t_detail = Table(detail_data, colWidths=[80, 110, 110, 80, 100, 60])
    t_detail.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#334155')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_detail)
    story.append(Spacer(1, 15))
    
    # Append the plotted 2D structural plan directly in the report
    if os.path.exists("assets/structural_drawing.png"):
        story.append(Paragraph("3. 2D Structural Coordination Drawing Layout", h2_style))
        story.append(Image("assets/structural_drawing.png", width=480, height=384))
        
    doc.build(story)
    return filename
