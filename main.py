import time
# ==========================================
# MOCK ARDUINO APPLAB SDK (Add this to test locally)
# ==========================================
import sys
from types import ModuleType

if 'applab' not in sys.modules:
    # Create a fake applab module in memory so Python doesn't crash
    mock_applab = ModuleType('applab')
    
    # Mock the Bridge class for .ino communication
    class MockBridge:
        def read_string(self): return "Dry"  # Simulates receiving "Dry" from your .ino sketch
        def send_command(self, cmd, val): print(f"[MOCK HARDWARE] Sending to MCU -> {cmd}: {val}")
    
    # Mock the LED control class
    class MockLeds:
        @staticmethod
        def set_led1_color(r, g, b): print(f"[MOCK LED] Status changed to RGB({r},{g},{b})")
        
    # Mock the AI Model framework
    class MockAI:
        def on_detect(self, callback):
            # Simulates the camera seeing a stressed leaf 3 seconds into running
            print("[MOCK AI] Model loaded. Simulating live camera stream predictions...")
            class Prediction:
                label = "stressed_leaf"
                value = 0.85
            time.sleep(3)
            callback([Prediction()])

    # Bind the mocks to the fake module
    mock_applab.Bridge = MockBridge
    mock_applab.Leds = MockLeds
    mock_applab.ImageClassification = MockAI
    mock_applab.VideoObjectDetection = MockAI
    
    # Inject it into Python's global system modules
    sys.modules['applab'] = mock_applab
# ==========================================

import time
import applab
from applab import Bridge
from applab import Leds

# ... REST OF YOUR CODE CONTINUES EXACTLY THE SAME BELOW ...
import applab
from applab import Bridge
from applab import Leds

# ==========================================
# 0. DYNAMIC CLASS RESOLUTION (Error Fix)
# ==========================================
# This safely checks your App Lab library and loads the correct AI module name
if hasattr(applab, 'ImageClassification'):
    from applab import ImageClassification as AIModelClass
elif hasattr(applab, 'VideoObjectDetection'):
    from applab import VideoObjectDetection as AIModelClass
elif hasattr(applab, 'ObjectDetection'):
    from applab import ObjectDetection as AIModelClass
else:
    from applab import AIModel as AIModelClass

# ==========================================
# 1. INITIALIZATION
# ==========================================
# Initialize the AI Model Brick using the verified class name
crop_camera_model = AIModelClass()

# Initialize the RPC Bridge to talk to the STM32 MCU (.ino side)
arduino_hardware = Bridge()

# Variables to track system logic variables across your dual models
current_soil_status = "Unknown"
plant_stress_factor = 1.0       # Default multiplier
water_requirement_pct = 50.0    # Base volume requirement %

# ==========================================
# 2. COMBINED LOGIC CORE FUNCTION
# ==========================================
def evaluate_combined_decision():
    """
    Implements the Combined Decision Logic:
    Evaluates soil classification alongside camera stress factor modifiers.
    """
    global current_soil_status, water_requirement_pct, plant_stress_factor
    
    print(f"\n[EVALUATING] Soil: {current_soil_status} | Stress Factor: {plant_stress_factor}")
    
    # Step 3 from your logic: If soil = "Dry" or "Very Dry"
    if current_soil_status in ["Dry", "Very Dry"]:
        print("-> Status: Irrigation Needed. Calculating precise duration...")
        
        # Calculate water duration proportional to requirement and stress factor
        # Formula: Duration ∝ water_requirement% × plant_stress_factor
        base_duration = 10.0  # 10 seconds baseline
        calculated_duration = base_duration * (water_requirement_pct / 100.0) * plant_stress_factor
        
        print(f"-> Calculated Irrigation Window: {calculated_duration:.2f} seconds.")
        
        # Action: Tell the .ino sketch to physically OPEN the solenoid valve
        Leds.set_led1_color(0, 1, 0) # Turn RGB LED green to show active watering
        arduino_hardware.send_command("VALVE_OPEN", 1)
        
        # Keep valve open for the smart calculated duration, then close it
        time.sleep(calculated_duration)
        
        arduino_hardware.send_command("VALVE_CLOSE", 0)
        Leds.set_led1_color(0, 0, 0) # Turn off status LED
        print("-> Irrigation window complete. Valve CLOSED.")

    # Step 4 from your logic: Else (soil = "Wet" / "Very Wet")
    elif current_soil_status in ["Wet", "Very Wet"]:
        print("-> Status: Adequate Moisture. KEEP valve CLOSED.")
        
        # Action: Ensure valve remains closed via hardware command
        arduino_hardware.send_command("VALVE_CLOSE", 0)
        
        # Send recommendation payload/log based on plant health class (Model 2 data)
        send_farmer_recommendation(current_soil_status, plant_stress_factor)
        
    else:
        print("-> Waiting for stable sensor classifications...")

def send_farmer_recommendation(soil, stress):
    """Logs or transmits diagnostic insights based on Model 2 classifications"""
    print(f"[REPORTS] Telemetry logged: System stable. Soil is {soil}. Stress modifier at {stress}.")

# ==========================================
# 3. MODEL 2 (CAMERA INFERENCE CALLBACK)
# ==========================================
def on_crop_image_detected(predictions):
    """
    Callback function triggered automatically every time Model 2 
    processes a camera frame via the App Lab Brick.
    """
    global plant_stress_factor, water_requirement_pct
    
    for prediction in predictions:
        # Check against the exact labels you trained in Edge Impulse / Colab
        if prediction.label == "stressed_leaf" and prediction.value > 0.70:
            plant_stress_factor = 1.5  # Increase watering window due to physical plant stress
            print(f"[MODEL 2] Leaf Stress Identified ({prediction.value:.2f}). Scaling factor set to 1.5")
            
        elif prediction.label == "healthy_leaf" and prediction.value > 0.70:
            plant_stress_factor = 1.0  # Reset back to standard base multiplier
            
# Assign the camera callback to your model brick interface
crop_camera_model.on_detect(on_crop_image_detected)

# ==========================================
# 4. MAIN EXECUTION LOOP
# ==========================================
print("System Initialized Successfully. Running inference handlers...")

while True:
    try:
        # Pull the current classification sent up by the MCU (.ino sketch running Model 1)
        mcu_data = arduino_hardware.read_string() 
        
        if mcu_data in ["Dry", "Very Dry", "Wet", "Very Wet"]:
            current_soil_status = mcu_data
            print(f"[MODEL 1 Updates] Received soil classification: {current_soil_status}")
            
            # Execute combined smart logic evaluation
            evaluate_combined_decision()
            
    except Exception as e:
        print(f"Polling warning: {e}")
        
    # Polling delay to balance CPU load on the processor
    time.sleep(1)
