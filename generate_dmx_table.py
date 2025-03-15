import csv
import os
from PIL import Image
import time
import math

# -------------------------------------------
# 1) Define the DMX steps and naming scheme
# -------------------------------------------
DMX_STEPS = [0, 85, 170, 255]

intensity_names = {
    0   : "Off",
    85  : "Dim",
    170 : "Mid",
    255 : "Full"
}

# -------------------------------------------
# 2) Approximate how W and A affect the color
# -------------------------------------------
# We'll treat:
#   White = adds equal parts (1,1,1) but scaled to prevent oversaturation
#   Amber ~ adds an (1.0, 0.75, 0.0) style to the final color
#
# The scaling factor is naive. Feel free to tweak if your fixture
# has a different amber or white mix ratio.

def to_srgb(r, g, b, w, a):
    for val in (r, g, b, w, a):
        if not 0 <= val <= 255:
            raise ValueError(f"DMX value {val} outside valid range 0-255")
    
    # Scale factors to prevent oversaturation
    # These values make the channels more balanced and prevent too many white results
    w_scale = 0.5  # White contributes at 50% to prevent oversaturation
    a_scale = 0.5  # Amber contributes at 50% to prevent oversaturation
    
    # Basic channel contributions:
    #   R channel → (r, 0, 0)
    #   G channel → (0, g, 0)
    #   B channel → (0, 0, b)
    #   W channel → (w, w, w) * w_scale
    #   A channel → (1.0, 0.75, 0.0) * a_scale * (a / 255)
    
    # Calculate the RGB values with scaled white and amber
    rr = r + (w * w_scale) + (a * a_scale)
    gg = g + (w * w_scale) + (a * 0.75 * a_scale)
    bb = b + (w * w_scale)
    
    # The above might add up beyond 255, so we clamp:
    rr = min(rr, 255)
    gg = min(gg, 255)
    bb = min(bb, 255)

    return (int(rr), int(gg), int(bb))

def perceived_brightness(r, g, b):
    """
    Calculate perceived brightness using the formula:
    (0.299*R + 0.587*G + 0.114*B)
    Returns a value quantized to one of the DMX_STEPS values
    """
    # Calculate raw brightness (0-255)
    raw_brightness = 0.299 * r + 0.587 * g + 0.114 * b
    
    # Quantize to one of the DMX_STEPS values
    if raw_brightness < 42:  # Midpoint between 0 and 85
        return 0
    elif raw_brightness < 127:  # Midpoint between 85 and 170
        return 85
    elif raw_brightness < 212:  # Midpoint between 170 and 255
        return 170
    else:
        return 255

def get_color_group(r, g, b):
    """
    Determine the color group based on RGB values.
    Returns a tuple of (main_color, color_category)
    """
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    
    # For black/gray/white determination
    if max_val == 0:
        return "black", "neutral"
    
    if max_val - min_val < 30:  # Small difference between channels indicates grayscale
        if max_val < 85:
            return "dark gray", "neutral"
        elif max_val < 170:
            return "gray", "neutral"
        else:
            return "white", "neutral"
    
    # Determine main color based on dominant channel
    if r > g and r > b:
        if g > b * 1.5:  # More green than blue
            main_color = "orange" if g > r * 0.7 else "red-orange"
            category = "warm"
        else:
            if b > r * 0.7:  # Significant blue
                main_color = "magenta"
                category = "cool"
            else:
                main_color = "red"
                category = "warm"
    elif g > r and g > b:
        if r > b * 1.5:  # More red than blue
            main_color = "yellow-green"
            category = "warm"
        else:
            if b > g * 0.7:  # Significant blue
                main_color = "teal"
                category = "cool"
            else:
                main_color = "green"
                category = "cool"
    elif b > r and b > g:
        if r > g * 1.5:  # More red than green
            main_color = "purple"
            category = "cool"
        else:
            if g > b * 0.7:  # Significant green
                main_color = "cyan"
                category = "cool"
            else:
                main_color = "blue"
                category = "cool"
    elif r == g and r > b:
        main_color = "yellow"
        category = "warm"
    elif r == b and r > g:
        main_color = "magenta"
        category = "cool"
    elif g == b and g > r:
        main_color = "cyan"
        category = "cool"
    else:
        main_color = "mixed"
        category = "neutral"
    
    # Determine if it's a pastel
    if min_val > 170:
        main_color = f"pastel {main_color}"
        
    # Determine if it's a deep/dark color
    if max_val < 170 and main_color != "black":
        main_color = f"deep {main_color}"
    
    return main_color, category

