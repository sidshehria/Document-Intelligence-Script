"""
Configuration file for PDF processing parameters, dictionaries, and regex patterns.
This file contains all the categorization rules, parameter mappings, and patterns
used for extracting and organizing fiber optic cable specifications.
"""

import re
import json
import os

# Section categorization keywords
SECTION_KEYWORDS = {
    "Cable Construction": [
        "cable", "construction", "fibre count", "fiber count", "outer sheath", "central strength member",
        "type of cable", "cable type", "structure", "design", "core", "tube", "elements",
        "fibres per tube", "fibers per tube", "number of fibres", "number of fibers", 
        "loose tubes", "loose tube", "number of loose", "fillers", "moisture barrier",
        "core wrapping", "ripcords", "cable diameter", "cable weight", "armoring", "armouring"
    ],
    "Colour Coding": [
        "fibre colour", "fiber colour", "tube colour", "color coding", "identification",
        "colour code", "fiber identification"
    ],
    "Mechanical Characteristics": [
        "tensile strength", "crush resistance", "impact strength", "mechanical properties",
        "bend radius", "temperature", "operating temperature", "installation", "service"
    ],
    "Optical Characteristics": [
        "attenuation", "pmd", "chromatic dispersion", "mfd", "mode field diameter",
        "optical parameters", "bandwidth", "wavelength", "loss", "numerical aperture"
    ],
    "Physical Specifications": [
        "diameter", "weight", "dimensions", "size", "length", "overall diameter",
        "cable weight", "nominal", "physical"
    ],
    "Standards & Compliance": [
        "standards", "compliance", "specification", "iec", "itu", "ansi", "telcordia"
    ],
    "Packaging & Marking": [
        "packaging", "cable marking", "wooden drums", "packing", "printing details",
        "marking", "labels", "drums"
    ]
}

# Fiber count patterns for detection
FIBER_COUNT_PATTERNS = [
    r'(\d+)F', r'(\d+)\s*fiber', r'(\d+)\s*fibre', 
    r'(\d+)\s*core', r'(\d+)F\b', r'\b(\d+)F\b'
]

# Parameter categorization mappings
PARAMETER_CATEGORIES = {
    "Cable Construction": [
        "fibre count", "fiber count", "number of fibres per tube", "number of fibers per tube",
        "fibres per tube", "fibers per tube", "number of loose tubes", "loose tubes",
        "central strength member", "number of fillers", "fillers", "moisture barrier",
        "core wrapping", "outer sheath", "inner sheath", "number of ripcords", "ripcords",
        "cable diameter", "cable weight", "armoring", "armouring", "loose tube od", 
        "overall cable diameter", "tube count", "tube od", "peripheral strength member"
    ],
    "Cable Characteristics": [
        "tensile strength", "crush resistance", "impact strength", "torsion",
        "minimum bend radius", "bend radius", "water penetration test",
        "environmental performance", "installation", "operation", "storage",
        "temperature performance", "impact resistance"
    ],
    "Fiber Characteristics": [
        "fibre type", "fiber type", "attenuation", "chromatic dispersion", 
        "pmd", "polarisation mode dispersion", "pmd (max. individual)", "pmd (link design value)",
        "cable cut off wavelength", "cut-off wavelength", "cut off wavelength", "λcc",
        "mfd", "mode field diameter", "core cladding concentricity", "core-cladding concentricity error",
        "cladding diameter", "cladding non-circularity", "cladding non circularity", 
        "coating diameter", "numerical aperture", "zero dispersion"
    ],
    "Physical Specifications": [
        "drum length"
    ],
    "Standards & Compliance": [
        "cpr class", "standards", "compliance"
    ]
}

# Color code mappings
COLOR_CODES = {
    'bl': 'Blue', 'or': 'Orange', 'gr': 'Green', 'br': 'Brown', 
    'wh': 'White', 'gy': 'Gray', 'rd': 'Red', 'bk': 'Black',
    'ye': 'Yellow', 'vi': 'Violet', 'pk': 'Pink', 'cy': 'Cyan',
    'yl': 'Yellow', 'sl': 'Silver', 'nt': 'Natural', 'aq': 'Aqua',
    'fi': 'Fiber', 'ca': 'Clear', 'na': 'Natural',
    'blue': 'Blue', 'orange': 'Orange', 'green': 'Green', 'brown': 'Brown',
    'white': 'White', 'gray': 'Gray', 'red': 'Red', 'black': 'Black',
    'yellow': 'Yellow', 'violet': 'Violet', 'pink': 'Pink', 'cyan': 'Cyan',
    'silver': 'Silver', 'natural': 'Natural', 'aqua': 'Aqua', 'clear': 'Clear'
}

