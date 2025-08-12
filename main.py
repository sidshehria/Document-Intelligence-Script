# Endpoint to list all JSON files and their contents from output_json directory
import glob


# type: ignore
# pylint: skip-file

import os
import json
import uuid
import tempfile
import pdfplumber
import re
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config_parameters import (
    SECTION_KEYWORDS, FIBER_COUNT_PATTERNS, PARAMETER_CATEGORIES, COLOR_CODES,
    TEXT_PARAMETER_PATTERNS, FIBER_COUNT_TEXT_PATTERNS, VALID_FIBER_COUNTS,
    ENHANCED_TEXT_PATTERNS, identify_section, categorize_parameter, 
    get_all_text_patterns, add_parameter_if_new, param_manager, ensure_parameter_exists
)

# FastAPI app setup
app = FastAPI()

@app.get("/api/json-files")
async def list_json_files():
    import os
    import json
    output_dir = os.path.join(os.path.dirname(__file__), "output_json")
    files = glob.glob(os.path.join(output_dir, "*.json"))
    result = []
    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            result.append({
                "filename": os.path.basename(file_path),
                "content": content
            })
        except Exception as e:
            result.append({
                "filename": os.path.basename(file_path),
                "error": str(e)
            })
    return result
# Configure CORS for Angular 13 frontend (e.g., http://localhost:4200)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Update with your Angular app URL
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
  
# Global column mappings storage to avoid attaching attributes to functions
COLUMN_MAPPINGS: dict = {}

def clean_parameter_value(value):
    """Clean parameter values by removing IEC standard codes and extra whitespace"""
    if not value or not isinstance(value, str):
        return value
    
    # Remove full IEC standard codes (e.g., "IEC-60794-1-21-E7")
    cleaned = re.sub(r'\s*IEC-[\d-]+(?:-[A-Z]\d+)?\s*', '', value)
    
    # Remove partial IEC codes like "E3", "E4", "E7", etc. attached to values
    cleaned = re.sub(r'([A-Z]\d+)$', '', cleaned)
    
    # Remove partial IEC codes like "E3", "E4", "E7", etc. when they appear alone
    if re.match(r'^[A-Z]\d+$', cleaned.strip()):
        return ""  # Return empty if it's just a partial IEC code
    
    # Clean up extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def parse_color_sequence(text):
    """Parse color coding sequences and return numbered color mappings"""
    color_mapping = {}
    if not text or text.strip() == "---":
        return color_mapping
    
    # Split by common separators and clean
    colors = re.split(r'[,\s]+', text.lower().strip())
    colors = [c.strip() for c in colors if c.strip()]
    
    # Map colors to numbers using the COLOR_CODES from config
    for i, color in enumerate(colors, 1):
        if color in COLOR_CODES:
            color_mapping[str(i)] = COLOR_CODES[color]
        elif len(color) >= 2:  # Keep as-is if not in mapping but looks like color code
            color_mapping[str(i)] = color.title()
    
    return color_mapping

def extract_fiber_counts_from_text(text):
    """Extract all fiber counts mentioned in the text, avoiding false positives"""
    fiber_counts = set()
    
    # Use patterns from configuration
    for pattern in FIBER_COUNT_TEXT_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            count = int(match.group(1))
            # Only accept realistic fiber counts from configuration
            if count in VALID_FIBER_COUNTS:
                fiber_counts.add(f"{count}F")
    
    # Also look for comma-separated lists like "24F, 96F"
    comma_pattern = r'(\d+F(?:\s*,\s*\d+F)+)'
    comma_matches = re.finditer(comma_pattern, text, re.IGNORECASE)
    for match in comma_matches:
        individual_counts = re.findall(r'(\d+)F', match.group(1))
        for count_str in individual_counts:
            count = int(count_str)
            if count in VALID_FIBER_COUNTS:
                fiber_counts.add(f"{count}F")
    
    return list(fiber_counts)

def extract_primary_fiber_count_from_filename(filename):
    """Extract the primary fiber count from filename - most reliable method"""
    # Look for patterns like "24F", "96F", etc. in filename
    filename_upper = filename.upper()
    
    # First, try to find complete patterns like "24F,96F" or "144F"
    # Handle comma-separated patterns first
    comma_separated_matches = re.findall(r'(\d+F(?:,\d+F)*)', filename_upper)
    if comma_separated_matches:
        # Split by comma and get all fiber counts
        all_counts = []
        for match in comma_separated_matches:
            counts_in_match = re.findall(r'(\d+)F', match)
            all_counts.extend([int(c) for c in counts_in_match])
        
        if all_counts:
            # Return all valid fiber counts, sorted largest first
            valid_counts = [c for c in all_counts if c in VALID_FIBER_COUNTS]
            if valid_counts:
                valid_counts.sort(reverse=True)
                return [f"{c}F" for c in valid_counts]
    
    # If no comma-separated pattern, look for individual fiber counts
    matches = re.findall(r'(\d+)F', filename_upper)
    if matches:
        # Convert to integers and filter out unrealistic values
        counts = [int(m) for m in matches]
        # Filter to valid fiber counts from configuration
        valid_counts = [c for c in counts if c in VALID_FIBER_COUNTS]
        
        if valid_counts:
            valid_counts.sort(reverse=True)  # Largest first
            return [f"{c}F" for c in valid_counts]
    
    return []

