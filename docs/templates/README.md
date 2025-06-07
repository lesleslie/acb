# Documentation Templates

This directory contains template files for creating new documentation in the ACB project.

## Available Templates

- **ADAPTER-TEMPLATE.md**: Template for creating new adapter documentation

## Usage

When creating documentation for a new adapter:

1. Copy the template: `cp ADAPTER-TEMPLATE.md ../adapters/your_adapter/README.md`
2. Replace all placeholder text:
   - `ADAPTER_NAME` → Your adapter name (e.g., "Cache", "Storage")
   - `DESCRIPTION` → Brief description of the adapter
   - `IMPLEMENTATIONS` → List of available implementations
   - `adapter_name` → Configuration key name
   - Fill in all sections with actual content

## Guidelines

- Follow the existing structure and formatting
- Include comprehensive examples
- Add troubleshooting information
- Update navigation links appropriately
- Use consistent terminology across all documentation