# Regex patterns for parameter extraction from text
TEXT_PARAMETER_PATTERNS = [
    (r'Number of Fiber per tube\s+(\d+)', 'Number Of Fibres Per Tube'),
    (r'Number of Fibre per tube\s+(\d+)', 'Number Of Fibres Per Tube'),
    (r'Number of Loose Tubes\s+(\d+)', 'Number Of Loose Tubes'),
    (r'Loose Tube OD\s+([\d.±\s]+mm)', 'Loose Tube OD'),
    (r'Central Strength Member\s+([\d.±\s]+mm\s+[A-Z]+\s+[A-Z]+)', 'Central Strength Member'),
    (r'Overall Cable Diameter\s+([\d.±\s]+mm)', 'Cable Diameter'),
    (r'Cable Diameter\s+([\d.±\s]+mm)', 'Cable Diameter'),
    (r'Cable Weight\s+([\d.±\s]+kg/km)', 'Cable Weight'),
    (r'Number of Ripcords\s+(\d+)', 'Number Of Ripcords'),
    (r'Inner Sheath\s+([\d.]+\s+mm\s+\([^)]+\)\s+[A-Z]+\s+-\s+[A-Z]+)', 'Inner Sheath'),
    (r'Outer Sheath\s+([\d.]+\s+mm\s+\([^)]+\)\s+[A-Z\s-]+)', 'Outer Sheath'),
    (r'Armoring\s+---\s+([A-Z\s]+Tape)', 'Armoring'),
    (r'Peripheral Strength Member\s+([A-Z\s]+Yarn)', 'Peripheral Strength Member'),
    (r'Moisture Barrier\s+---\s+([A-Z\s]+Gel)', 'Moisture Barrier'),
    (r'Core Wrapping\s+---\s+([A-Z\s]+Tape)', 'Core Wrapping'),
    (r'Tensile Strength\s+(?:at\s+)?(\d+\s*nm\s*≤\s*[\d.]+\s*dB/km\s+[\d.]+W@[\d.]+\s*%\s*Fiber\s*Strain)', 'Tensile Strength'),
    (r'(\d+\.?\d*W\s*@\s*[\d.]+\s*%\s*Fiber\s*Strain)\s+Installation', 'Max. Tensile Strength'),
    (r'Attenuation\s+at\s+(\d+\s*nm)\s*≤?\s*([\d.]+\s*dB/km)', 'Attenuation'),
    (r'at\s+(\d+\s*nm)\s*≤?\s*([\d.]+\s*dB/km)', 'Attenuation'),
    (r'(?:at\s+)?(\d+\s*nm)\s+([\d.±\s]+µm)', 'Mode Field Diameter'),
    (r'Mode Field Diameter\s+at\s+(\d+\s*nm)\s+([\d.±\s]+µm)', 'Mode Field Diameter'),
    (r'(\d+\s*-\s*\d+\s*nm)\s*≤?\s*([\d.]+\s*ps/nm\.km)', 'Chromatic Dispersion'),
    (r'Chromatic Dispersion\s+(\d+\s*nm)\s*≤?\s*([\d.]+\s*ps/nm\.km)', 'Chromatic Dispersion')
]

# Specific fiber count patterns for text detection
FIBER_COUNT_TEXT_PATTERNS = [
    r'(?:fiber|fibre)\s+count:?\s*(\d+)F?',  # "fiber count: 24" or "fibre count 24F"
    r'(\d+)F\s+(?:fiber|fibre)',            # "24F fiber" or "96F fibre"
    r'(\d+)F\s*[,/&]',                      # "24F," or "96F/"
    r'(\d+)F\s*(?:cable|optical)',          # "24F cable"
    r'(?:^|\s)(\d+)F(?=\s|$|[,/&])',       # standalone "24F" with word boundaries
]

# Valid fiber counts (to avoid false positives)
VALID_FIBER_COUNTS = [2, 4, 6, 8, 12, 24, 48, 96, 144, 288]