def calculate_fiber_count_from_construction(tables):
    """Calculate actual fiber count from construction parameters"""
    try:
        fibers_per_tube = None
        num_tubes = None
        
        for table in tables:
            for row in table:
                cleaned = [str(cell).strip() for cell in row if cell is not None]
                if len(cleaned) < 2:
                    continue
                
                param_name = cleaned[0].lower()
                
                # Look for fibers per tube
                if any(pattern in param_name for pattern in ['fiber per tube', 'fibre per tube', 'fibres per tube']):
                    for cell in cleaned[1:]:
                        if cell and cell.isdigit():
                            fibers_per_tube = int(cell)
                            break
                
                # Look for number of tubes
                if any(pattern in param_name for pattern in ['number of tube', 'loose tube', 'tubes']):
                    for cell in cleaned[1:]:
                        if cell and cell.isdigit() and int(cell) <= 50:  # Reasonable tube count
                            num_tubes = int(cell)
                            break
        
        if fibers_per_tube and num_tubes:
            total_fibers = fibers_per_tube * num_tubes
            if total_fibers in VALID_FIBER_COUNTS:
                return f"{total_fibers}F"
    except:
        pass
    return None

def extract_text_content(page):
    """Extract all text content from a page including headings and paragraphs"""
    text_content = {}
    
    try:
        # Get all text from the page
        full_text = page.extract_text()
        if not full_text:
            return text_content
        
        lines = full_text.split('\n')
        current_heading = None
        content_buffer = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect headings (lines that are all caps, or have specific patterns)
            if (line.isupper() and len(line) > 3) or any(keyword in line.lower() for keyword in 
                ['specification', 'description', 'technical', 'parameters', 'characteristics']):
                
                # Save previous content if exists
                if current_heading and content_buffer:
                    text_content[current_heading] = ' '.join(content_buffer)
                    content_buffer = []
                
                current_heading = line
            else:
                content_buffer.append(line)
        
        # Save last content
        if current_heading and content_buffer:
            text_content[current_heading] = ' '.join(content_buffer)
    
    except Exception as e:
        print(f"[WARNING] Error extracting text from page: {str(e)}")
        return {}
    
    return text_content

def extract_parameters_from_text(text, detected_fiber_counts):
    """Extract structured parameters from document text when table parsing fails"""
    parameters = {}
    
    # Get all patterns from configuration (including dynamic ones)
    all_patterns = get_all_text_patterns()
    
    for pattern, param_name in all_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Handle patterns with multiple capture groups
            if len(match.groups()) > 1:
                # For patterns like Attenuation with wavelength and value
                if 'attenuation' in param_name.lower():
                    wavelength = match.group(1).strip()
                    value = match.group(2).strip()
                    dynamic_param_name = f"Attenuation at {wavelength}"
                    final_value = clean_parameter_value(f"≤ {value}")
                elif 'mode field diameter' in param_name.lower():
                    wavelength = match.group(1).strip()
                    value = match.group(2).strip()
                    dynamic_param_name = f"MFD at {wavelength}"
                    final_value = clean_parameter_value(value)
                elif 'chromatic dispersion' in param_name.lower():
                    wavelength_range = match.group(1).strip()
                    value = match.group(2).strip()
                    dynamic_param_name = f"Chromatic Dispersion at {wavelength_range}"
                    final_value = clean_parameter_value(f"≤ {value}")
                else:
                    # Default: combine all groups
                    dynamic_param_name = param_name
                    final_value = clean_parameter_value(" ".join(match.groups()).strip())
            else:
                # Single capture group - handle environmental parameters specially
                if 'environmental_installation' in param_name.lower() or 'installation_temp' in param_name.lower():
                    dynamic_param_name = "Installation Temperature"
                    final_value = clean_parameter_value(match.group(1).strip())
                elif 'environmental_operation' in param_name.lower() or 'operation_temp' in param_name.lower():
                    dynamic_param_name = "Operation Temperature"
                    final_value = clean_parameter_value(match.group(1).strip())
                elif 'environmental_storage' in param_name.lower() or 'storage_temp' in param_name.lower():
                    dynamic_param_name = "Storage Temperature" 
                    final_value = clean_parameter_value(match.group(1).strip())
                elif 'tensile_strength_max' in param_name.lower():
                    dynamic_param_name = "Max. Tensile Strength"
                    final_value = clean_parameter_value(match.group(1).strip())
                else:
                    dynamic_param_name = param_name
                    final_value = clean_parameter_value(match.group(1).strip())
            
            # Use enhanced parameter categorization
            section = ensure_parameter_exists(dynamic_param_name, final_value)
            if section not in parameters:
                parameters[section] = {}
            parameters[section][dynamic_param_name] = final_value
    
    return parameters

def extract_color_coding_from_text(text, max_fiber_count=None):
    """Extract color coding sequences from document text with support for tabular data"""
    color_patterns = {}
    
    # Only extract tabular color coding data (Fibre Colour)
    tabular_colors = extract_tabular_color_coding(text, max_fiber_count)
    if tabular_colors:
        color_patterns.update(tabular_colors)
    
    # Skip the fallback color sequence extraction to avoid Color_Sequence_X entries
    
    return color_patterns

