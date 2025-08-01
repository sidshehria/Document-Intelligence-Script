# PDF Processing Configuration System

This project has been refactored to use a separate configuration file (`config_parameters.py`) for managing parameters, dictionaries, and regex patterns. This makes it easier to maintain and extend the system.

## File Structure

- `main.py` - Main PDF processing script
- `config_parameters.py` - Configuration file with all parameters, patterns, and categorization rules
- `dynamic_parameters.json` - Automatically created file to store new parameters discovered during processing
- `test_config.py` - Test script to verify configuration system

## How It Works

### Parameter Categories
Parameters are automatically categorized into sections:
- **Cable Construction** - Physical cable structure (fiber count, tubes, sheath, etc.)
- **Cable Characteristics** - Mechanical properties (tensile strength, bend radius, etc.)
- **Fiber Characteristics** - Optical properties (attenuation, dispersion, MFD, etc.)
- **Physical Specifications** - Physical measurements (diameter, weight, etc.)
- **Standards & Compliance** - Standards and certifications
- **Colour Coding** - Fiber and tube color schemes
- **Packaging & Marking** - Packaging and marking information

### Dynamic Parameter Addition

When the system encounters a new parameter that doesn't exist in the configuration:

1. **Automatic Detection** - The system identifies unknown parameters during processing
2. **Smart Categorization** - Uses keyword matching to suggest the appropriate section
3. **Persistent Storage** - Saves new parameters to `dynamic_parameters.json`
4. **Immediate Availability** - New parameters are immediately available for future processing

### Configuration Files

#### `config_parameters.py`
Contains all static configuration:
- `SECTION_KEYWORDS` - Keywords for section identification
- `PARAMETER_CATEGORIES` - Parameter categorization mappings
- `COLOR_CODES` - Color abbreviation mappings
- `TEXT_PARAMETER_PATTERNS` - Regex patterns for text extraction
- `VALID_FIBER_COUNTS` - Valid fiber count values
- `ENHANCED_TEXT_PATTERNS` - Advanced extraction patterns

#### `dynamic_parameters.json` (auto-created)
Stores dynamically discovered parameters:
```json
{
  "parameters": {
    "Section Name": ["Parameter 1", "Parameter 2"]
  },
  "patterns": [
    ["regex_pattern", "Parameter Name"]
  ],
  "descriptions": {
    "Parameter Name": "Description of parameter"
  }
}
```

## Usage

### Running the Main Script
```bash
python main.py
```

The script will automatically:
1. Load configuration from `config_parameters.py`
2. Load any dynamic parameters from `dynamic_parameters.json`
3. Process PDF files and categorize parameters
4. Add any new parameters to the dynamic configuration
5. Save updates to `dynamic_parameters.json`

### Testing the Configuration
```bash
python test_config.py
```

### Adding New Parameters Manually

You can add new parameters programmatically:

```python
from config_parameters import add_parameter_if_new

# Add a new parameter
add_parameter_if_new(
    parameter_name="New Parameter Name",
    suggested_section="Appropriate Section",
    pattern=r"Pattern\s+(.*)",  # Optional regex pattern
    description="Description of parameter"  # Optional description
)
```

### Customizing Categories

To add new parameter categories or modify existing ones, edit the `PARAMETER_CATEGORIES` dictionary in `config_parameters.py`:

```python
PARAMETER_CATEGORIES = {
    "New Category": [
        "parameter 1", "parameter 2", "parameter 3"
    ],
    # ... existing categories
}
```

### Adding New Extraction Patterns

To add new regex patterns for text extraction, add them to `TEXT_PARAMETER_PATTERNS`:

```python
TEXT_PARAMETER_PATTERNS = [
    (r'New Pattern\s+(.*)', 'Parameter Name'),
    # ... existing patterns
]
```

## Benefits

1. **Maintainability** - All configuration is centralized in one file
2. **Extensibility** - Easy to add new parameters and patterns
3. **Automatic Learning** - System learns and adapts to new parameters
4. **Persistence** - New parameters are saved and reused
5. **Type Safety** - Configuration is validated and typed
6. **Backwards Compatibility** - Existing functionality is preserved

## Configuration Management

### Viewing Current Configuration
```python
from config_parameters import param_manager

# View all dynamic parameters
print(param_manager.dynamic_params)

# Get all patterns (static + dynamic)
patterns = param_manager.get_all_patterns()
```

### Resetting Configuration
To reset dynamic parameters, simply delete `dynamic_parameters.json` and restart the application.

## Troubleshooting

1. **Missing Parameters** - Check `dynamic_parameters.json` to see if parameters were automatically added
2. **Wrong Categorization** - Modify `PARAMETER_CATEGORIES` in `config_parameters.py`
3. **Pattern Issues** - Add or modify patterns in `TEXT_PARAMETER_PATTERNS`
4. **Configuration Errors** - Run `test_config.py` to verify configuration integrity

## Future Enhancements

The configuration system is designed to be extensible. Future enhancements could include:

- Web interface for configuration management
- Machine learning-based parameter categorization
- Export/import of configuration templates
- Version control for configuration changes
- Advanced pattern validation and testing