# Enhanced parameter extraction patterns for complex text
ENHANCED_TEXT_PATTERNS = {
    'tensile_installation_operation': r'Installation:\s*(\d+\s*N)\s*.*?Operation:\s*(\d+\s*N)',
    'max_tensile_strength': r'(?:Max\.\s*)?Tensile\s*Strength\s*\(max\.\)\s*(\d+\s*N)(?:\s*IEC-[\d-]+)?',
    'tensile_strength_max': r'Tensile\s*Strength\s*\(max\.\)\s*(\d+\s*N)(?:\s*IEC-[\d-]+)?',
    'crush_resistance': r'(?:Max\.\s*)?Crush\s*Resistance\s*([\d.]+\s*N/[\d.]+\s*(?:x\s*[\d.]+\s*)?(?:mm|cm))(?:\s*IEC-[\d-]+)?',
    'impact_resistance': r'Impact\s*(?:Resistance|Strength)\s*([\d.]+\s*N\.m)(?:\s*IEC-[\d-]+)?',
    'impact_strength': r'Impact\s*Strength\s*([\d.]+\s*N\.m)(?:\s*IEC-[\d-]+)?',
    'torsion': r'Torsion\s*(±\s*\d+\s*°)(?:\s*IEC-[\d-]+)?',
    'minimum_bend_radius': r'Minimum\s*Bend\s*Radius\s*([\d.]+\s*(?:x\s*D|mm))(?:\s*IEC-[\d-]+)?',
    'water_penetration': r'Water\s*Penetration\s*Test\s*([\d.]+\s*m\s*water\s*head,\s*[\d.]+\s*m\s*sample,\s*[\d.]+\s*hours)(?:\s*IEC-[\d-]+)?',
    'environmental_installation': r'Installation\s+([-+]?\d+\s*°C\s*to\s*[+-]?\d+\s*°C)(?:\s+Environmental Performance)?',
    'environmental_operation': r'(?:Environmental Performance\s+)?Operation\s+([-+]?\d+\s*°C\s*to\s*[+-]?\d+\s*°C)',
    'environmental_storage': r'Storage\s+([-+]?\d+\s*°C\s*to\s*[+-]?\d+\s*°C)',
    'installation_temp': r'Installation\s+([-+]?\d+\s*°C\s*to\s*[+-]?\d+\s*°C)(?:\s+Environmental Performance)?',
    'operation_temp': r'(?:Environmental Performance\s+)?Operation\s+([-+]?\d+\s*°C\s*to\s*[+-]?\d+\s*°C)', 
    'storage_temp': r'Storage\s+([-+]?\d+\s*°C\s*to\s*[+-]?\d+\s*°C)',
    'attenuation': r'(\d+)\s*nm\s*≤\s*([\d.]+)\s*dB/km',
    'mode_field_diameter': r'(\d+)\s*nm\s+([\d.±\s]+)\s*µm'
}

# Configuration file path for storing new parameters
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'dynamic_parameters.json')