def extract_tabular_color_coding(text, max_fiber_count=None):
    """Extract color coding from tabular format in PDF text"""
    color_mapping = {}
    
    # Look for fiber count and color patterns in tabular format
    # Pattern: "Fibre Count 1 2 3 ... Fibre Colour Rd Gr Bl ..."
    fiber_count_pattern = r'Fibre\s+Count\s+((?:\d+\s*)+)'
    fiber_color_pattern = r'Fibre\s+Colour\s+((?:[A-Za-z]{2}\*?\s*)+)'
    
    # Find all fiber count sequences
    count_matches = re.findall(fiber_count_pattern, text, re.IGNORECASE)
    color_matches = re.findall(fiber_color_pattern, text, re.IGNORECASE)
    
    if count_matches and color_matches:
        for i, (count_seq, color_seq) in enumerate(zip(count_matches, color_matches)):
            # Extract fiber numbers
            fiber_numbers = re.findall(r'\d+', count_seq)
            # Extract color codes
            color_codes = re.findall(r'[A-Za-z]{2}\*?', color_seq)
            
            # Map fiber numbers to colors
            for fiber_num, color_code in zip(fiber_numbers, color_codes):
                # Clean color code (remove asterisk if present)
                clean_color = color_code.replace('*', '').lower()
                
                # Convert using COLOR_CODES mapping if available
                if clean_color in COLOR_CODES:
                    color_name = COLOR_CODES[clean_color]
                else:
                    color_name = clean_color.title()
                
                # Only include if within max_fiber_count limit
                if max_fiber_count is None or int(fiber_num) <= max_fiber_count:
                    color_mapping[fiber_num] = color_name
    
    return {"Fibre Colour": color_mapping} if color_mapping else {}