def get_color_wheel_position(r, g, b):
    """
    Calculate the position on a color wheel for a given RGB color.
    Returns (x, y) coordinates where (0,0) is the center of the wheel.
    """
    # Convert RGB to HSV
    r, g, b = r/255.0, g/255.0, b/255.0
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    
    if max_val == 0:
        return 0, 0  # Black is at the center
    
    delta = max_val - min_val
    
    # Calculate hue (0-360)
    if delta == 0:
        hue = 0  # Gray
    elif max_val == r:
        hue = 60 * (((g - b) / delta) % 6)
    elif max_val == g:
        hue = 60 * (((b - r) / delta) + 2)
    else:  # max_val == b
        hue = 60 * (((r - g) / delta) + 4)
    
    # Calculate saturation (0-1)
    if max_val == 0:
        saturation = 0
    else:
        saturation = delta / max_val
    
    # Convert hue and saturation to x,y coordinates
    # Hue is the angle, saturation is the distance from center
    angle_rad = math.radians(hue)
    x = saturation * math.cos(angle_rad)
    y = saturation * math.sin(angle_rad)
    
    return x, y

def calculate_color_temperature(r, g, b):
    """
    Approximate the color temperature in Kelvin for an RGB color.
    This is a simplified approximation based on RGB ratios.
    Returns a temperature range category.
    """
    # Normalize RGB values to 0-1
    r, g, b = r/255.0, g/255.0, b/255.0
    
    # Skip black or very dark colors
    if max(r, g, b) < 0.1:
        return "neutral"
    
    # Calculate ratios that correlate with temperature
    # Higher r/b ratio indicates warmer color
    # Higher b/r ratio indicates cooler color
    if r > 0 and b > 0:
        rb_ratio = r/b
        br_ratio = b/r
    else:
        # Handle division by zero
        rb_ratio = 10 if r > 0 else 0
        br_ratio = 10 if b > 0 else 0
    
    # Green affects perception but in a more complex way
    # High green with high red = warm yellow
    # High green with high blue = cool cyan
    
    # Determine temperature category
    if rb_ratio > 3:
        return "very-warm"  # Very warm (amber, orange, warm red)
    elif rb_ratio > 1.5:
        return "warm"       # Warm (yellow, light orange)
    elif br_ratio > 3:
        return "very-cool"  # Very cool (deep blue, cyan)
    elif br_ratio > 1.5:
        return "cool"       # Cool (blue, teal)
    elif g > max(r, b) * 1.5:
        return "cool"       # Green-dominant colors appear cooler
    elif abs(r - b) < 0.1 and r > 0.7 and g > 0.7:
        return "neutral"    # Close to white
    elif abs(r - b) < 0.2:
        return "neutral"    # Balanced r and b = neutral
    else:
        # Slight dominance
        return "warm" if r > b else "cool"

# -------------------------------------------
# 3) Generate all combinations (4^5 = 1024 total)
# -------------------------------------------
total_combinations = len(DMX_STEPS) ** 5  # = 1024
print(f"Generating {total_combinations} color combinations...")
start_time = time.time()

combos = []
index = 1

for r in DMX_STEPS:
    for g in DMX_STEPS:
        for b in DMX_STEPS:
            for w in DMX_STEPS:
                for a in DMX_STEPS:
                    # Skip if R, G, and B are all 255 (creates white regardless of W and A)
                    if r == 255 and g == 255 and b == 255:
                        continue
                        
                    # Build a descriptive "name" for the color
                    # e.g. "R=85 (Dim) + G=0 (Off) + B=170 (Mid) + W=0 (Off) + A=255 (Full)"
                    name_parts = [
                        f"R={r} ({intensity_names[r]})",
                        f"G={g} ({intensity_names[g]})",
                        f"B={b} ({intensity_names[b]})",
                        f"W={w} ({intensity_names[w]})",
                        f"A={a} ({intensity_names[a]})"
                    ]
                    color_name = " + ".join(name_parts)
                    
                    # Calculate the perceived brightness to check if it's not 0
                    sr, sg, sb = to_srgb(r, g, b, w, a)
                    brightness = perceived_brightness(sr, sg, sb)
                    
                    # Skip colors with brightness 0 (essentially black/off)
                    if brightness == 0:
                        continue
                    
                    # Get color group and category
                    main_color, category = get_color_group(sr, sg, sb)
                    
                    # Calculate color temperature
                    temperature = calculate_color_temperature(sr, sg, sb)
                    
                    combos.append((
                        index,
                        color_name,
                        r, g, b, w, a,
                        main_color,
                        category,
                        temperature
                    ))
                    index += 1