class ParameterManager:
    """Class to manage dynamic parameter addition and configuration updates"""
    
    def __init__(self):
        self.dynamic_params = self.load_dynamic_parameters()
    
    def load_dynamic_parameters(self):
        """Load dynamically added parameters from JSON file"""
        if os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARNING] Error loading dynamic parameters: {e}")
                return {}
        return {}
    
    def save_dynamic_parameters(self):
        """Save dynamic parameters to JSON file"""
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.dynamic_params, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Dynamic parameters saved to {CONFIG_FILE_PATH}")
        except Exception as e:
            print(f"[ERROR] Failed to save dynamic parameters: {e}")
    
    def add_new_parameter(self, parameter_name, section, pattern=None, description=None):
        """Add a new parameter to the dynamic configuration"""
        param_lower = parameter_name.lower()
        
        # Check if parameter already exists in static configuration
        for category, params in PARAMETER_CATEGORIES.items():
            if param_lower in [p.lower() for p in params]:
                print(f"[INFO] Parameter '{parameter_name}' already exists in {category}")
                return category
        
        # Check if parameter exists in dynamic configuration
        if 'parameters' not in self.dynamic_params:
            self.dynamic_params['parameters'] = {}
        
        if section not in self.dynamic_params['parameters']:
            self.dynamic_params['parameters'][section] = []
        
        # Add if not already present
        if param_lower not in [p.lower() for p in self.dynamic_params['parameters'][section]]:
            self.dynamic_params['parameters'][section].append(parameter_name)
            
            # Auto-generate pattern if not provided
            if not pattern:
                pattern = self.generate_pattern_for_parameter(parameter_name)
            
            # Add pattern
            if pattern:
                if 'patterns' not in self.dynamic_params:
                    self.dynamic_params['patterns'] = []
                self.dynamic_params['patterns'].append((pattern, parameter_name))
            
            # Add to section keywords for better detection
            self.add_new_section_keyword(section, parameter_name.split()[0])
            
            # Add description if provided
            if description:
                if 'descriptions' not in self.dynamic_params:
                    self.dynamic_params['descriptions'] = {}
                self.dynamic_params['descriptions'][parameter_name] = description
            
            self.save_dynamic_parameters()
            print(f"[INFO] Added new parameter '{parameter_name}' to section '{section}' with auto-generated pattern")
        
        return section
    
    def generate_pattern_for_parameter(self, parameter_name):
        """Auto-generate regex pattern for a parameter"""
        import re
        
        # Clean parameter name for pattern matching
        clean_name = re.escape(parameter_name.lower())
        
        # Handle specific parameter types with special patterns
        param_lower = parameter_name.lower()
        
        if 'attenuation' in param_lower:
            # Pattern for attenuation with any wavelength
            return r'(?:attenuation\s+at\s+)?(\d+\s*nm)\s*≤?\s*([\d.]+\s*dB/km)'
        elif 'mode field diameter' in param_lower or 'mfd' in param_lower:
            # Pattern for MFD with any wavelength
            return r'(?:mode\s+field\s+diameter\s+at\s+|mfd\s+at\s+)?(\d+\s*nm)\s+([\d.±\s]+µm)'
        elif 'chromatic dispersion' in param_lower:
            # Pattern for chromatic dispersion with any wavelength range
            return r'(?:chromatic\s+dispersion\s+)?(\d+\s*(?:-\s*\d+)?\s*nm)\s*≤?\s*([\d.]+\s*ps/nm\.km)'
        elif 'wavelength' in param_lower:
            # Pattern for wavelength parameters
            return r'(?:' + clean_name.replace(r'\ ', r'\s+') + r')\s*([\d.-]+\s*nm)'
        elif any(unit in param_lower for unit in ['diameter', 'weight', 'length', 'radius']):
            # Pattern for measurements
            units = r'(?:mm|kg/km|km|m|µm|nm)'
            return r'(?:' + clean_name.replace(r'\ ', r'\s+') + r')[:\s]*([\d.±\s]+\s*' + units + r')'
        elif any(perf in param_lower for perf in ['strength', 'resistance', 'force']):
            # Pattern for performance parameters
            units = r'(?:N|kN|N/mm|N\.m|kg)'
            return r'(?:' + clean_name.replace(r'\ ', r'\s+') + r')[:\s]*([\d.±\s]+\s*' + units + r')'
        else:
            # Replace common variations for general parameters 
            variations = [
                clean_name,
                clean_name.replace(r'\ ', r'\s+'),  # Handle spaces
                clean_name.replace(r'fibre', r'fibr?e?'),  # Handle fiber/fibre
                clean_name.replace(r'fiber', r'fibr?e?'),  # Handle fiber/fibre
                clean_name.replace(r'colour', r'colou?r'),  # Handle color/colour
                clean_name.replace(r'diameter', r'dia\.?(?:meter)?'),  # Handle dia/diameter
            ]
            
            # Create pattern that matches the parameter name followed by value
            param_pattern = f"(?:{'|'.join(variations)})"
            value_pattern = r'[:\s]*([^,\n]+?)(?=\s*(?:[A-Z][a-z]|$|\n))'
            
            return f"{param_pattern}{value_pattern}"
    
    def get_parameter_category(self, parameter_name):
        """Get the category/section for a parameter, including dynamic parameters"""
        param_lower = parameter_name.lower()
        
        # Check static configuration first
        for category, params in PARAMETER_CATEGORIES.items():
            if any(param.lower() in param_lower or param_lower in param.lower() for param in params):
                return category
        
        # Check dynamic configuration
        if 'parameters' in self.dynamic_params:
            for section, params in self.dynamic_params['parameters'].items():
                if any(param.lower() in param_lower or param_lower in param.lower() for param in params):
                    return section
        
        # Return default based on section keywords with enhanced keyword matching
        return self.identify_section_from_keywords(parameter_name)
    
    def identify_section_from_keywords(self, text):
        """Identify section based on keywords including dynamic keywords"""
        text_lower = text.lower()
        
        # Get all keywords (static + dynamic)
        all_keywords = self.get_section_keywords()
        
        # Check each section's keywords
        for section, keywords in all_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return section
        
        # Enhanced keyword matching based on parameter content
        if any(word in text_lower for word in ['fiber', 'fibre', 'attenuation', 'dispersion', 'mode', 'wavelength', 'core', 'cladding']):
            return "Fiber Characteristics"
        elif any(word in text_lower for word in ['tube', 'diameter', 'weight', 'sheath', 'armor', 'strength', 'construction']):
            return "Cable Construction"
        elif any(word in text_lower for word in ['tensile', 'crush', 'bend', 'temperature', 'environmental', 'torsion', 'impact']):
            return "Cable Characteristics"
        elif any(word in text_lower for word in ['color', 'colour', 'coding']):
            return "Colour Coding"
        elif any(word in text_lower for word in ['drum', 'length', 'packing', 'marking']):
            return "Physical Specifications"
        
        return "General Information"
    
    def get_all_patterns(self):
        """Get all patterns including dynamic ones"""
        patterns = list(TEXT_PARAMETER_PATTERNS)
        
        if 'patterns' in self.dynamic_params:
            patterns.extend(self.dynamic_params['patterns'])
        
        return patterns
    
    def add_new_section_keyword(self, section, keyword):
        """Add a new keyword to a section (only if meaningful)"""
        # Skip very common/generic words
        generic_words = {'of', 'the', 'and', 'or', 'in', 'at', 'to', 'for', 'with', 'number', 'type', 'mode'}
        if keyword.lower() in generic_words or len(keyword) < 3:
            return
            
        if 'section_keywords' not in self.dynamic_params:
            self.dynamic_params['section_keywords'] = {}
        
        if section not in self.dynamic_params['section_keywords']:
            self.dynamic_params['section_keywords'][section] = []
        
        if keyword.lower() not in [k.lower() for k in self.dynamic_params['section_keywords'][section]]:
            self.dynamic_params['section_keywords'][section].append(keyword)
            print(f"[INFO] Added keyword '{keyword}' to section '{section}'")
    
    def get_section_keywords(self):
        """Get all section keywords including dynamic ones"""
        all_keywords = SECTION_KEYWORDS.copy()
        
        if 'section_keywords' in self.dynamic_params:
            for section, keywords in self.dynamic_params['section_keywords'].items():
                if section in all_keywords:
                    all_keywords[section].extend(keywords)
                else:
                    all_keywords[section] = keywords
        
        return all_keywords

