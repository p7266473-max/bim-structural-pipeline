import json
import numpy as np
import openseespy.opensees as ops

def run_opensees_analysis(geojson_data):
    """
    Ingests GeoJSON structure data and performs a 2D frame matrix structural analysis using OpenSeesPy.
    
    The GeoJSON format should look like:
    {
      "type": "FeatureCollection",
      "features": [
         {"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]}, "properties": {"type": "node", "support": "pinned" or "fixed" or "none", "node_id": 1}},
         {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[x1, y1], [x2, y2]]}, "properties": {"type": "beam", "beam_id": 1, "load_kn_m": 15.0, "section_w_mm": 300, "section_h_mm": 600}}
      ]
    }
    """
    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 3)
    
    nodes = {}
    elements = []
    
    # First pass: parse nodes
    for feature in geojson_data.get("features", []):
        geom = feature.get("geometry")
        props = feature.get("properties", {})
        if geom and geom.get("type") == "Point":
            coords = geom.get("coordinates")
            # In 2D, coords are typically [x, y]
            x, y = coords[0], coords[1]
            node_id = int(props.get("node_id", len(nodes) + 1))
            nodes[node_id] = (x, y)
            ops.node(node_id, float(x), float(y))
            
            # Apply boundary conditions
            support = props.get("support", "none")
            if support == "pinned":
                ops.fix(node_id, 1, 1, 0)
            elif support == "fixed":
                ops.fix(node_id, 1, 1, 1)
                
    # Define materials and sections
    # E = 30 GPa (Concrete), A = w * h, Iz = w * h^3 / 12
    # Transformed to standard beam-column elements
    ops.geomTransf('Linear', 1)
    
    element_id_counter = 1
    loads = []
    
    # Second pass: parse line elements (beams / columns)
    for feature in geojson_data.get("features", []):
        geom = feature.get("geometry")
        props = feature.get("properties", {})
        if geom and geom.get("type") == "LineString":
            coords = geom.get("coordinates")
            if len(coords) < 2:
                continue
            
            # Find or create nodes matching the end coordinates
            pt1, pt2 = coords[0], coords[1]
            
            def find_or_create_node(pt):
                # Check if matches existing node
                for nid, ncoords in nodes.items():
                    if np.allclose(ncoords, pt, atol=0.01):
                        return nid
                # Create a new node if none found
                new_id = len(nodes) + 1
                nodes[new_id] = (pt[0], pt[1])
                ops.node(new_id, float(pt[0]), float(pt[1]))
                return new_id
            
            n1 = find_or_create_node(pt1)
            n2 = find_or_create_node(pt2)
            
            # Cross section parameters (defaults: 300x600mm)
            width = float(props.get("section_w_mm", 300)) / 1000.0
            height = float(props.get("section_h_mm", 600)) / 1000.0
            
            A = width * height
            E = 3.0e7 # kN/m^2 (30 GPa)
            I = (width * (height ** 3)) / 12.0
            
            ops.element('elasticBeamColumn', element_id_counter, n1, n2, A, E, I, 1)
            
            # Load parsing (uniform gravity load in kN/m)
            load_val = float(props.get("load_kn_m", 0.0))
            if load_val > 0:
                loads.append((element_id_counter, load_val))
                
            elements.append({
                "element_id": element_id_counter,
                "n1": n1,
                "n2": n2,
                "length": np.linalg.norm(np.array(pt2) - np.array(pt1)),
                "properties": props
            })
            element_id_counter += 1

    # Apply loads
    ops.timeSeries('Constant', 1)
    ops.pattern('Plain', 1, 1)
    
    for elem_id, load_val in loads:
        # Uniform distributed gravity load (negative y direction)
        ops.eleLoad('-ele', elem_id, '-type', '-beamUniform', -load_val)
        
    # Run analysis
    ops.constraints('Plain')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr', 1.0e-12, 10)
    ops.algorithm('Linear')
    ops.analysis('Static')
    ops.analyze(1)
    
    # Calculate reactions explicitly before querying nodeReaction
    ops.reactions()
    
    # Extract results
    results = {
        "nodes": {},
        "elements": []
    }
    
    for nid in nodes.keys():
        disp = ops.nodeDisp(nid) # [dx, dy, rz]
        reaction = [0.0, 0.0, 0.0]
        try:
            reaction = ops.nodeReaction(nid)
        except Exception:
            pass
        results["nodes"][nid] = {
            "displacements": disp,
            "reactions": reaction,
            "coordinates": list(nodes[nid])
        }
        
    for elem in elements:
        eid = elem["element_id"]
        # Forces at the two ends [P1, V1, M1, P2, V2, M2]
        forces = ops.basicForce(eid) if hasattr(ops, 'basicForce') else ops.eleResponse(eid, 'forces')
        results["elements"].append({
            "element_id": eid,
            "n1": elem["n1"],
            "n2": elem["n2"],
            "length": elem["length"],
            "forces": list(forces) if forces else [0.0]*6,
            "properties": elem["properties"]
        })
        
    return results