print(f"Generated {len(combos)} combinations in {time.time() - start_time:.2f} seconds")

# Sort by perceived brightness
print("Sorting combinations by brightness...")
sorted_by_brightness = sorted(
    combos,
    key=lambda x: perceived_brightness(*to_srgb(x[2], x[3], x[4], x[5], 0))  # Ignore amber for brightness calculation
)

# -------------------------------------------
# 4) Write out CSV files
# -------------------------------------------
print("Writing CSV files...")

try:
    with open("dmx_colors.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "Name", "R DMX", "G DMX", "B DMX", "W DMX", "A DMX", "sR", "sG", "sB", "Brightness", "Brightness Name", "Color Group", "Category", "Temperature"])
        for row in combos:
            idx, name, r, g, b, w, a, main_color, category, temperature = row
            sr, sg, sb = to_srgb(r, g, b, w, a)
            brightness = perceived_brightness(sr, sg, sb)
            brightness_name = intensity_names[brightness]
            writer.writerow([idx, name, r, g, b, w, a, sr, sg, sb, brightness, brightness_name, main_color, category, temperature])
    print(f"Successfully wrote {len(combos)} combinations to dmx_colors.csv")
except IOError as e:
    print(f"Error writing CSV file: {e}")

# Create additional CSV with sorted results
try:
    with open("dmx_colors_by_brightness.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "Name", "R DMX", "G DMX", "B DMX", "W DMX", "A DMX", "sR", "sG", "sB", "Brightness", "Brightness Name", "Color Group", "Category", "Temperature"])
        for row in sorted_by_brightness:
            idx, name, r, g, b, w, a, main_color, category, temperature = row
            sr, sg, sb = to_srgb(r, g, b, w, a)
            brightness = perceived_brightness(sr, sg, sb)
            brightness_name = intensity_names[brightness]
            writer.writerow([idx, name, r, g, b, w, a, sr, sg, sb, brightness, brightness_name, main_color, category, temperature])
    print(f"Successfully wrote {len(combos)} combinations to dmx_colors_by_brightness.csv")
except IOError as e:
    print(f"Error writing sorted CSV: {e}")

# -------------------------------------------
# 5) Generate small PNG swatches
# -------------------------------------------
print("Generating swatch images...")
try:
    os.makedirs("swatches", exist_ok=True)
    
    # Track progress
    total = len(combos)
    last_percent = -1
    
    for i, (idx, name, r, g, b, w, a, main_color, category, temperature) in enumerate(combos):
        # Show progress every 10%
        percent_done = int((i / total) * 100)
        if percent_done % 10 == 0 and percent_done != last_percent:
            print(f"{percent_done}% complete ({i}/{total} swatches)")
            last_percent = percent_done
            
        # Convert the DMX values to approximate sRGB
        sr, sg, sb = to_srgb(r, g, b, w, a)
        
        # Create a 20×20 image of that color
        img = Image.new("RGB", (20, 20), (sr, sg, sb))
        
        # Filename example: "swatches/0001_R=0(Off)+G=0(Off)+....png"
        filename = f"{idx:04d}_" + name.replace(" + ", "_").replace(" ", "") + ".png"
        
        img.save(os.path.join("swatches", filename))
    
    print("100% complete - All swatch images generated")
except Exception as e:
    print(f"Error generating swatches: {e}")

# -------------------------------------------
# 6) Generate HTML preview page
# -------------------------------------------
print("Creating HTML preview page...")

try:
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>DMX Color Swatches</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
        }
        .swatch { 
            display: inline-block;
            margin: 5px;
            text-align: center;
            vertical-align: top;
            width: 150px;
            position: relative;
        }
        .swatch img {
            border: 1px solid #ccc;
            width: 40px;
            height: 40px;
        }
        .swatch p {
            font-size: 12px;
            margin: 2px 0;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        h1 {
            margin-bottom: 20px;
        }
        .controls {
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 10px;
        }
        .filter-group {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .filter-label {
            font-weight: bold;
            margin-right: 2px;
        }
        .section {
            margin-bottom: 30px;
        }
        .dmx-values {
            font-weight: bold;
            color: #333;
        }
        .color-info {
            font-style: italic;
            color: #666;
        }
        select {
            padding: 4px;
            border-radius: 4px;
        }
        input[type="text"] {
            padding: 5px;
            width: 200px;
            border-radius: 4px;
            border: 1px solid #ccc;
        }
        button {
            padding: 5px 10px;
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background-color: #e0e0e0;
        }
        .color-wheel-container {
            margin: 20px 0;
            text-align: center;
        }
        .color-wheel {
            position: relative;
            width: 400px;
            height: 400px;
            margin: 0 auto;
            border: 1px solid #ccc;
            border-radius: 50%;
            background: radial-gradient(circle, white 0%, rgba(255,255,255,0) 70%), 
                        conic-gradient(
                            red 0deg, 
                            yellow 60deg, 
                            lime 120deg, 
                            cyan 180deg, 
                            blue 240deg, 
                            magenta 300deg, 
                            red 360deg
                        );
        }
        .color-dot {
            position: absolute;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            cursor: pointer;
            border: 1px solid rgba(0,0,0,0.3);
        }
        .color-dot:hover {
            z-index: 100;
            width: 14px;
            height: 14px;
            box-shadow: 0 0 5px rgba(0,0,0,0.5);
        }
        .color-wheel-controls {
            margin: 10px 0;
        }
        .view-toggle {
            display: flex;
            justify-content: center;
            margin: 10px 0;
        }
        .view-toggle button {
            margin: 0 5px;
        }
        .active-view {
            background-color: #ddd;
            font-weight: bold;
        }
        .favorite-btn {
            position: absolute;
            top: 5px;
            right: 5px;
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            color: #ccc;
            padding: 0;
            margin: 0;
            width: 24px;
            height: 24px;
            line-height: 24px;
            text-align: center;
        }
        .favorite-btn:hover {
            color: #ffcc00;
        }
        .favorite-btn.active {
            color: #ffcc00;
        }
        .dark-mode {
            background-color: #222;
            color: #eee;
        }
        .dark-mode .swatch {
            background-color: #333;
        }
        .dark-mode .controls {
            background-color: #333;
            border-color: #444;
        }
        .dark-mode button {
            background-color: #444;
            color: #eee;
            border-color: #555;
        }
        .dark-mode button:hover {
            background-color: #555;
        }
        .dark-mode select,
        .dark-mode input[type="text"] {
            background-color: #444;
            color: #eee;
            border-color: #555;
        }
        .theme-toggle {
            position: absolute;
            top: 20px;
            right: 20px;
        }
    </style>
    <script>
        // Simple array to store favorites
        let favorites = [];
        
        // Load favorites from localStorage on page load
        function loadFavorites() {
            const stored = localStorage.getItem('dmxFavorites');
            if (stored) {
                favorites = JSON.parse(stored);
                updateFavoriteButtons();
            }
        }
        
        // Save favorites to localStorage
        function saveFavorites() {
            localStorage.setItem('dmxFavorites', JSON.stringify(favorites));
        }
        
        // Toggle a swatch as favorite
        function toggleFavorite(index) {
            const idx = favorites.indexOf(index);
            if (idx === -1) {
                favorites.push(index);
            } else {
                favorites.splice(idx, 1);
            }
            saveFavorites();
            updateFavoriteButtons();
            applyFilters(); // Re-apply filters to update display
        }
        
        // Update the appearance of favorite buttons
        function updateFavoriteButtons() {
            document.querySelectorAll('.favorite-btn').forEach(btn => {
                const index = btn.getAttribute('data-index');
                if (favorites.includes(index)) {
                    btn.innerHTML = '★';
                    btn.classList.add('active');
                } else {
                    btn.innerHTML = '☆';
                    btn.classList.remove('active');
                }
            });
        }
        
        // Apply all filters
        function applyFilters() {
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const rValue = document.getElementById('filter-r').value;
            const gValue = document.getElementById('filter-g').value;
            const bValue = document.getElementById('filter-b').value;
            const wValue = document.getElementById('filter-w').value;
            const aValue = document.getElementById('filter-a').value;
            const iValue = document.getElementById('filter-i').value;
            const colorValue = document.getElementById('filter-color').value;
            const categoryValue = document.getElementById('filter-category').value;
            const favoritesOnly = document.getElementById('filter-favorites').checked;
            
            let visibleCount = 0;
            const swatches = document.querySelectorAll('.swatch');
            
            swatches.forEach(swatch => {
                // Get all data attributes
                const name = swatch.getAttribute('data-name').toLowerCase();
                const r = swatch.getAttribute('data-r');
                const g = swatch.getAttribute('data-g');
                const b = swatch.getAttribute('data-b');
                const w = swatch.getAttribute('data-w');
                const a = swatch.getAttribute('data-a');
                const brightness = swatch.getAttribute('data-brightness');
                const colorGroup = swatch.getAttribute('data-color-group');
                const category = swatch.getAttribute('data-category');
                const index = swatch.getAttribute('data-index');
                
                // Check if it matches all filters
                let visible = true;
                
                // Text search
                if (searchTerm && !name.includes(searchTerm)) {
                    visible = false;
                }
                
                // Channel filters
                if (rValue !== 'any' && r !== rValue) visible = false;
                if (gValue !== 'any' && g !== gValue) visible = false;
                if (bValue !== 'any' && b !== bValue) visible = false;
                if (wValue !== 'any' && w !== wValue) visible = false;
                if (aValue !== 'any' && a !== aValue) visible = false;
                if (iValue !== 'any' && brightness !== iValue) visible = false;
                
                // Color group filter
                if (colorValue !== 'any' && !colorGroup.includes(colorValue)) visible = false;
                
                // Category filter
                if (categoryValue !== 'any' && category !== categoryValue) visible = false;
                
                // Favorites filter
                if (favoritesOnly && !favorites.includes(index)) visible = false;
                
                // Apply visibility
                if (visible) {
                    swatch.style.display = 'inline-block';
                    visibleCount++;
                    
                    // Also show the corresponding dot on the color wheel
                    const dot = document.getElementById('dot-' + index);
                    if (dot) dot.style.display = 'block';
                } else {
                    swatch.style.display = 'none';
                    
                    // Also hide the corresponding dot on the color wheel
                    const dot = document.getElementById('dot-' + index);
                    if (dot) dot.style.display = 'none';
                }
            });
            
            // Update status
            document.getElementById('filter-status').textContent = `Showing ${visibleCount} of ${swatches.length} swatches`;
        }
        
        // Reset all filters
        function resetFilters() {
            document.getElementById('search').value = '';
            document.getElementById('filter-r').value = 'any';
            document.getElementById('filter-g').value = 'any';
            document.getElementById('filter-b').value = 'any';
            document.getElementById('filter-w').value = 'any';
            document.getElementById('filter-a').value = 'any';
            document.getElementById('filter-i').value = 'any';
            document.getElementById('filter-color').value = 'any';
            document.getElementById('filter-category').value = 'any';
            document.getElementById('filter-favorites').checked = false;
            applyFilters();
        }
        
        // Toggle dark mode
        function toggleDarkMode() {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('dmxDarkMode', isDark ? 'true' : 'false');
            document.getElementById('dark-mode-toggle').textContent = isDark ? 'Light Mode' : 'Dark Mode';
        }
        
        // Switch between views
        function switchView(viewName) {
            // Hide all views
            document.getElementById('grid-view').style.display = 'none';
            document.getElementById('wheel-view').style.display = 'none';
            
            // Show selected view
            document.getElementById(viewName).style.display = 'block';
            
            // Update active button
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.classList.remove('active-view');
            });
            document.getElementById(viewName + '-btn').classList.add('active-view');
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            // Load favorites
            loadFavorites();
            
            // Set up event listeners for filter changes
            document.getElementById('search').addEventListener('input', applyFilters);
            document.getElementById('filter-r').addEventListener('change', applyFilters);
            document.getElementById('filter-g').addEventListener('change', applyFilters);
            document.getElementById('filter-b').addEventListener('change', applyFilters);
            document.getElementById('filter-w').addEventListener('change', applyFilters);
            document.getElementById('filter-a').addEventListener('change', applyFilters);
            document.getElementById('filter-i').addEventListener('change', applyFilters);
            document.getElementById('filter-color').addEventListener('change', applyFilters);
            document.getElementById('filter-category').addEventListener('change', applyFilters);
            document.getElementById('filter-favorites').addEventListener('change', applyFilters);
            
            // Check for dark mode preference
            if (localStorage.getItem('dmxDarkMode') === 'true') {
                document.body.classList.add('dark-mode');
                document.getElementById('dark-mode-toggle').textContent = 'Light Mode';
            }
            
            // Initial filter application
            applyFilters();
            
            // Set initial view
            switchView('grid-view');
        });
    </script>