# Global parameter manager instance
param_manager = ParameterManager()

# Helper functions that use the parameter manager
def identify_section(row_text):
    """Enhanced section identification with case-insensitive matching"""
    return param_manager.identify_section_from_keywords(row_text)

def categorize_parameter(parameter_name):
    """Categorize parameters based on their names to ensure proper section assignment"""
    return param_manager.get_parameter_category(parameter_name)

def get_all_text_patterns():
    """Get all text extraction patterns"""
    return param_manager.get_all_patterns()

def add_parameter_if_new(parameter_name, suggested_section=None, pattern=None, description=None):
    """Add a new parameter if it doesn't exist"""
    if not suggested_section:
        suggested_section = identify_section(parameter_name)
    
    return param_manager.add_new_parameter(parameter_name, suggested_section, pattern, description)

def ensure_parameter_exists(parameter_name, parameter_value=None):
    """Ensure a parameter exists in the configuration, add if missing"""
    # First try to find existing category
    existing_category = categorize_parameter(parameter_name)
    
    # If it's in "General Information", it might be a new parameter
    if existing_category == "General Information":
        # Try to determine better category based on the parameter name and value
        better_category = param_manager.identify_section_from_keywords(parameter_name)
        if parameter_value:
            # Use value to help categorize
            combined_text = f"{parameter_name} {parameter_value}"
            better_category = param_manager.identify_section_from_keywords(combined_text)
        
        # Add the parameter to the better category
        return add_parameter_if_new(parameter_name, better_category)
    
    return existing_category