def extract_grouped_data(pdf_path):
    """Enhanced data extraction from PDF with precise table parsing"""
    
    # Store fiber-specific values during parsing
    fiber_specific_values = {}
    # Store column mappings for fiber counts
    fiber_column_mappings = {}
    
    try:
        # Collect all text content first to detect fiber counts
        all_text_content = ""
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        all_text_content += page_text + "\n"
                except Exception as e:
                    print(f"[WARNING] Error reading page text: {str(e)}")
                    continue
        
        # Step 1: Try to get primary fiber counts from filename (most reliable)
        filename = os.path.basename(pdf_path)
        filename_fiber_counts = extract_primary_fiber_count_from_filename(filename)
        
        # Step 2: Detect all fiber counts mentioned in the document text
        text_detected_counts = extract_fiber_counts_from_text(all_text_content)
        
        # Step 3: Extract tables for construction analysis
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
                except Exception as e:
                    continue
        
        # Step 4: Try to calculate fiber count from construction parameters
        calculated_fiber_count = calculate_fiber_count_from_construction(tables)
        
        # Step 5: Determine the final fiber counts using priority order
        detected_fiber_counts = []
        
        # Priority 1: If filename has clear fiber counts, use them as primary
        if filename_fiber_counts:
            detected_fiber_counts.extend(filename_fiber_counts)
            print(f"[INFO] Primary fiber counts from filename: {filename_fiber_counts}")
        
        # Priority 2: If we calculated from construction, validate against filename or add as alternative
        if calculated_fiber_count:
            calc_count = calculated_fiber_count
            if calc_count not in detected_fiber_counts:
                # Only add if it makes sense - either no filename match or it's a reasonable alternative
                if not detected_fiber_counts:
                    detected_fiber_counts.append(calc_count)
                elif int(calc_count.replace('F', '')) in VALID_FIBER_COUNTS:
                    detected_fiber_counts.append(calc_count)
            print(f"[INFO] Calculated fiber count from construction: {calculated_fiber_count}")
        
        # Priority 3: Add relevant text-detected counts only if they're not already covered
        for fc in text_detected_counts:
            count = int(fc.replace('F', ''))
            if fc not in detected_fiber_counts:
                # Be very selective about adding text-detected counts
                if filename_fiber_counts:
                    # Only add if it's already in the filename-detected counts
                    if fc in filename_fiber_counts:
                        if fc not in detected_fiber_counts:
                            detected_fiber_counts.append(fc)
                else:
                    # No filename counts, be more liberal but still filter
                    if count in VALID_FIBER_COUNTS:
                        detected_fiber_counts.append(fc)
        
        # Remove duplicates while preserving order
        unique_counts = []
        for fc in detected_fiber_counts:
            if fc not in unique_counts:
                unique_counts.append(fc)
        detected_fiber_counts = unique_counts
        
        # If still no fiber counts, use text detection as fallback
        if not detected_fiber_counts:
            detected_fiber_counts = text_detected_counts
            print(f"[INFO] Using text-detected fiber counts as fallback: {detected_fiber_counts}")
        
        # Ensure we have at least one fiber count
        if not detected_fiber_counts:
            print(f"[WARNING] No fiber counts detected, defaulting to 24F")
            detected_fiber_counts = ["24F"]
        
        # Initialize data structure for all detected fiber counts
        fibre_data = {}
        for fiber_count in detected_fiber_counts:
            fibre_data[fiber_count] = {
                "Document_Text_Content": {},
                "Technical_Specifications": {}
            }

        current_section = "General Information"

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                
                try:
                    # Extract text content from this page
                    text_content = extract_text_content(page)
                    
                    # Add text content to all fiber counts (since text usually applies to all)
                    for fiber_count in detected_fiber_counts:
                        fibre_data[fiber_count]["Document_Text_Content"][f"Page_{page_num}"] = text_content
                    
                    # Extract color coding from page text
                    page_text = page.extract_text()
                    if page_text:
                        # Extract color coding separately for each fiber count
                        for fiber_count in detected_fiber_counts:
                            # Extract numeric value from fiber count (e.g., "24F" -> 24, "12F" -> 12)
                            match = re.search(r'(\d+)', fiber_count)
                            numeric_count = int(match.group(1)) if match and match.group(1).isdigit() else 0
                            
                            # Extract color coding limited to this specific fiber count
                            color_coding = extract_color_coding_from_text(page_text, numeric_count)
                            if color_coding:
                                fibre_data[fiber_count]["Technical_Specifications"].setdefault("Colour Coding", {}).update(color_coding)
                        
                        # Extract structured parameters from text when table parsing might miss them
                        text_parameters = extract_parameters_from_text(page_text, detected_fiber_counts)
                        if text_parameters:
                            for fiber_count in detected_fiber_counts:
                                for section, params in text_parameters.items():
                                    if section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][section] = {}
                                    for param_name, param_value in params.items():
                                        # Only add if not already present from table extraction
                                        if param_name not in fibre_data[fiber_count]["Technical_Specifications"][section]:
                                            fibre_data[fiber_count]["Technical_Specifications"][section][param_name] = param_value
                        
                        # Enhanced parameter extraction for critical missing values from concatenated text
                        # Use patterns from configuration
                        # Extract Tensile Strength with Installation/Operation values
                        if 'tensile_installation_operation' in ENHANCED_TEXT_PATTERNS:
                            tensile_match = re.search(ENHANCED_TEXT_PATTERNS['tensile_installation_operation'], page_text, re.DOTALL)
                            if tensile_match:
                                installation_val, operation_val = tensile_match.groups()
                                tensile_value = f"Installation: {installation_val} Operation: {operation_val}"
                                param_name = "Max. Tensile Strength"
                                for fiber_count in detected_fiber_counts:
                                    param_section = categorize_parameter(param_name)
                                    if param_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][param_section] = {}
                                    fibre_data[fiber_count]["Technical_Specifications"][param_section][param_name] = tensile_value
                                add_parameter_if_new(param_name, param_section)
                        
                        # Extract other enhanced patterns
                        enhanced_param_mapping = {
                            'crush_resistance': 'Max. Crush Resistance',
                            'impact_resistance': 'Impact Resistance',
                            'impact_strength': 'Impact Strength', 
                            'torsion': 'Torsion',
                            'minimum_bend_radius': 'Minimum Bend Radius',
                            'water_penetration': 'Water Penetration Test',
                            'tensile_strength_max': 'Max. Tensile Strength',
                            'max_tensile_strength': 'Max. Tensile Strength'
                        }
                        
                        for pattern_key, param_name in enhanced_param_mapping.items():
                            if pattern_key in ENHANCED_TEXT_PATTERNS:
                                match = re.search(ENHANCED_TEXT_PATTERNS[pattern_key], page_text)
                                if match:
                                    value = clean_parameter_value(match.group(1))
                                    for fiber_count in detected_fiber_counts:
                                        param_section = categorize_parameter(param_name)
                                        if param_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                            fibre_data[fiber_count]["Technical_Specifications"][param_section] = {}
                                        # Only add if not already present or empty
                                        if (param_name not in fibre_data[fiber_count]["Technical_Specifications"][param_section] or
                                            not fibre_data[fiber_count]["Technical_Specifications"][param_section][param_name]):
                                            fibre_data[fiber_count]["Technical_Specifications"][param_section][param_name] = value
                                    add_parameter_if_new(param_name, param_section)
                        
                        # Extract Environmental Performance temperatures separately
                        temp_patterns = {
                            'environmental_installation': 'Installation Temperature',
                            'environmental_operation': 'Operation Temperature', 
                            'environmental_storage': 'Storage Temperature',
                            'installation_temp': 'Installation Temperature',
                            'operation_temp': 'Operation Temperature',
                            'storage_temp': 'Storage Temperature'
                        }
                        
                        for temp_type, param_name in temp_patterns.items():
                            if temp_type in ENHANCED_TEXT_PATTERNS:
                                temp_match = re.search(ENHANCED_TEXT_PATTERNS[temp_type], page_text)
                                if temp_match:
                                    temp_value = clean_parameter_value(temp_match.group(1))
                                    for fiber_count in detected_fiber_counts:
                                        param_section = categorize_parameter(param_name)
                                        if param_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                            fibre_data[fiber_count]["Technical_Specifications"][param_section] = {}
                                        # Only add if not already present or empty
                                        if (param_name not in fibre_data[fiber_count]["Technical_Specifications"][param_section] or
                                            not fibre_data[fiber_count]["Technical_Specifications"][param_section][param_name]):
                                            fibre_data[fiber_count]["Technical_Specifications"][param_section][param_name] = temp_value
                                    add_parameter_if_new(param_name, param_section)
                        
                        # Extract Attenuation values with wavelengths
                        if 'attenuation' in ENHANCED_TEXT_PATTERNS:
                            attenuation_matches = re.findall(ENHANCED_TEXT_PATTERNS['attenuation'], page_text)
                            for wavelength, value in attenuation_matches:
                                attenuation_value = f"≤ {value} dB/km"
                                param_name = f"Attenuation at {wavelength}nm"
                                for fiber_count in detected_fiber_counts:
                                    param_section = categorize_parameter("Attenuation")
                                    if param_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][param_section] = {}
                                    if param_name not in fibre_data[fiber_count]["Technical_Specifications"][param_section]:
                                        fibre_data[fiber_count]["Technical_Specifications"][param_section][param_name] = attenuation_value
                                add_parameter_if_new(param_name, param_section)
                        
                        # Extract Mode Field Diameter values with wavelengths
                        if 'mode_field_diameter' in ENHANCED_TEXT_PATTERNS:
                            mfd_matches = re.findall(ENHANCED_TEXT_PATTERNS['mode_field_diameter'], page_text)
                            for wavelength, value in mfd_matches:
                                mfd_value = f"{value.strip()} µm"
                                param_name = f"MFD at {wavelength}nm"
                                for fiber_count in detected_fiber_counts:
                                    param_section = categorize_parameter("Mode Field Diameter")
                                    if param_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][param_section] = {}
                                    if param_name not in fibre_data[fiber_count]["Technical_Specifications"][param_section]:
                                        fibre_data[fiber_count]["Technical_Specifications"][param_section][param_name] = mfd_value
                                add_parameter_if_new(param_name, param_section)
                    
                    # Extract table data with precise parsing
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables, 1):
                        if not table or len(table) < 2:
                            continue
                        
                        # Initialize column mappings storage at the start of table processing
                        # fiber_column_mappings is now initialized at function level
                        
                        # Process each row carefully
                        for row_idx, row in enumerate(table):
                            if not row or len(row) < 2:
                                continue

                            # Clean the row data
                            cleaned = [str(cell).strip() if cell else "" for cell in row]
                            
                            # Skip empty rows or rows that are clearly headers
                            if not cleaned[0] or cleaned[0].lower() in [
                                'parameter', 'sl.no.', 'sr.no.', 'specifications', 
                                'description', 'details', 'type', 'color', 'dimensions'
                            ]:
                                continue
                            
                            # Check if this is a fiber count header row (contains "2F", "4F", "8F", etc.)
                            if any(fc_word in cleaned[0].lower() for fc_word in ['fibre count', 'fiber count']):
                                # This row defines column mappings for fiber counts
                                for col_idx in range(1, len(cleaned)):
                                    cell_value = cleaned[col_idx]
                                    if cell_value:
                                        for fc in detected_fiber_counts:
                                            if fc.upper() == cell_value.upper():
                                                fiber_column_mappings[fc] = col_idx
                                                print(f"[INFO] Mapped {fc} to column {col_idx}")
                                
                                # Store the mappings for use in subsequent rows
                                # No need to store as function attribute - use local variable
                                
                                # For the fiber count parameter itself, assign the correct value to each fiber type
                                for fiber_count in detected_fiber_counts:
                                    if current_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][current_section] = {}
                                    fibre_data[fiber_count]["Technical_Specifications"][current_section]["Fiber Count"] = fiber_count.replace('F', '')
                                
                                continue  # Skip further processing of this header row
                            
                            # Determine section based on row content
                            row_text = " ".join(cleaned)
                            new_section = identify_section(row_text)
                            if new_section and new_section != "General Information":
                                current_section = new_section

                            parameter_name = cleaned[0]
                            
                            # Normalize parameter name to prevent duplicates
                            def normalize_parameter_name(name):
                                """Normalize parameter names to prevent duplicate keys."""
                                if not name:
                                    return name
                                
                                # Convert to title case and normalize variations
                                normalized = name.strip().title()
                                
                                # Handle specific variations
                                variations = {
                                    'Fiber Core': 'Fiber Core',
                                    'Fibre Core': 'Fiber Core',
                                    'Fiber Count': 'Fiber Count',
                                    'Fibre Count': 'Fiber Count',
                                    'Od': 'OD',
                                    'I.D': 'ID',
                                    'O.D': 'OD',
                                    'I.D.': 'ID',
                                    'O.D.': 'OD'
                                }
                                
                                for variant, standard in variations.items():
                                    if normalized == variant:
                                        normalized = standard
                                        break
                                
                                return normalized
                            
                            parameter_name = normalize_parameter_name(parameter_name)
                            
                            # Skip fiber count rows as they're handled above
                            if any(fc_word in parameter_name.lower() for fc_word in ['fibre count', 'fiber count']):
                                continue
                            
                            # Handle parameters that should use fiber-specific column mappings
                            if any(phrase in parameter_name.lower() for phrase in [
                                'number of fibres per tube', 'number of fibers per tube', 'fibres per tube', 'fibers per tube'
                            ]):
                                # For "fibres per tube", we need the actual value from the table, not the total fiber count
                                for fiber_count in detected_fiber_counts:
                                    if current_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][current_section] = {}
                                    
                                    # For "fibres per tube", store values in the fiber-specific dictionary
                                    parameter_value = ""
                                    if fiber_count in fiber_column_mappings:
                                        col_idx = fiber_column_mappings[fiber_count]
                                        if col_idx < len(cleaned) and cleaned[col_idx]:
                                            parameter_value = clean_parameter_value(cleaned[col_idx])
                                            # Store the value from the mapped column
                                            if fiber_count not in fiber_specific_values:
                                                fiber_specific_values[fiber_count] = {}
                                            key = f"{current_section}_{parameter_name}"
                                            fiber_specific_values[fiber_count][key] = parameter_value
                                            print(f"[INFO] Stored {fiber_count} {parameter_name} = {parameter_value}")
                                    
                                # Skip further processing for this parameter
                                continue
                            
                            elif any(phrase in parameter_name.lower() for phrase in [
                                'cable diameter', 'cable weight', 'number of loose tubes'
                            ]):
                                # These parameters may have different values for different fiber counts
                                for fiber_count in detected_fiber_counts:
                                    # Use parameter-specific categorization
                                    parameter_section = categorize_parameter(parameter_name)
                                    
                                    # Add new parameter if not known
                                    add_parameter_if_new(parameter_name, parameter_section)
                                    
                                    if parameter_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][parameter_section] = {}
                                    
                                    # Get the value from the appropriate column
                                    if fiber_count in fiber_column_mappings:
                                        col_idx = fiber_column_mappings[fiber_count]
                                        if col_idx < len(cleaned) and cleaned[col_idx]:
                                            parameter_value = clean_parameter_value(cleaned[col_idx])
                                        else:
                                            # Fallback to first available value
                                            parameter_value = clean_parameter_value(cleaned[1]) if len(cleaned) > 1 and cleaned[1] else ""
                                    else:
                                        # No column mapping, use default logic
                                        parameter_value = clean_parameter_value(cleaned[1]) if len(cleaned) > 1 and cleaned[1] else ""
                                    
                                    fibre_data[fiber_count]["Technical_Specifications"][parameter_section][parameter_name] = parameter_value
                                # Use column mappings if available
                                for fiber_count in detected_fiber_counts:
                                    if current_section not in fibre_data[fiber_count]["Technical_Specifications"]:
                                        fibre_data[fiber_count]["Technical_Specifications"][current_section] = {}
                                    
                                    # Get the value from the appropriate column
                                    if fiber_count in fiber_column_mappings:
                                        col_idx = fiber_column_mappings[fiber_count]
                                        if col_idx < len(cleaned) and cleaned[col_idx]:
                                            parameter_value = clean_parameter_value(cleaned[col_idx])
                                        else:
                                            # Fallback to using the fiber count itself for logical parameters
                                            if 'fibres per tube' in parameter_name.lower() or 'fibers per tube' in parameter_name.lower():
                                                parameter_value = fiber_count.replace('F', '')
                                            else:
                                                parameter_value = clean_parameter_value(cleaned[1]) if len(cleaned) > 1 and cleaned[1] else ""
                                    else:
                                        # No column mapping, use default logic
                                        if 'fibres per tube' in parameter_name.lower() or 'fibers per tube' in parameter_name.lower():
                                            parameter_value = fiber_count.replace('F', '')
                                        else:
                                            parameter_value = clean_parameter_value(cleaned[1]) if len(cleaned) > 1 and cleaned[1] else ""
                                    
                                    fibre_data[fiber_count]["Technical_Specifications"][current_section][parameter_name] = parameter_value
                                
                                continue  # Skip the general parameter handaling below.
                            
                            # General parameter handling for parameters that don't need fiber-specific columns
                            else:
                                # Regular parameter handling with fiber-specific column detection
                                parameter_value = None
                                color_sequence = None
                                
                                # Check if this row has fiber count headers in the columns (like "2F", "4F", "8F")
                                fiber_columns = {}
                                for col_idx in range(1, len(cleaned)):
                                    cell_value = cleaned[col_idx]
                                    if cell_value:
                                        # Check if this cell is a fiber count header
                                        for fc in detected_fiber_counts:
                                            if fc.upper() in cell_value.upper() or cell_value.upper() == fc.upper():
                                                fiber_columns[fc] = col_idx
                                
                                # If we found fiber-specific columns, use the appropriate one
                                if fiber_columns and fiber_count in fiber_columns:
                                    col_idx = fiber_columns[fiber_count]
                                    # Look for the parameter value in the next row or same row after the header
                                    # This is a header row, so skip parameter extraction for now 
                                    if any(fc in cleaned for fc in detected_fiber_counts):
                                        continue
                                
                                # Method 1: If there are exactly as many data columns as fiber counts, map them
                                data_columns = [cleaned[i] for i in range(1, len(cleaned)) if cleaned[i] and not any(fc.upper() in cleaned[i].upper() for fc in detected_fiber_counts)]
                                if len(data_columns) == len(detected_fiber_counts):
                                    # Map data columns to fiber counts (assuming they're in the same order)
                                    fiber_index = detected_fiber_counts.index(fiber_count)
                                    if fiber_index < len(data_columns):
                                        parameter_value = data_columns[fiber_index]
                                
                                # Method 2: Look for numeric values or specific patterns and construct complete parameter descriptions
                                if parameter_value is None:
                                    # For parameters that commonly have multi-part values, try to construct complete descriptions
                                    if any(keyword in parameter_name.lower() for keyword in [
                                        'tensile', 'strength', 'attenuation', 'dispersion', 'diameter', 'wavelength', 'bend'
                                    ]):
                                        # Try to construct a complete parameter description from multiple cells
                                        value_parts = []
                                        for col_idx in range(1, len(cleaned)):
                                            cell_value = cleaned[col_idx]
                                            if cell_value and cell_value not in ['---', 'N/A', 'n/a']:
                                                # Clean and add meaningful cell values
                                                clean_cell = cell_value.strip()
                                                if clean_cell:
                                                    value_parts.append(clean_cell)
                                        
                                        if value_parts:
                                            # Join parts intelligently
                                            parameter_value = " ".join(value_parts)
                                            # Clean up excessive spacing
                                            parameter_value = re.sub(r'\s+', ' ', parameter_value).strip()
                                    else:
                                        # Standard single-value extraction for simpler parameters
                                        for col_idx in range(1, len(cleaned)):
                                            cell_value = cleaned[col_idx]
                                            if not cell_value:
                                                continue
                                            
                                            # Check if this looks like a parameter value (numbers, units, ranges, etc.)
                                            if (re.search(r'\d+', cell_value) and 
                                                (any(unit in cell_value.lower() for unit in ['mm', 'km', 'db', 'nm', 'ps', 'µm', 'kg', 'n', 'j', '°c', 'kn']) or
                                                 any(char in cell_value for char in ['±', '≤', '≥', '%', '-', '/']))):
                                                parameter_value = cell_value
                                                break
                                            
                                            # Check if this is a descriptive value (materials, types, etc.)
                                            elif (len(cell_value) > 2 and 
                                                  not cell_value.lower() in ['color', 'colour', 'type'] and
                                                  not re.match(r'^[a-z]{2}$', cell_value.lower())):  # Not just color codes
                                                parameter_value = cell_value
                                                break
                                
                                # Method 3: Look for color sequences if parameter relates to color
                                if any(color_word in parameter_name.lower() for color_word in ['color', 'colour']):
                                    # Find color sequence in the row
                                    color_cells = []
                                    for col_idx in range(1, len(cleaned)):
                                        cell_value = cleaned[col_idx]
                                        if (cell_value and len(cell_value) <= 4 and 
                                            re.match(r'^[a-z]{2,4}$', cell_value.lower())):  # Looks like color code
                                            color_cells.append(cell_value)
                                    
                                    if color_cells:
                                        color_sequence = ' '.join(color_cells)
                                        parameter_value = parse_color_sequence(color_sequence)
                                
                                # Method 4: If no clear value found, take the most meaningful non-empty cell
                                if parameter_value is None:
                                    for col_idx in range(1, len(cleaned)):
                                        cell_value = cleaned[col_idx]
                                        if cell_value and cell_value.lower() not in ['---', 'n/a', 'na']:
                                            parameter_value = cell_value
                                            break
                            
                            # Store the parameter - handle multi-column tables with fiber-specific values
                            if parameter_value is not None:
                                # Check if this row has different values for different fiber counts
                                local_fiber_values = {}
                                
                                # Look for header row that might contain fiber count identifiers
                                if any(fc_pattern in ' '.join(cleaned).upper() for fc_pattern in [f'{fc}' for fc in detected_fiber_counts]):
                                    # This row contains fiber count headers, try to map columns
                                    for col_idx in range(1, len(cleaned)):
                                        cell_value = cleaned[col_idx]
                                        if cell_value:
                                            # Check if this cell matches a detected fiber count
                                            for fc in detected_fiber_counts:
                                                if fc in cell_value.upper() or cell_value.upper() in fc:
                                                    local_fiber_values[fc] = {'column': col_idx, 'header': cell_value}
                                
                                # If we found column mappings, use them for subsequent parameter extraction
                                if local_fiber_values:
                                    # Store column mappings for future use
                                    # Store column mappings for future use
                                    global COLUMN_MAPPINGS
                                    COLUMN_MAPPINGS = local_fiber_values 
                                    
                                    # For fiber count parameter, assign the correct values
                                    if any(fc_word in parameter_name.lower() for fc_word in ['fibre count', 'fiber count']):
                                        for fc in detected_fiber_counts:
                                            if current_section not in fibre_data[fc]["Technical_Specifications"]:
                                                fibre_data[fc]["Technical_Specifications"][current_section] = {}
                                            fibre_data[fc]["Technical_Specifications"][current_section][parameter_name] = fc.replace('F', '')
                                    else:
                                        # For other parameters in header row, don't assign values yet
                                        continue
                                else:
                                    # Check if we have column mappings from a previous header row
                                    # Use existing global column mappings if available
                                    if COLUMN_MAPPINGS:
                                        # Extract fiber-specific values based on column mappings
                                        for fc in detected_fiber_counts:
                                            # Skip color-related parameters to avoid overriding tabular color extraction
                                            if any(color_term in parameter_name.lower() for color_term in ['fibre colour', 'fiber colour', 'colour', 'color']):
                                                continue
                                                
                                            # Use enhanced parameter categorization
                                            parameter_section = ensure_parameter_exists(parameter_name, parameter_value)
                                            
                                            if fc in COLUMN_MAPPINGS:
                                                col_idx = COLUMN_MAPPINGS[fc]['column']
                                                if col_idx < len(cleaned):
                                                    specific_value = clean_parameter_value(cleaned[col_idx]) if cleaned[col_idx] else clean_parameter_value(parameter_value)
                                                    
                                                    if parameter_section not in fibre_data[fc]["Technical_Specifications"]:
                                                        fibre_data[fc]["Technical_Specifications"][parameter_section] = {}
                                                    fibre_data[fc]["Technical_Specifications"][parameter_section][parameter_name] = specific_value
                                            else:
                                                # No specific column mapping, use shared value
                                                if parameter_section not in fibre_data[fc]["Technical_Specifications"]:
                                                    fibre_data[fc]["Technical_Specifications"][parameter_section] = {}
                                                fibre_data[fc]["Technical_Specifications"][parameter_section][parameter_name] = clean_parameter_value(parameter_value)
                                    else:
                                        # No column mappings, assign same value to all fiber counts
                                        for fiber_count in detected_fiber_counts:
                                            # Skip color-related parameters to avoid overriding tabular color extraction
                                            if any(color_term in parameter_name.lower() for color_term in ['fibre colour', 'fiber colour', 'colour', 'color']):
                                                continue
                                                
                                            # Use enhanced parameter categorization
                                            parameter_section = ensure_parameter_exists(parameter_name, parameter_value)
                                            
                                            # Check if this parameter already exists in any other section to avoid duplicates
                                            existing_sections = []
                                            for section_name, section_data in fibre_data[fiber_count]["Technical_Specifications"].items():
                                                if parameter_name in section_data:
                                                    existing_sections.append(section_name)
                                            
                                            # Only add if not already present in the correct section
                                            if parameter_section not in existing_sections:
                                                if isinstance(parameter_value, dict):  # Color coding
                                                    section_data = fibre_data[fiber_count]["Technical_Specifications"].setdefault("Colour Coding", {})
                                                    section_data[parameter_name] = parameter_value
                                                else:
                                                    section_data = fibre_data[fiber_count]["Technical_Specifications"].setdefault(parameter_section, {})
                                                    section_data[parameter_name] = clean_parameter_value(parameter_value)
                                                    
                                                # Remove from incorrect sections if present
                                                for wrong_section in existing_sections:
                                                    if wrong_section != parameter_section:
                                                        del fibre_data[fiber_count]["Technical_Specifications"][wrong_section][parameter_name]
                
                except Exception as e:
                    print(f"[WARNING] Error processing page {page_num}: {str(e)}")
                    continue

        # Apply stored fiber-specific values at the end
        for fc, vals in fiber_specific_values.items():
            for key, value in vals.items():
                # key format: "Section_Parameter Name"
                if '_' in key:
                    sec, param = key.split('_', 1)
                    section_dict = fibre_data[fc]["Technical_Specifications"].setdefault(sec, {})
                    section_dict[param] = value
        
        # Clean up duplicate parameters - ensure each parameter is only in its correct section
        for fiber_count in detected_fiber_counts:
            specs = fibre_data[fiber_count]["Technical_Specifications"]
            parameters_to_move = {}
            
            # Find all parameters and their correct sections
            for section_name, section_data in specs.items():
                for param_name in list(section_data.keys()):
                    correct_section = categorize_parameter(param_name)
                    if correct_section != section_name:
                        # Mark for moving
                        if correct_section not in parameters_to_move:
                            parameters_to_move[correct_section] = {}
                        parameters_to_move[correct_section][param_name] = section_data[param_name]
                        # Remove from wrong section
                        del section_data[param_name]
            
            # Move parameters to correct sections
            for correct_section, params in parameters_to_move.items():
                if correct_section not in specs:
                    specs[correct_section] = {}
                for param_name, param_value in params.items():
                    # Only add if not already present in correct section
                    if param_name not in specs[correct_section]:
                        specs[correct_section][param_name] = param_value
        
        return fibre_data, detected_fiber_counts
    
    except Exception as e:
        print(f"[ERROR] Failed to process PDF {pdf_path}: {str(e)}")
        return {}, []


