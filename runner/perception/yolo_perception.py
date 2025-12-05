import time
from typing import List
from ultralytics import YOLO
from runner.logger import log
from runner.perception.ui_element import UIElement
from runner.config import YOLO_MODEL_PATH

class YOLOPerception:
    def __init__(self, model_path: str = None):
        self.model_path = model_path or YOLO_MODEL_PATH
        log("INFO", "yolo_init", "Initializing YOLO model", model_path=self.model_path)
        try:
            self.model = YOLO(self.model_path)
        except Exception as e:
            log("ERROR", "yolo_init_failed", "Failed to load YOLO model", error=str(e))
            raise

    def analyze(self, screenshot_path: str) -> List[UIElement]:
        """
        Run inference on the screenshot and return detected UI elements.
        """
        start = time.time()
        log("INFO", "perception_yolo_start", "Analyzing screenshot with YOLO", screenshot_path=screenshot_path)

        try:
            # Run inference
            # conf=0.2 is a reasonable default, can be tuned
            results = self.model(screenshot_path, conf=0.2, verbose=False)
            
            elements = []
            if results:
                result = results[0]  # We only process one image
                boxes = result.boxes
                
                for i, box in enumerate(boxes):
                    # xyxy coordinates
                    coords = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                    x1, y1, x2, y2 = map(int, coords)
                    
                    # Confidence
                    conf = float(box.conf[0])
                    
                    # Class
                    cls_id = int(box.cls[0])
                    cls_name = result.names[cls_id]
                    
                    # Create UIElement
                    # We might not have text content from YOLO, so we leave it empty or infer it later (e.g. via OCR)
                    # For now, we just return the box and type.
                    element = UIElement(
                        id=f"yolo-{i}",
                        bbox=[x1, y1, x2, y2],
                        text="", # YOLO doesn't give text
                        type=cls_name,
                        metadata={"confidence": conf}
                    )
                    elements.append(element)

            duration = time.time() - start
            log("INFO", "perception_yolo_done", "YOLO perception complete", duration_ms=int(duration * 1000), count=len(elements))
            return elements

        except Exception as e:
            log("ERROR", "perception_yolo_failed", "YOLO inference failed", error=str(e))
            raise
