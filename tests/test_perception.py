import os
import sys
sys.path.append(os.getcwd())
import pytest
from runner.perception.yolo_perception import YOLOPerception

# Mock YOLO model to avoid downloading large weights during test if possible,
# or just run it if the user wants real verification.
# Since the user asked to "run via UV when done", I assume they want a real run.
# I will try to use the real class.

def test_yolo_perception_init():
    # Test initialization with a standard model to ensure code works
    # We use yolov8n.pt which ultralytics can auto-download
    try:
        perception = YOLOPerception(model_path="yolov8n.pt")
        assert perception.model is not None
        print("YOLOPerception initialized successfully")
    except Exception as e:
        pytest.fail(f"Failed to initialize YOLOPerception: {e}")

def test_yolo_perception_analyze_mock_image(tmp_path):
    # Create a dummy image for testing
    from PIL import Image
    
    img_path = tmp_path / "test_screenshot.png"
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save(img_path)
    
    # Use standard model for test
    perception = YOLOPerception(model_path="yolov8n.pt")
    
    # We expect it to run without error, even if it detects nothing on a red square
    try:
        elements = perception.analyze(str(img_path))
        print(f"Analyzed image, found {len(elements)} elements")
        assert isinstance(elements, list)
    except Exception as e:
        pytest.fail(f"Analysis failed: {e}")

if __name__ == "__main__":
    # Manual run support
    test_yolo_perception_init()
    print("Init test passed")
    
    # Create a temp dir for the image test
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdirname:
        test_yolo_perception_analyze_mock_image(Path(tmpdirname))
    print("Analyze test passed")