# --- FastAPI endpoint for PDF upload and extraction ---
@app.post("/extract")
async def extract_pdf(file: UploadFile = File(...)):
    """
    Accepts a PDF file upload, extracts fiber optic cable data, and returns JSON.
    (MongoDB saving placeholder included for future integration.)
    """
    try:
        # Save uploaded file to a temporary location (or use in-memory if possible)
        contents = await file.read()
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}.pdf")
        with open(temp_path, "wb") as f:
            f.write(contents)

        # Use the main extraction logic on the uploaded file
        grouped_data, detected_fiber_counts = extract_grouped_data(temp_path)

        # Prepare output for all detected fiber counts
        results = []
        for fiber_count in detected_fiber_counts:
            has_table_data = any(grouped_data[fiber_count]["Technical_Specifications"].values())
            has_text_data = any(grouped_data[fiber_count]["Document_Text_Content"].values())
            if has_table_data or has_text_data:
                output_json = {
                    "metadata": {
                        "source_file": file.filename,
                        "fiber_type": fiber_count,
                        # Use current date or datetime.now() if needed
                        "processing_date": "2025-08-11",
                        "detected_fiber_counts": detected_fiber_counts
                    },
                    "document_content": grouped_data[fiber_count]["Document_Text_Content"],
                    "technical_specifications": grouped_data[fiber_count]["Technical_Specifications"]
                }
                # --- Placeholder for MongoDB integration ---
                # from pymongo import MongoClient
                # client = MongoClient("mongodb://localhost:27017/")
                # db = client["your_db_name"]
                # db["your_collection_name"].insert_one(output_json)
                results.append(output_json)

        os.remove(temp_path)
        if not results:
            return JSONResponse(status_code=400, content={"error": "No meaningful data extracted from PDF."})
        # Return JSON results to Angular frontend
        return JSONResponse(status_code=200, content={"results": results})
    except Exception as e:
        print(f"[EXTRACT_PDF ERROR] {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})



# Serve Angular 13 production build (update path to your build folder)
from fastapi.staticfiles import StaticFiles
import pathlib

# Path to Angular build output
angular_dist = pathlib.Path(__file__).parent / "salesaidocumentation" / "dist"
# Find the actual app folder inside dist (since Angular 13 outputs dist/<app-name>)
if angular_dist.exists():
    for sub in angular_dist.iterdir():
        if sub.is_dir():
            app_dist = sub
            break
    else:
        app_dist = angular_dist
    app.mount("/", StaticFiles(directory=str(app_dist), html=True), name="frontend")

# To run locally: uvicorn main:app --reload

# Alias /api/upload to /extract for Angular proxy
from fastapi import Request
@app.post("/api/upload")
async def api_upload_proxy(request: Request):
    print("UPLOAD ENDPOINT HIT")
    try:
        form = await request.form()
        print("FORM RECEIVED:", form)
        file = form["file"]
        print("FILE RECEIVED:", file)
        result = await extract_pdf(file)
        print("EXTRACT_PDF RESULT:", result)
        return result
    except Exception as e:
        print(f"[UPLOAD ENDPOINT ERROR] {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})