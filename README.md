# DMX Color Visualization Tool (v2.0-dev)

A powerful utility for lighting designers and programmers to visualize, explore, and filter DMX color combinations for RGBWA fixtures. This is the development version with planned enhancements.

![DMX Color Visualization Tool](https://github.com/username/dmx-colors/raw/main/screenshot.png)

## Overview

This tool generates all possible color combinations for RGBWA (Red, Green, Blue, White, Amber) DMX fixtures using standard DMX steps (0, 85, 170, 255), calculates their visual appearance, and provides an interactive interface to explore them. It's designed to help lighting designers and programmers find the perfect color combinations for their shows.

## Current Features

- **Comprehensive Color Generation**: Creates 1000+ unique color combinations using standard DMX values
- **Intelligent Color Mixing**: Simulates how White and Amber channels affect the final color output
- **Multiple Visualization Methods**:
  - Grid view with detailed color information
  - Color wheel visualization showing color relationships
- **Advanced Filtering System**:
  - Filter by individual DMX channel values (R, G, B, W, A)
  - Filter by perceived brightness
  - Filter by color group (red, blue, pastel, etc.)
  - Filter by color category (warm, cool, neutral)
  - Text search for specific combinations
  - Favorites system to mark and filter preferred colors
- **Dark Mode**: Toggle between light and dark interface themes
- **Data Export**: Generates CSV files with complete color data
  - Standard order CSV
  - Brightness-sorted CSV
- **Swatch Generation**: Creates visual swatch images for all colors

## Planned Enhancements for v2.0

This development version will include the following planned improvements:

### 1. Enhanced Favorites System
- Dedicated favorites view with improved layout
- Export options specifically for favorite colors
- Grouping and organization of favorites
- Notes and tags for favorite colors

### 2. Advanced Export Options
- Multiple export formats (CSV, JSON, XML)
- Custom export templates
- Selective export of filtered results
- Direct export to lighting console formats

### 3. Fixture Profiles
- Support for different fixture types and manufacturers
- Custom color mixing algorithms per fixture
- Fixture-specific DMX mapping
- Multi-fixture comparison

### 4. Interactive Color Wheel
- Click on color wheel dots to highlight corresponding swatches
- Drag and drop color selection
- Visual color relationships and harmonies
- Color temperature visualization

### 5. Performance Optimizations
- Pagination for large color sets
- Lazy loading of swatches
- Caching for frequently accessed swatches
- Reduced memory footprint

### 6. User Interface Improvements
- Responsive design for mobile devices
- Customizable layout
- Keyboard shortcuts
- Improved accessibility

## Getting Started

### Prerequisites

- Python 3.6 or higher
- PIL (Python Imaging Library) / Pillow

### Installation

1. Clone or download this repository
2. Install required dependencies:
   ```
   pip install pillow
   ```

### Usage

1. Run the script:
   ```
   python generate_dmx_table.py
   ```

2. The script will:
   - Generate all color combinations
   - Create CSV files with color data
   - Generate swatch images
   - Create an HTML preview page

3. Open `dmx_preview.html` in your web browser to explore the colors

## How It Works

### DMX Value Calculation

The tool uses four standard DMX steps (0, 85, 170, 255) for each channel, representing:
- 0: Off
- 85: Dim
- 170: Mid
- 255: Full

### Color Mixing Logic

- **RGB Channels**: Standard RGB color mixing
- **White Channel**: Adds equal parts (R,G,B) at 50% intensity to prevent oversaturation
- **Amber Channel**: Adds a warm tone (R:1.0, G:0.75, B:0.0) at 50% intensity

### Color Classification

Colors are automatically classified by:
- **Main Color Group**: Identifies the dominant hue (red, green, blue, etc.)
- **Color Category**: Categorizes as warm, cool, or neutral
- **Brightness Level**: Quantizes perceived brightness to DMX steps

## Development Guidelines

If you're contributing to this development version, please follow these guidelines:

1. **Feature Branches**: Create a new branch for each feature or enhancement
2. **Testing**: Test all changes thoroughly before merging
3. **Documentation**: Update this README and add inline comments for new features
4. **Compatibility**: Ensure backward compatibility with v1.0 data formats
5. **Performance**: Consider the impact of changes on performance, especially for large color sets

## File Structure

- `generate_dmx_table.py`: Main Python script
- `dmx_colors.csv`: All color combinations in index order
- `dmx_colors_by_brightness.csv`: Color combinations sorted by brightness
- `swatches/`: Directory containing swatch images for all colors
- `dmx_preview.html`: Interactive HTML interface for exploring colors

## Customization

You can customize the tool by modifying:
- `DMX_STEPS`: Change the DMX values used for generation
- `w_scale` and `a_scale`: Adjust how White and Amber channels affect the final color
- HTML/CSS in the script: Modify the appearance of the preview page

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the needs of lighting designers working with RGBWA fixtures
- Thanks to the lighting design community for feedback and suggestions 