</head>
<body>
    <h1>DMX Color Swatches</h1>
    
    <button id="dark-mode-toggle" class="theme-toggle" onclick="toggleDarkMode()">Dark Mode</button>
    
    <div class="controls">
        <div class="filter-group">
            <input type="text" id="search" placeholder="Filter by name...">
        </div>
        
        <div class="filter-group">
            <span class="filter-label">R:</span>
            <select id="filter-r">
                <option value="any">Any</option>
                <option value="0">0 (Off)</option>
                <option value="85">85 (Dim)</option>
                <option value="170">170 (Mid)</option>
                <option value="255">255 (Full)</option>
            </select>
        </div>
        
        <div class="filter-group">
            <span class="filter-label">G:</span>
            <select id="filter-g">
                <option value="any">Any</option>
                <option value="0">0 (Off)</option>
                <option value="85">85 (Dim)</option>
                <option value="170">170 (Mid)</option>
                <option value="255">255 (Full)</option>
            </select>
        </div>
        
        <div class="filter-group">
            <span class="filter-label">B:</span>
            <select id="filter-b">
                <option value="any">Any</option>
                <option value="0">0 (Off)</option>
                <option value="85">85 (Dim)</option>
                <option value="170">170 (Mid)</option>
                <option value="255">255 (Full)</option>
            </select>
        </div>
        
        <div class="filter-group">
            <span class="filter-label">W:</span>
            <select id="filter-w">
                <option value="any">Any</option>
                <option value="0">0 (Off)</option>
                <option value="85">85 (Dim)</option>
                <option value="170">170 (Mid)</option>
                <option value="255">255 (Full)</option>
            </select>
        </div>
        
        <div class="filter-group">
            <span class="filter-label">A:</span>
            <select id="filter-a">
                <option value="any">Any</option>
                <option value="0">0 (Off)</option>
                <option value="85">85 (Dim)</option>
                <option value="170">170 (Mid)</option>
                <option value="255">255 (Full)</option>
            </select>
        </div>
        
        <div class="filter-group">
            <span class="filter-label">I:</span>
            <select id="filter-i">
                <option value="any">Any</option>
                <option value="85">85 (Dim)</option>
                <option value="170">170 (Mid)</option>
                <option value="255">255 (Full)</option>
            </select>
        </div>
        
        <div class="filter-group">
            <span class="filter-label">Color:</span>
            <select id="filter-color">
                <option value="any">Any</option>
                <option value="red">Red</option>
                <option value="orange">Orange</option>
                <option value="yellow">Yellow</option>
                <option value="green">Green</option>
                <option value="cyan">Cyan</option>
                <option value="blue">Blue</option>
                <option value="purple">Purple</option>
                <option value="magenta">Magenta</option>
                <option value="pastel">Pastel</option>
                <option value="deep">Deep</option>
                <option value="gray">Gray</option>
                <option value="white">White</option>
            </select>
        </div>
        
        <div class="filter-group">
            <span class="filter-label">Category:</span>
            <select id="filter-category">
                <option value="any">Any</option>
                <option value="warm">Warm</option>
                <option value="cool">Cool</option>
                <option value="neutral">Neutral</option>
            </select>
        </div>
        
        <div class="filter-group">
            <label>
                <input type="checkbox" id="filter-favorites">
                Favorites Only
            </label>
        </div>
        
        <button onclick="resetFilters()">Reset Filters</button>
        <div id="filter-status" style="margin-left: 10px; font-style: italic;"></div>
    </div>
    
    <div class="view-toggle">
        <button id="grid-view-btn" class="view-btn active-view" onclick="switchView('grid-view')">Grid View</button>
        <button id="wheel-view-btn" class="view-btn" onclick="switchView('wheel-view')">Color Wheel View</button>
    </div>
    
    <div id="wheel-view" class="section" style="display: none;">
        <h2>Color Wheel Visualization</h2>
        <div class="color-wheel-container">
            <div class="color-wheel">
