import ezdxf
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_dxf_export(geojson_data, filename="structural_layout.dxf"):
    """
    Generates a standard CAD-compatible 2D structural layout in AutoCAD DXF format.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Define layers
    doc.layers.new(name='COLUMNS', dxfattribs={'color': 1}) # Red
    doc.layers.new(name='BEAMS', dxfattribs={'color': 3})   # Green
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
                msp.add_circle((x, y), radius=0.25, dxfattribs={'layer': 'COLUMNS'})
                msp.add_text(f"C{nid}", dxfattribs={'layer': 'COLUMNS', 'height': 0.15}).set_placement((x + 0.3, y + 0.3))
                
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

def generate_pdf_report(opensees_results, check1, check2, check3, filename="structural_compliance_report.pdf"):
    """
    Generates a publication-grade structural compliance report detailing matrix outputs and rules checks.
    """
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Custom Styles for Premium Aesthetics
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
    
    doc.build(story)
    return filename