"""

    # Add dots to the color wheel
    for idx, name, r, g, b, w, a, main_color, category, temperature in combos:
        sr, sg, sb = to_srgb(r, g, b, w, a)
        x, y = get_color_wheel_position(sr, sg, sb)
        
        # Convert x,y (-1 to 1) to pixel coordinates (0 to 400)
        px = 200 + (x * 180)  # 200 is center, 180 is radius
        py = 200 - (y * 180)  # Negative y because CSS y-axis is inverted
        
        # Add a dot for this color
        html_content += f"""
                <div id="dot-{idx}" class="color-dot" style="left: {px}px; top: {py}px; background-color: rgb({sr},{sg},{sb});" 
                     title="#{idx:04d} - {main_color.title()} - R:{r} G:{g} B:{b} W:{w} A:{a}"
                     onclick="showSwatchDetails('{idx}')"></div>"""
    
    html_content += """
            </div>
            <div class="color-wheel-controls">
                <p>Click on any dot to view its details in the grid view.</p>
            </div>
        </div>
    </div>
    
    <div id="grid-view" class="section">
"""

    # Add regular order swatches
    html_content += "<h2>Swatches by Index</h2>"
    for idx, name, r, g, b, w, a, main_color, category, temperature in combos:
        sr, sg, sb = to_srgb(r, g, b, w, a)
        brightness = perceived_brightness(sr, sg, sb)
        brightness_name = intensity_names[brightness]
        swatch_filename = f"{idx:04d}_" + name.replace(" + ", "_").replace(" ", "") + ".png"
        
        html_content += f"""
        <div class="swatch" data-name="{name}" data-r="{r}" data-g="{g}" data-b="{b}" data-w="{w}" data-a="{a}" data-brightness="{brightness}" data-color-group="{main_color}" data-category="{category}" data-index="{idx}">
            <button class="favorite-btn" data-index="{idx}" onclick="toggleFavorite('{idx}')">☆</button>
            <img src="swatches/{swatch_filename}" width="40" height="40">
            <p><strong>#{idx:04d}</strong></p>
            <p class="dmx-values">R:{r} G:{g} B:{b} W:{w} A:{a} I:{brightness}</p>
            <p>{name}</p>
            <p>RGB: ({sr},{sg},{sb})</p>
            <p>Brightness: {brightness} ({brightness_name})</p>
            <p class="color-info">{main_color.title()} - {category.title()}</p>
        </div>
        """
    
    # Add brightness-sorted swatches
    html_content += """
    </div>
    
    <div class="section">
        <h2>Swatches by Brightness</h2>
    """
    
    for idx, name, r, g, b, w, a, main_color, category, temperature in sorted_by_brightness:
        sr, sg, sb = to_srgb(r, g, b, w, a)
        brightness = perceived_brightness(sr, sg, sb)
        brightness_name = intensity_names[brightness]
        swatch_filename = f"{idx:04d}_" + name.replace(" + ", "_").replace(" ", "") + ".png"
        
        html_content += f"""
        <div class="swatch" data-name="{name}" data-r="{r}" data-g="{g}" data-b="{b}" data-w="{w}" data-a="{a}" data-brightness="{brightness}" data-color-group="{main_color}" data-category="{category}" data-index="{idx}">
            <button class="favorite-btn" data-index="{idx}" onclick="toggleFavorite('{idx}')">☆</button>
            <img src="swatches/{swatch_filename}" width="40" height="40">
            <p><strong>#{idx:04d}</strong></p>
            <p class="dmx-values">R:{r} G:{g} B:{b} W:{w} A:{a} I:{brightness}</p>
            <p>{name}</p>
            <p>RGB: ({sr},{sg},{sb})</p>
            <p>Brightness: {brightness} ({brightness_name})</p>
            <p class="color-info">{main_color.title()} - {category.title()}</p>
        </div>
        """
    
    html_content += """
    </div>
    
    <script>
        // Initialize the view
        document.addEventListener('DOMContentLoaded', function() {
            switchView('grid-view');
        });
    </script>
</body>
</html>
"""

    with open("dmx_preview.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Created dmx_preview.html")
except IOError as e:
    print(f"Error writing HTML preview: {e}")

print(f"All operations completed in {time.time() - start_time:.2f} seconds")